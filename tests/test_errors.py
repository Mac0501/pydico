from collections.abc import Hashable

import pytest

from pydico import (
    AbstractTypeRegistrationError,
    CircularDependencyError,
    ConflictingInjectKeyError,
    ConflictingRegistrationError,
    DisposalError,
    ImplementationTypeMismatchError,
    InjectionError,
    InstanceTypeMismatchError,
    MissingTypeAnnotationError,
    NoActiveScopeError,
    ProviderClosedError,
    PydicoError,
    RegistrationError,
    ResolutionError,
    ScopeClosedError,
    ScopeRequiredError,
    ServiceIdentifier,
    ServiceNotRegisteredError,
    UnsupportedTypeAnnotationError,
)


class Service:
    pass


class Implementation(Service):
    pass


class Other:
    pass


def target(dependency: Service) -> None:
    pass


@pytest.mark.parametrize(
    ("error_type", "base_type"),
    [
        (RegistrationError, PydicoError),
        (ConflictingRegistrationError, RegistrationError),
        (ImplementationTypeMismatchError, RegistrationError),
        (AbstractTypeRegistrationError, RegistrationError),
        (InstanceTypeMismatchError, RegistrationError),
        (ResolutionError, PydicoError),
        (ProviderClosedError, ResolutionError),
        (ScopeClosedError, ResolutionError),
        (ScopeRequiredError, ResolutionError),
        (CircularDependencyError, ResolutionError),
        (ServiceNotRegisteredError, ResolutionError),
        (InjectionError, ResolutionError),
        (ConflictingInjectKeyError, InjectionError),
        (NoActiveScopeError, InjectionError),
        (MissingTypeAnnotationError, InjectionError),
        (UnsupportedTypeAnnotationError, InjectionError),
        (DisposalError, PydicoError),
    ],
)
def test_error_hierarchy(
    error_type: type[Exception], base_type: type[Exception]
) -> None:
    assert issubclass(error_type, base_type)


def test_registration_errors_expose_structured_context() -> None:
    conflict = ConflictingRegistrationError(Service, ("implementation_type", "factory"))
    mismatch = ImplementationTypeMismatchError(Service, Other)
    abstract = AbstractTypeRegistrationError(Service, Implementation)
    instance = InstanceTypeMismatchError(Service, Other)

    assert conflict.service_type is Service
    assert conflict.strategies == ("implementation_type", "factory")
    assert mismatch.service_type is Service
    assert mismatch.implementation_type is Other
    assert abstract.service_type is Service
    assert abstract.implementation_type is Implementation
    assert instance.service_type is Service
    assert instance.instance_type is Other


def test_resolution_errors_expose_service_and_injection_context() -> None:
    key: Hashable = "primary"
    required = ScopeRequiredError(Service, key)
    missing = ServiceNotRegisteredError(
        Service,
        key=key,
        target=target,
        parameter_name="dependency",
    )
    no_scope = NoActiveScopeError(target)
    missing_annotation = MissingTypeAnnotationError(target, "dependency")
    unsupported = UnsupportedTypeAnnotationError(target, "dependency", list[Service])
    conflicting_key = ConflictingInjectKeyError(
        target, "dependency", ("first", "second")
    )

    assert required.service_type is Service and required.key == key
    assert missing.service_type is Service and missing.key == key
    assert missing.target is target and missing.parameter_name == "dependency"
    assert no_scope.target is target
    assert missing_annotation.parameter_name == "dependency"
    assert unsupported.annotation == list[Service]
    assert conflicting_key.target is target
    assert conflicting_key.parameter_name == "dependency"
    assert conflicting_key.keys == ("first", "second")


def test_service_identifier_and_cycle_are_immutable_and_key_aware() -> None:
    first = ServiceIdentifier(Service, "primary")
    second = ServiceIdentifier(Other)
    error = CircularDependencyError((first, second, first))

    assert str(first) == "Service[key='primary']"
    assert error.chain == (first, second, first)
    assert str(error) == (
        "Circular dependency detected: "
        "Service[key='primary'] -> Other -> Service[key='primary']"
    )

    with pytest.raises(AttributeError):
        first.key = "other"  # pyright: ignore[reportAttributeAccessIssue]
