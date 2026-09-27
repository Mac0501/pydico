from __future__ import annotations

import inspect
from collections.abc import Generator, Hashable, Sequence
from contextlib import contextmanager
from threading import Condition, RLock, local
from types import TracebackType
from typing import TYPE_CHECKING, TypeGuard, TypeVar, cast, get_type_hints

from pydico._disposal import close_instances
from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import (
    CircularDependencyError,
    InjectionError,
    MissingTypeAnnotationError,
    ProviderClosedError,
    ResolutionError,
    ScopeRequiredError,
    ServiceNotRegisteredError,
    UnsupportedTypeAnnotationError,
)
from pydico.identifiers import ServiceIdentifier
from pydico.lifecycle import SupportsClose
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
        self._owned_singletons: list[SupportsClose] = []
        self._owned_singleton_ids: set[int] = set()
        self._singleton_lock = RLock()
        self._resolution_state = _ResolutionState()
        self._lifecycle = Condition(RLock())
        self._active_resolutions = 0
        self._closing = False
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
                    instance = self._create_from_descriptor(descriptor, resolver=self)
                    self._singleton_instances[cache_key] = instance
                    instance_id = id(instance)
                    if (
                        isinstance(instance, SupportsClose)
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
        signature = inspect.signature(implementation_type.__init__)
        try:
            type_hints = get_type_hints(implementation_type.__init__)
        except Exception as error:
            raise InjectionError(
                f"Cannot resolve type annotations for "
                f"{implementation_type.__qualname__}."
            ) from error
        kwargs: dict[str, object] = {}

        for name, parameter in signature.parameters.items():
            if name == "self":
                continue

            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            if parameter.default is not inspect.Parameter.empty:
                continue

            annotation = type_hints.get(name)
            if annotation is None:
                raise MissingTypeAnnotationError(implementation_type, name)

            if not _is_type(annotation):
                raise UnsupportedTypeAnnotationError(
                    implementation_type, name, annotation
                )

            dependency = resolver.get_service(annotation)
            if dependency is None:
                raise ServiceNotRegisteredError(
                    annotation,
                    target=implementation_type,
                    parameter_name=name,
                )

            kwargs[name] = dependency

        return implementation_type(**kwargs)

    def close(self) -> None:
        with self._lifecycle:
            if self._closed:
                return
            if self._closing:
                while not self._closed:
                    self._lifecycle.wait()
                return
            if self._resolution_state.activity_depth > 0:
                raise RuntimeError(
                    "Cannot close the service provider during service resolution."
                )
            self._closing = True
            while self._active_resolutions > 0:
                self._lifecycle.wait()

        with self._singleton_lock:
            instances = tuple(reversed(self._owned_singletons))
            self._owned_singletons.clear()
            self._owned_singleton_ids.clear()
            self._singleton_instances.clear()

        try:
            close_instances(instances)
        finally:
            with self._lifecycle:
                self._closed = True
                self._closing = False
                self._lifecycle.notify_all()

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


def _is_type(value: object) -> TypeGuard[type[object]]:
    return isinstance(value, type)


class _ResolutionState(local):
    def __init__(self) -> None:
        self.stack: list[ServiceDescriptor[object]] = []
        self.activity_depth = 0
