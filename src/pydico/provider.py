from __future__ import annotations

import inspect
from collections.abc import Hashable, Sequence
from typing import TypeGuard, TypeVar, cast, get_type_hints

from pydico.descriptors import ServiceDescriptor
from pydico.lifetimes import ServiceLifetime

T = TypeVar("T")


class ServiceProvider:
    def __init__(self, descriptors: Sequence[ServiceDescriptor[object]]) -> None:
        self._descriptors = tuple(descriptors)
        self._singleton_instances: dict[int, object] = {}

    def get_service(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> T | None:
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

    def _get_from_descriptor(self, descriptor: ServiceDescriptor[T]) -> T:
        if descriptor.instance is not None:
            return descriptor.instance

        if descriptor.lifetime is ServiceLifetime.SINGLETON:
            cache_key = id(descriptor)
            if cache_key not in self._singleton_instances:
                self._singleton_instances[cache_key] = self._create_from_descriptor(
                    descriptor
                )
            return cast(T, self._singleton_instances[cache_key])

        if descriptor.lifetime is ServiceLifetime.TRANSIENT:
            return self._create_from_descriptor(descriptor)

        raise NotImplementedError("Scoped services are not supported yet.")

    def _create_from_descriptor(self, descriptor: ServiceDescriptor[T]) -> T:
        if descriptor.factory is not None:
            return descriptor.factory(self)

        if descriptor.implementation_type is None:
            raise TypeError(
                f"Service type {descriptor.service_type} has no implementation, factory, or instance."
            )

        return self._create_instance(descriptor.implementation_type)

    def _create_instance(self, implementation_type: type[T]) -> T:
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

            dependency = self.get_service(annotation)
            if dependency is None:
                raise LookupError(
                    f"No service registered for dependency {annotation} required by {implementation_type.__name__}."
                )

            kwargs[name] = dependency

        return implementation_type(**kwargs)


def _is_type(value: object) -> TypeGuard[type[object]]:
    return isinstance(value, type)
