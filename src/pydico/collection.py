from collections.abc import Hashable
from inspect import isabstract
from threading import RLock
from typing import Self, TypeVar, overload

from pydico._typing import ServiceFactory
from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import (
    AbstractTypeRegistrationError,
    ConflictingRegistrationError,
    ImplementationTypeMismatchError,
    InstanceTypeMismatchError,
)
from pydico.lifetimes import ServiceLifetime
from pydico.provider import ServiceProvider

T = TypeVar("T")


class ServiceCollection:

    def __init__(self) -> None:
        self._descriptors: list[ServiceDescriptor[object]] = []
        self._lock = RLock()

    @overload
    def add_transient(
        self,
        service_type: type[T],
        *,
        key: Hashable | None = None,
    ) -> Self: ...

    @overload
    def add_transient(
        self,
        service_type: type[T],
        implementation_type: type[T],
        *,
        key: Hashable | None = None,
    ) -> Self: ...

    @overload
    def add_transient(
        self,
        service_type: type[T],
        *,
        factory: ServiceFactory[T],
        key: Hashable | None = None,
    ) -> Self: ...

    def add_transient(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        *,
        factory: ServiceFactory[T] | None = None,
        key: Hashable | None = None,
    ) -> Self:
        return self._add_descriptor(
            service_type=service_type,
            lifetime=ServiceLifetime.TRANSIENT,
            implementation_type=implementation_type,
            factory=factory,
            key=key,
        )

    @overload
    def add_scoped(
        self,
        service_type: type[T],
        *,
        key: Hashable | None = None,
    ) -> Self: ...

    @overload
    def add_scoped(
        self,
        service_type: type[T],
        implementation_type: type[T],
        *,
        key: Hashable | None = None,
    ) -> Self: ...

    @overload
    def add_scoped(
        self,
        service_type: type[T],
        *,
        factory: ServiceFactory[T],
        key: Hashable | None = None,
    ) -> Self: ...

    def add_scoped(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        *,
        factory: ServiceFactory[T] | None = None,
        key: Hashable | None = None,
    ) -> Self:
        return self._add_descriptor(
            service_type=service_type,
            lifetime=ServiceLifetime.SCOPED,
            implementation_type=implementation_type,
            factory=factory,
            key=key,
        )

    @overload
    def add_singleton(
        self,
        service_type: type[T],
        *,
        key: Hashable | None = None,
    ) -> Self: ...

    @overload
    def add_singleton(
        self,
        service_type: type[T],
        implementation_type: type[T],
        *,
        key: Hashable | None = None,
    ) -> Self: ...

    @overload
    def add_singleton(
        self,
        service_type: type[T],
        *,
        factory: ServiceFactory[T],
        key: Hashable | None = None,
    ) -> Self: ...

    def add_singleton(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        *,
        factory: ServiceFactory[T] | None = None,
        key: Hashable | None = None,
    ) -> Self:
        return self._add_descriptor(
            service_type=service_type,
            lifetime=ServiceLifetime.SINGLETON,
            implementation_type=implementation_type,
            factory=factory,
            key=key,
        )

    def add_instance(
        self,
        service_type: type[T],
        instance: T,
        *,
        key: Hashable | None = None,
    ) -> Self:
        return self._add_descriptor(
            service_type=service_type,
            lifetime=ServiceLifetime.SINGLETON,
            instance=instance,
            key=key,
        )

    def build_service_provider(self) -> ServiceProvider:
        with self._lock:
            descriptors = tuple(self._descriptors)

        return ServiceProvider(descriptors)

    def _add_descriptor(
        self,
        *,
        service_type: type[T],
        lifetime: ServiceLifetime,
        implementation_type: type[T] | None = None,
        instance: T | None = None,
        factory: ServiceFactory[T] | None = None,
        key: Hashable | None = None,
    ) -> Self:

        self._validate_descriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            instance=instance,
        )

        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=(
                None
                if factory is not None or instance is not None
                else implementation_type or service_type
            ),
            factory=factory,
            instance=instance,
            lifetime=lifetime,
            key=key,
        )
        self._append_descriptor(descriptor)

        return self

    def _append_descriptor(self, descriptor: ServiceDescriptor[object]) -> None:
        with self._lock:
            self._descriptors.append(descriptor)

    def _validate_descriptor(
        self,
        service_type: type[T],
        implementation_type: type[T] | None,
        factory: ServiceFactory[T] | None,
        instance: T | None,
    ) -> None:

        strategies = tuple(
            name
            for name, value in (
                ("implementation_type", implementation_type),
                ("factory", factory),
                ("instance", instance),
            )
            if value is not None
        )
        if len(strategies) > 1:
            raise ConflictingRegistrationError(service_type, strategies)

        if implementation_type is not None:
            if isabstract(implementation_type):
                raise AbstractTypeRegistrationError(service_type, implementation_type)

            if not issubclass(implementation_type, service_type):
                raise ImplementationTypeMismatchError(service_type, implementation_type)

        if instance is not None and not isinstance(instance, service_type):
            raise InstanceTypeMismatchError(service_type, type(instance))

        if implementation_type is None and factory is None and instance is None:
            if isabstract(service_type):
                raise AbstractTypeRegistrationError(service_type)
