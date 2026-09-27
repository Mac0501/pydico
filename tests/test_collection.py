from __future__ import annotations

import re
from abc import ABC, abstractmethod

import pytest

from pydico.collection import ServiceCollection
from pydico.lifetimes import ServiceLifetime
from pydico.resolver import ServiceResolver


class AbstractService(ABC):
    @abstractmethod
    def run(self) -> str: ...


class Service:
    pass


class AnotherService:
    pass


class ServiceImplementation(Service):
    pass


class AbstractImplementation(Service, ABC):
    @abstractmethod
    def run(self) -> str: ...


def create_service(_: ServiceResolver) -> Service:
    return Service()


def test_registration_methods_return_collection_for_chaining() -> None:
    collection = ServiceCollection()

    assert collection.add_transient(Service) is collection
    assert collection.add_scoped(Service) is collection
    assert collection.add_singleton(Service) is collection
    assert collection.add_instance(Service, Service()) is collection


def test_default_registration_uses_service_type_as_implementation() -> None:
    provider = ServiceCollection().add_transient(Service).build_service_provider()

    assert isinstance(provider.get_service(Service), Service)


def test_registration_accepts_implementation_subclass() -> None:
    provider = (
        ServiceCollection()
        .add_transient(Service, ServiceImplementation)
        .build_service_provider()
    )

    assert isinstance(provider.get_service(Service), ServiceImplementation)


def test_factory_registration_is_used_for_resolution() -> None:
    provider = (
        ServiceCollection()
        .add_transient(Service, factory=create_service)
        .build_service_provider()
    )

    assert isinstance(provider.get_service(Service), Service)


def test_instance_registration_returns_existing_instance() -> None:
    instance = Service()
    provider = (
        ServiceCollection().add_instance(Service, instance).build_service_provider()
    )

    assert provider.get_service(Service) is instance


def test_registration_rejects_implementation_and_factory_together() -> None:
    with pytest.raises(ValueError, match="Use only one"):
        ServiceCollection()._add_descriptor(  # pyright: ignore[reportPrivateUsage]
            service_type=Service,
            lifetime=ServiceLifetime.TRANSIENT,
            implementation_type=ServiceImplementation,
            factory=create_service,
        )


def test_registration_rejects_implementation_and_instance_together() -> None:
    with pytest.raises(ValueError, match="Use only one"):
        ServiceCollection()._add_descriptor(  # pyright: ignore[reportPrivateUsage]
            service_type=Service,
            lifetime=ServiceLifetime.TRANSIENT,
            implementation_type=ServiceImplementation,
            instance=Service(),
        )


def test_registration_rejects_factory_and_instance_together() -> None:
    with pytest.raises(ValueError, match="Use only one"):
        ServiceCollection()._add_descriptor(  # pyright: ignore[reportPrivateUsage]
            service_type=Service,
            lifetime=ServiceLifetime.TRANSIENT,
            factory=create_service,
            instance=Service(),
        )


def test_abstract_service_requires_explicit_construction_strategy() -> None:
    with pytest.raises(TypeError, match="abstract"):
        ServiceCollection().add_transient(AbstractService)


def test_abstract_implementation_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be abstract"):
        ServiceCollection().add_transient(Service, AbstractImplementation)


def test_implementation_must_subclass_service_type() -> None:
    with pytest.raises(ValueError, match="must be a subclass"):
        ServiceCollection().add_transient(
            Service, AnotherService
        )  # pyright: ignore[reportArgumentType]


def test_instance_must_match_service_type() -> None:
    with pytest.raises(
        ValueError,
        match=re.escape("must be an instance of service type"),
    ):
        ServiceCollection().add_instance(
            Service, AnotherService()
        )  # pyright: ignore[reportArgumentType]
