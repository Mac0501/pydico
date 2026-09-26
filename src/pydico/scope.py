from __future__ import annotations

from collections.abc import Hashable
from threading import RLock
from types import TracebackType
from typing import TypeVar, cast

from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import ScopeClosedError
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
        self._lock = RLock()
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise ScopeClosedError("This service scope is closed.")

    def get_service(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> T | None:
        with self._lock:
            self._ensure_open()
            if key is None:
                if service_type in (ServiceScope, ServiceResolver):
                    return cast(T, self)
                if service_type is ServiceProvider:
                    return cast(T, self._root_provider)
            descriptor = self._root_provider._get_descriptor(service_type, key=key)
            if descriptor is None:
                return None
            result = self._root_provider._get_from_descriptor(descriptor, scope=self)
            self._ensure_open()
            return result

    def get_services(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> tuple[T, ...]:
        with self._lock:
            self._ensure_open()
            result = tuple(
                self._root_provider._get_from_descriptor(descriptor, scope=self)
                for descriptor in self._root_provider._get_descriptors(
                    service_type, key=key
                )
            )
            self._ensure_open()
            return result

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
            return cast(T, self._scoped_instances[cache_key])

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._scoped_instances.clear()

    def __enter__(self) -> ServiceScope:
        with self._lock:
            self._ensure_open()
            return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
