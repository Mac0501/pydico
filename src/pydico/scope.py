from __future__ import annotations

from collections.abc import Hashable
from contextvars import Token
from threading import RLock, local
from types import TracebackType
from typing import TypeVar, cast

from pydico._context import activate_resolver, restore_resolver
from pydico._disposal import close_instances
from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import CloseDuringResolutionError, ScopeClosedError
from pydico.lifecycle import SupportsClose
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
        self._owned_instances: list[SupportsClose] = []
        self._owned_instance_ids: set[int] = set()
        self._lock = RLock()
        self._resolution_state = _ScopeResolutionState()
        self._closed = False
        self._activation_token: Token[ServiceResolver | None] | None = None

    def _ensure_open(self) -> None:
        if self._closed:
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
                    isinstance(instance, SupportsClose)
                    and instance_id not in self._owned_instance_ids
                ):
                    self._owned_instances.append(instance)
                    self._owned_instance_ids.add(instance_id)
            return cast(T, self._scoped_instances[cache_key])

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            if self._resolution_state.activity_depth > 0:
                raise CloseDuringResolutionError(self)
            self._closed = True
            instances = tuple(reversed(self._owned_instances))
            self._owned_instances.clear()
            self._owned_instance_ids.clear()
            self._scoped_instances.clear()
        close_instances(instances)

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


class _ScopeResolutionState(local):
    def __init__(self) -> None:
        self.activity_depth = 0
