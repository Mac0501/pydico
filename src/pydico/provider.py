from __future__ import annotations

import inspect
from collections.abc import Hashable, Sequence
from threading import RLock, local
from typing import TYPE_CHECKING, TypeGuard, TypeVar, cast, get_type_hints

from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import CircularDependencyError, ScopedResolutionError
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
        self._singleton_lock = RLock()
        self._resolution_state = _ResolutionState()

    def create_scope(self) -> ServiceScope:
        from pydico.scope import ServiceScope

        return ServiceScope(self)

    def get_service(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> T | None:
        if key is None and service_type in (ServiceProvider, ServiceResolver):
            return cast(T, self)

        descriptor = self._get_descriptor(service_type, key=key)
        if descriptor is None:
            return None
        return self._get_from_descriptor(descriptor)

    def get_services(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> tuple[T, ...]:
        return tuple(
            self._get_from_descriptor(descriptor)
            for descriptor in self._get_descriptors(service_type, key=key)
        )

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
                    self._singleton_instances[cache_key] = self._create_from_descriptor(
                        descriptor, resolver=self
                    )
                return cast(T, self._singleton_instances[cache_key])

        if descriptor.lifetime is ServiceLifetime.TRANSIENT:
            return self._create_from_descriptor(descriptor, resolver=scope or self)

        if scope is None:
            raise ScopedResolutionError(
                f"Scoped service {descriptor.service_type.__qualname__} requires an active scope. Use provider.create_scope()."
            )
        return scope._get_scoped_instance(descriptor)

    def _create_from_descriptor(
        self, descriptor: ServiceDescriptor[T], *, resolver: ServiceResolver
    ) -> T:
        stack = self._resolution_state.stack
        for index, active_descriptor in enumerate(stack):
            if active_descriptor is descriptor:
                raise CircularDependencyError((*stack[index:], active_descriptor))

        stack.append(cast(ServiceDescriptor[object], descriptor))
        try:
            if descriptor.factory is not None:
                return descriptor.factory(resolver)

            if descriptor.implementation_type is None:
                raise TypeError(
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
        type_hints = get_type_hints(implementation_type.__init__)
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
                raise TypeError(
                    f"Cannot resolve parameter {name!r} for {implementation_type.__name__}: missing type annotation."
                )

            if not _is_type(annotation):
                raise TypeError(
                    f"Cannot resolve parameter {name!r} for {implementation_type.__name__}: annotation must be a type."
                )

            dependency = resolver.get_service(annotation)
            if dependency is None:
                raise LookupError(
                    f"No service registered for dependency {annotation} required by {implementation_type.__name__}."
                )

            kwargs[name] = dependency

        return implementation_type(**kwargs)


def _is_type(value: object) -> TypeGuard[type[object]]:
    return isinstance(value, type)


class _ResolutionState(local):
    def __init__(self) -> None:
        self.stack: list[ServiceDescriptor[object]] = []
