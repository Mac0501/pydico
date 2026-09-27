"""Public package API for pydico."""

from pydico.collection import ServiceCollection
from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import (
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
)
from pydico.identifiers import ServiceIdentifier
from pydico.injection import inject
from pydico.lifetimes import ServiceLifetime
from pydico.provider import ServiceProvider
from pydico.resolver import ServiceResolver
from pydico.scope import ServiceScope

__all__ = [
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
]
