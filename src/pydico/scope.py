from __future__ import annotations

import asyncio
from collections.abc import Hashable
from contextvars import Token
from threading import Condition, RLock, get_ident, local
from types import TracebackType
from typing import TypeVar, cast

from pydico._context import activate_resolver, restore_resolver
from pydico._disposal import aclose_instances, close_instances, ensure_sync_disposable
from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import CloseDuringResolutionError, ScopeClosedError
from pydico.lifecycle import OwnedResource, SupportsAsyncClose, SupportsClose
from pydico.provider import ServiceProvider
from pydico.resolver import ServiceResolver

# Provider and scope intentionally share internal resolution operations.
# pyright: reportPrivateUsage=false


T = TypeVar("T")


class ServiceScope:
    """An independent cache with a synchronized resolution lifecycle."""

    def __init__(self, root_provider: ServiceProvider) -> None:
        self._root_provider = root_provider
        self._scoped_instances: dict[int, object] = {}
        self._owned_instances: list[OwnedResource] = []
        self._owned_instance_ids: set[int] = set()
        self._lock = RLock()
        self._lifecycle = Condition(self._lock)
        self._resolution_state = _ScopeResolutionState()
        self._closing = False
        self._closing_thread_id: int | None = None
        self._closing_async_task: asyncio.Task[object] | None = None
        self._closed = False
        self._activation_token: Token[ServiceResolver | None] | None = None

    def _ensure_open(self) -> None:
        if self._closing or self._closed:
            raise ScopeClosedError()

    def get_service(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> T | None:
        with self._lock:
            self._ensure_open()
            self._resolution_state.activity_depth += 1
            try:
                with self._root_provider._resolution_context():
                    if key is None:
                        if service_type in (ServiceScope, ServiceResolver):
                            return cast(T, self)
                        if service_type is ServiceProvider:
                            return cast(T, self._root_provider)
                    descriptor = self._root_provider._get_descriptor(
                        service_type, key=key
                    )
                    if descriptor is None:
                        return None
                    result = self._root_provider._get_from_descriptor(
                        descriptor, scope=self
                    )
                    self._ensure_open()
                    return result
            finally:
                self._resolution_state.activity_depth -= 1

    def get_services(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> tuple[T, ...]:
        with self._lock:
            self._ensure_open()
            self._resolution_state.activity_depth += 1
            try:
                with self._root_provider._resolution_context():
                    result = tuple(
                        self._root_provider._get_from_descriptor(descriptor, scope=self)
                        for descriptor in self._root_provider._get_descriptors(
                            service_type, key=key
                        )
                    )
                    self._ensure_open()
                    return result
            finally:
                self._resolution_state.activity_depth -= 1

    def _get_scoped_instance(self, descriptor: ServiceDescriptor[T]) -> T:
        with self._lock:
            self._ensure_open()
            cache_key = id(descriptor)
            if cache_key not in self._scoped_instances:
                instance = self._root_provider._create_from_descriptor(
                    descriptor, resolver=self
                )
                self._ensure_open()
                self._scoped_instances[cache_key] = instance
                instance_id = id(instance)
                if (
                    isinstance(instance, (SupportsClose, SupportsAsyncClose))
                    and instance_id not in self._owned_instance_ids
                ):
                    self._owned_instances.append(instance)
                    self._owned_instance_ids.add(instance_id)
            return cast(T, self._scoped_instances[cache_key])

    def close(self) -> None:
        closing_thread_id = get_ident()
        if not self._begin_sync_close(closing_thread_id):
            return

        with self._lock:
            instances = tuple(reversed(self._owned_instances))
            try:
                ensure_sync_disposable(instances)
            except BaseException:
                self._abort_close()
                raise
            self._clear_instances()
        try:
            close_instances(instances)
        finally:
            self._finish_close()

    async def aclose(self) -> None:
        if self._resolution_state.activity_depth > 0:
            raise CloseDuringResolutionError(self)
        owner = asyncio.current_task()
        if owner is None:
            raise RuntimeError("ServiceScope.aclose() requires an asyncio task.")
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

        with self._lock:
            instances = tuple(reversed(self._owned_instances))
            self._clear_instances()

        async def dispose() -> None:
            try:
                await aclose_instances(instances)
            finally:
                self._finish_close()

        cleanup = asyncio.create_task(dispose())
        with self._lock:
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
                    return True
                if self._closing_async_task is owner:
                    return False
                self._lifecycle.wait()

    def _clear_instances(self) -> None:
        self._owned_instances.clear()
        self._owned_instance_ids.clear()
        self._scoped_instances.clear()

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

    def __enter__(self) -> ServiceScope:
        with self._lock:
            self._ensure_open()
            if self._activation_token is not None:
                raise RuntimeError("This service scope is already active.")
            self._activation_token = activate_resolver(self)
            return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        with self._lock:
            token = self._activation_token
            self._activation_token = None
        try:
            if token is not None:
                restore_resolver(token)
        finally:
            self.close()

    async def __aenter__(self) -> ServiceScope:
        with self._lock:
            self._ensure_open()
            if self._activation_token is not None:
                raise RuntimeError("This service scope is already active.")
            self._activation_token = activate_resolver(self)
            return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        with self._lock:
            token = self._activation_token
            self._activation_token = None
        try:
            if token is not None:
                restore_resolver(token)
        finally:
            await self.aclose()


class _ScopeResolutionState(local):
    def __init__(self) -> None:
        self.activity_depth = 0
