from collections.abc import Callable, Hashable
from inspect import isabstract
from threading import RLock
from typing import Self, TypeVar, overload

from pydico.descriptors import ServiceDescriptor
from pydico.lifetimes import ServiceLifetime
from pydico.provider import ServiceProvider
from pydico.resolver import ServiceResolver

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
        factory: Callable[[ServiceResolver], T],
        key: Hashable | None = None,
    ) -> Self: ...

    def add_transient(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        *,
        factory: Callable[[ServiceResolver], T] | None = None,
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
        factory: Callable[[ServiceResolver], T],
        key: Hashable | None = None,
    ) -> Self: ...

    def add_scoped(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        *,
        factory: Callable[[ServiceResolver], T] | None = None,
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
        factory: Callable[[ServiceResolver], T],
        key: Hashable | None = None,
    ) -> Self: ...

    def add_singleton(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        *,
        factory: Callable[[ServiceResolver], T] | None = None,
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
        factory: Callable[[ServiceResolver], T] | None = None,
        key: Hashable | None = None,
    ) -> Self:

        self._validate_descriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            instance=instance,
        )

        descriptor: ServiceDescriptor[object] = ServiceDescriptor(
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
        with self._lock:
            self._descriptors.append(descriptor)

        return self

    def _validate_descriptor(
        self,
        service_type: type[T],
        implementation_type: type[T] | None,
        factory: Callable[[ServiceResolver], T] | None,
        instance: T | None,
    ) -> None:

        if (
            sum(value is not None for value in (implementation_type, factory, instance))
            > 1
        ):
            raise ValueError(
                "Use only one of implementation_type, factory, or instance."
            )

        if implementation_type is not None:
            if isabstract(implementation_type):
                raise ValueError(
                    f"Implementation type {implementation_type} cannot be abstract."
                )

            if not issubclass(implementation_type, service_type):
                raise ValueError(
                    f"Implementation type {implementation_type} must be a subclass of service type {service_type}."
                )

        if instance is not None and not isinstance(instance, service_type):
            raise ValueError(
                f"Instance {instance} must be an instance of service type {service_type}."
            )

        if implementation_type is None and factory is None and instance is None:
            if isabstract(service_type):
                raise TypeError(
                    f"Service type {service_type} is abstract and needs an implementation, factory, or instance."
                )
