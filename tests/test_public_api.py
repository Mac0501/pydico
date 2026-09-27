import pydico
from pydico import (
    CircularDependencyError,
    InjectionError,
    ScopeClosedError,
    ScopedResolutionError,
    ServiceCollection,
    ServiceDescriptor,
    ServiceLifetime,
    ServiceProvider,
    ServiceResolver,
    ServiceScope,
    inject,
)
from pydico.collection import ServiceCollection as InternalServiceCollection
from pydico.descriptors import ServiceDescriptor as InternalServiceDescriptor
from pydico.exceptions import CircularDependencyError as InternalCircularDependencyError
from pydico.exceptions import InjectionError as InternalInjectionError
from pydico.exceptions import ScopeClosedError as InternalScopeClosedError
from pydico.exceptions import ScopedResolutionError as InternalScopedResolutionError
from pydico.injection import inject as internal_inject
from pydico.lifetimes import ServiceLifetime as InternalServiceLifetime
from pydico.provider import ServiceProvider as InternalServiceProvider
from pydico.resolver import ServiceResolver as InternalServiceResolver
from pydico.scope import ServiceScope as InternalServiceScope


def test_public_api_exports_are_explicit_and_complete() -> None:
    expected = {
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
    }

    assert set(pydico.__all__) == expected
    assert {name for name in expected if getattr(pydico, name, None) is None} == set()


def test_public_symbols_reference_the_implemented_types() -> None:
    assert ServiceCollection is InternalServiceCollection
    assert ServiceDescriptor is InternalServiceDescriptor
    assert ServiceLifetime is InternalServiceLifetime
    assert ServiceProvider is InternalServiceProvider
    assert ServiceResolver is InternalServiceResolver
    assert ServiceScope is InternalServiceScope
    assert CircularDependencyError is InternalCircularDependencyError
    assert InjectionError is InternalInjectionError
    assert ScopeClosedError is InternalScopeClosedError
    assert ScopedResolutionError is InternalScopedResolutionError
    assert inject is internal_inject
