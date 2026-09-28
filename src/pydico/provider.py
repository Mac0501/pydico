from __future__ import annotations

import asyncio
from collections.abc import Generator, Hashable, Sequence
from contextlib import contextmanager
from threading import Condition, RLock, get_ident, local
from types import TracebackType
from typing import TYPE_CHECKING, TypeVar, cast

from pydico._context import activate_resolver, restore_resolver
from pydico._dependencies import DependencyPlan, resolve_dependency
from pydico._disposal import aclose_instances, close_instances, ensure_sync_disposable
from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import (
    CircularDependencyError,
    CloseDuringResolutionError,
    ProviderClosedError,
    ResolutionError,
    ScopeRequiredError,
)
from pydico.identifiers import ServiceIdentifier
from pydico.lifecycle import OwnedResource, SupportsAsyncClose, SupportsClose
from pydico.lifetimes import ServiceLifetime
from pydico.resolver import ServiceResolver

# Provider and scope intentionally share internal resolution operations.
# pyright: reportPrivateUsage=false


if TYPE_CHECKING:
    from pydico.scope import ServiceScope

T = TypeVar("T")


class ServiceProvider:
    def __init__(self, descriptors: Sequence[ServiceDescriptor[object]]) -> None:
        self._descriptors = tuple(descriptors)
        self._singleton_instances: dict[int, object] = {}
        self._owned_singletons: list[OwnedResource] = []
        self._owned_singleton_ids: set[int] = set()
        self._singleton_lock = RLock()
        self._constructor_plans: dict[type[object], DependencyPlan] = {}
        self._constructor_plans_lock = RLock()
        self._resolution_state = _ResolutionState()
        self._lifecycle = Condition(RLock())
        self._active_resolutions = 0
        self._closing = False
        self._closing_thread_id: int | None = None
        self._closing_async_task: asyncio.Task[object] | None = None
        self._closed = False

    def create_scope(self) -> ServiceScope:
        from pydico.scope import ServiceScope

        with self._lifecycle:
            self._ensure_open()
            return ServiceScope(self)

    def get_service(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> T | None:
        with self._resolution_context():
            if key is None and service_type in (ServiceProvider, ServiceResolver):
                return cast(T, self)

            descriptor = self._get_descriptor(service_type, key=key)
            if descriptor is None:
                return None
            return self._get_from_descriptor(descriptor)

    def get_services(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> tuple[T, ...]:
        with self._resolution_context():
            return tuple(
                self._get_from_descriptor(descriptor)
                for descriptor in self._get_descriptors(service_type, key=key)
            )

    def _ensure_open(self) -> None:
        if self._closing or self._closed:
            raise ProviderClosedError()

    @contextmanager
    def _resolution_context(self) -> Generator[None]:
        state = self._resolution_state
        with self._lifecycle:
            if state.activity_depth == 0:
                self._ensure_open()
            self._active_resolutions += 1
            state.activity_depth += 1
        try:
            yield
        finally:
            with self._lifecycle:
                state.activity_depth -= 1
                self._active_resolutions -= 1
                if self._active_resolutions == 0:
                    self._lifecycle.notify_all()

    def _get_descriptor(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> ServiceDescriptor[T] | None:
        descriptors = self._get_descriptors(service_type, key=key)
        if not descriptors:
            return None
        return descriptors[-1]

    def _get_descriptors(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> tuple[ServiceDescriptor[T], ...]:
        return tuple(
            cast(ServiceDescriptor[T], descriptor)
            for descriptor in self._descriptors
            if descriptor.service_type is service_type and descriptor.key == key
        )

    def _get_from_descriptor(
        self, descriptor: ServiceDescriptor[T], *, scope: ServiceScope | None = None
    ) -> T:
        if descriptor.instance is not None:
            return descriptor.instance

        if descriptor.lifetime is ServiceLifetime.SINGLETON:
            cache_key = id(descriptor)
            with self._singleton_lock:
                if cache_key not in self._singleton_instances:
                    token = activate_resolver(self)
                    try:
                        instance = self._create_from_descriptor(
                            descriptor, resolver=self
                        )
                    finally:
                        restore_resolver(token)
                    self._singleton_instances[cache_key] = instance
                    instance_id = id(instance)
                    if (
                        isinstance(instance, (SupportsClose, SupportsAsyncClose))
                        and instance_id not in self._owned_singleton_ids
                    ):
                        self._owned_singletons.append(instance)
                        self._owned_singleton_ids.add(instance_id)
                return cast(T, self._singleton_instances[cache_key])

        if descriptor.lifetime is ServiceLifetime.TRANSIENT:
            return self._create_from_descriptor(descriptor, resolver=scope or self)

        if scope is None:
            raise ScopeRequiredError(descriptor.service_type, descriptor.key)
        return scope._get_scoped_instance(descriptor)

    def _create_from_descriptor(
        self, descriptor: ServiceDescriptor[T], *, resolver: ServiceResolver
    ) -> T:
        stack = self._resolution_state.stack
        for index, active_descriptor in enumerate(stack):
            if active_descriptor is descriptor:
                cycle = (*stack[index:], active_descriptor)
                raise CircularDependencyError(
                    tuple(
                        ServiceIdentifier(item.service_type, item.key) for item in cycle
                    )
                )

        stack.append(descriptor)
        try:
            if descriptor.factory is not None:
                return descriptor.factory(resolver)

            if descriptor.implementation_type is None:
                raise ResolutionError(
                    f"Service type {descriptor.service_type} has no implementation, factory, or instance."
                )

            return self._create_instance(
                descriptor.implementation_type, resolver=resolver
            )
        finally:
            stack.pop()

    def _create_instance(
        self, implementation_type: type[T], *, resolver: ServiceResolver
    ) -> T:
        plan = self._get_constructor_plan(implementation_type)
        requests = plan.requests(plan.required_parameters())
        args: list[object] = []
        kwargs: dict[str, object] = {}

        for request in requests:
            dependency = resolve_dependency(
                request, resolver=resolver, target=implementation_type
            )
            if request.positional_only:
                args.append(dependency)
            else:
                kwargs[request.parameter_name] = dependency

        return implementation_type(*args, **kwargs)

    def _get_constructor_plan(
        self, implementation_type: type[object]
    ) -> DependencyPlan:
        with self._constructor_plans_lock:
            plan = self._constructor_plans.get(implementation_type)
            if plan is None:
                plan = DependencyPlan(
                    implementation_type.__init__, error_target=implementation_type
                )
                self._constructor_plans[implementation_type] = plan
            return plan

    def close(self) -> None:
        closing_thread_id = get_ident()
        if not self._begin_sync_close(closing_thread_id):
            return

        with self._singleton_lock:
            instances = tuple(reversed(self._owned_singletons))
            try:
                ensure_sync_disposable(instances)
            except BaseException:
                self._abort_close()
                raise
            self._clear_singletons()

        try:
            close_instances(instances)
        finally:
            self._finish_close()

    async def aclose(self) -> None:
        if self._resolution_state.activity_depth > 0:
            raise CloseDuringResolutionError(self)
        owner = asyncio.current_task()
        if owner is None:
            raise RuntimeError("ServiceProvider.aclose() requires an asyncio task.")
        closing_thread_id = get_ident()
        begin = asyncio.create_task(
            asyncio.to_thread(self._begin_async_close, owner, closing_thread_id)
        )
        cancellation: asyncio.CancelledError | None = None
        while not begin.done():
            try:
                await asyncio.shield(begin)
            except asyncio.CancelledError as error:
                cancellation = error
        should_close = begin.result()
        if not should_close:
            if cancellation is not None:
                raise cancellation
            return

        with self._singleton_lock:
            instances = tuple(reversed(self._owned_singletons))
            self._clear_singletons()

        async def dispose() -> None:
            try:
                await aclose_instances(instances)
            finally:
                self._finish_close()

        cleanup = asyncio.create_task(dispose())
        with self._lifecycle:
            if self._closing_async_task is owner:
                self._closing_async_task = cleanup

        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError as error:
                cancellation = error
            except Exception:
                break
        cleanup_error: Exception | None = None
        try:
            cleanup.result()
        except Exception as error:
            cleanup_error = error
        if cancellation is not None:
            if cleanup_error is not None:
                raise cancellation from cleanup_error
            raise cancellation
        if cleanup_error is not None:
            raise cleanup_error

    def _begin_sync_close(self, closing_thread_id: int) -> bool:
        with self._lifecycle:
            while True:
                if self._closed:
                    return False
                if self._resolution_state.activity_depth > 0:
                    raise CloseDuringResolutionError(self)
                if not self._closing:
                    self._closing = True
                    self._closing_thread_id = closing_thread_id
                    self._closing_async_task = None
                    while self._active_resolutions > 0:
                        self._lifecycle.wait()
                    return True
                if self._closing_thread_id == closing_thread_id:
                    return False
                self._lifecycle.wait()

    def _begin_async_close(
        self,
        owner: asyncio.Task[object],
        closing_thread_id: int,
    ) -> bool:
        with self._lifecycle:
            while True:
                if self._closed:
                    return False
                if not self._closing:
                    self._closing = True
                    self._closing_thread_id = closing_thread_id
                    self._closing_async_task = owner
                    while self._active_resolutions > 0:
                        self._lifecycle.wait()
                    return True
                if self._closing_async_task is owner:
                    return False
                self._lifecycle.wait()

    def _clear_singletons(self) -> None:
        self._owned_singletons.clear()
        self._owned_singleton_ids.clear()
        self._singleton_instances.clear()

    def _abort_close(self) -> None:
        with self._lifecycle:
            self._closing = False
            self._closing_thread_id = None
            self._closing_async_task = None
            self._lifecycle.notify_all()

    def _finish_close(self) -> None:
        with self._lifecycle:
            self._closed = True
            self._closing = False
            self._closing_thread_id = None
            self._closing_async_task = None
            self._lifecycle.notify_all()

    async def __aenter__(self) -> ServiceProvider:
        with self._lifecycle:
            self._ensure_open()
            return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    def __enter__(self) -> ServiceProvider:
        with self._lifecycle:
            self._ensure_open()
            return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class _ResolutionState(local):
    def __init__(self) -> None:
        self.stack: list[ServiceDescriptor[object]] = []
        self.activity_depth = 0
