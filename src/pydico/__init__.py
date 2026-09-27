"""Public package API for pydico."""

from pydico.collection import ServiceCollection
from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import (
    CircularDependencyError,
    InjectionError,
    ScopeClosedError,
    ScopedResolutionError,
)
from pydico.injection import inject
from pydico.lifetimes import ServiceLifetime
from pydico.provider import ServiceProvider
from pydico.resolver import ServiceResolver
from pydico.scope import ServiceScope

__all__ = [
    "CircularDependencyError",
    "InjectionError",
    "ScopeClosedError",
    "ScopedResolutionError",
    "ServiceCollection",
    "ServiceDescriptor",
    "ServiceLifetime",
    "ServiceProvider",
    "ServiceResolver",
    "ServiceScope",
    "inject",
]
