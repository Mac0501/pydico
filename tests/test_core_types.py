from __future__ import annotations

import pytest

from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import CircularDependencyError
from pydico.identifiers import ServiceIdentifier
from pydico.lifetimes import ServiceLifetime


class Service:
    pass


class OtherService:
    pass


def test_service_lifetime_values_are_stable() -> None:
    assert ServiceLifetime.SINGLETON.value == "singleton"
    assert ServiceLifetime.SCOPED.value == "scoped"
    assert ServiceLifetime.TRANSIENT.value == "transient"


def test_service_descriptor_is_immutable() -> None:
    descriptor = ServiceDescriptor(
        service_type=Service,
        lifetime=ServiceLifetime.TRANSIENT,
    )

    with pytest.raises(AttributeError):
        setattr(descriptor, "lifetime", ServiceLifetime.SINGLETON)


def test_service_descriptor_preserves_registration_metadata() -> None:
    instance = Service()

    descriptor = ServiceDescriptor(
        service_type=Service,
        lifetime=ServiceLifetime.SINGLETON,
        implementation_type=Service,
        instance=instance,
        key="main",
    )

    assert descriptor.service_type is Service
    assert descriptor.lifetime is ServiceLifetime.SINGLETON
    assert descriptor.implementation_type is Service
    assert descriptor.instance is instance
    assert descriptor.key == "main"


def test_circular_dependency_error_exposes_chain_and_message() -> None:
    first = ServiceIdentifier(Service, key="first")
    second = ServiceIdentifier(OtherService)
    chain = (first, second, first)
    error = CircularDependencyError(chain)

    assert error.chain == (first, second, first)
    assert str(error) == (
        "Circular dependency detected: "
        "Service[key='first'] -> OtherService -> Service[key='first']"
    )
