import pydico
import pydico.collection as collection_module
import pydico.descriptors as descriptors_module
import pydico.exceptions as exceptions_module
import pydico.identifiers as identifiers_module
import pydico.injection as injection_module
import pydico.lifetimes as lifetimes_module
import pydico.provider as provider_module
import pydico.resolver as resolver_module
import pydico.scope as scope_module
from pydico import (
    AbstractTypeRegistrationError,
    CircularDependencyError,
    ConflictingRegistrationError,
    ImplementationTypeMismatchError,
    InjectionError,
    InstanceTypeMismatchError,
    MissingTypeAnnotationError,
    NoActiveScopeError,
    PydicoError,
    RegistrationError,
    ResolutionError,
    ScopeClosedError,
    ScopeRequiredError,
    ServiceCollection,
    ServiceDescriptor,
    ServiceIdentifier,
    ServiceLifetime,
    ServiceNotRegisteredError,
    ServiceProvider,
    ServiceResolver,
    ServiceScope,
    UnsupportedTypeAnnotationError,
    inject,
)


def test_public_api_exports_are_explicit_and_complete() -> None:
    expected = {
        "AbstractTypeRegistrationError",
        "CircularDependencyError",
        "ConflictingRegistrationError",
        "ImplementationTypeMismatchError",
        "InjectionError",
        "InstanceTypeMismatchError",
        "MissingTypeAnnotationError",
        "NoActiveScopeError",
        "PydicoError",
        "RegistrationError",
        "ResolutionError",
        "ScopeClosedError",
        "ScopeRequiredError",
        "ServiceCollection",
        "ServiceDescriptor",
        "ServiceIdentifier",
        "ServiceLifetime",
        "ServiceNotRegisteredError",
        "ServiceProvider",
        "ServiceResolver",
        "ServiceScope",
        "UnsupportedTypeAnnotationError",
        "inject",
    }

    assert set(pydico.__all__) == expected
    assert {name for name in expected if getattr(pydico, name, None) is None} == set()


def test_public_symbols_reference_the_implemented_types() -> None:
    assert ServiceCollection is collection_module.ServiceCollection
    assert ServiceDescriptor is descriptors_module.ServiceDescriptor
    assert ServiceIdentifier is identifiers_module.ServiceIdentifier
    assert ServiceLifetime is lifetimes_module.ServiceLifetime
    assert ServiceProvider is provider_module.ServiceProvider
    assert ServiceResolver is resolver_module.ServiceResolver
    assert ServiceScope is scope_module.ServiceScope
    assert inject is injection_module.inject

    error_types = {
        AbstractTypeRegistrationError,
        CircularDependencyError,
        ConflictingRegistrationError,
        ImplementationTypeMismatchError,
        InjectionError,
        InstanceTypeMismatchError,
        MissingTypeAnnotationError,
        NoActiveScopeError,
        PydicoError,
        RegistrationError,
        ResolutionError,
        ScopeClosedError,
        ScopeRequiredError,
        ServiceNotRegisteredError,
        UnsupportedTypeAnnotationError,
    }
    assert all(
        error_type is getattr(exceptions_module, error_type.__name__)
        for error_type in error_types
    )
