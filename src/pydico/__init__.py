"""Public package API for pydico."""

from pydico.collection import ServiceCollection
from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import (
    AbstractTypeRegistrationError,
    CircularDependencyError,
    CollectionMaterializationError,
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
    ServiceNotRegisteredError,
    UnsupportedTypeAnnotationError,
)
from pydico.identifiers import ServiceIdentifier
from pydico.injection import inject
from pydico.lifecycle import SupportsClose
from pydico.lifetimes import ServiceLifetime
from pydico.metadata import InjectKey
from pydico.provider import ServiceProvider
from pydico.resolver import ServiceResolver
from pydico.scope import ServiceScope
from pydico.validation import ServiceProviderValidationError, ValidationIssue

__all__ = [
    "AbstractTypeRegistrationError",
    "CircularDependencyError",
    "CollectionMaterializationError",
    "ConflictingInjectKeyError",
    "ConflictingRegistrationError",
    "DisposalError",
    "ImplementationTypeMismatchError",
    "InjectionError",
    "InjectKey",
    "InstanceTypeMismatchError",
    "MissingTypeAnnotationError",
    "NoActiveScopeError",
    "PydicoError",
    "ProviderClosedError",
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
    "ServiceProviderValidationError",
    "ServiceResolver",
    "ServiceScope",
    "SupportsClose",
    "UnsupportedTypeAnnotationError",
    "ValidationIssue",
    "inject",
]
