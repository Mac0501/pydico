from __future__ import annotations

import pytest

from pydico.collection import ServiceCollection
from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import ScopedResolutionError
from pydico.lifetimes import ServiceLifetime
from pydico.provider import ServiceProvider
from pydico.resolver import ServiceResolver

# pyright: reportMissingParameterType=false, reportUnknownParameterType=false


class Service:
    pass


class FirstService(Service):
    pass


class SecondService(Service):
    pass


class Dependency:
    pass


class MissingDependency:
    pass


class Consumer:
    def __init__(self, dependency: Dependency) -> None:
        self.dependency = dependency


class ConsumerWithDefault:
    def __init__(self, dependency: MissingDependency | None = None) -> None:
        self.dependency = dependency


class ConsumerWithVariadicParameters:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs


class ConsumerWithMissingAnnotation:
    def __init__(self, dependency) -> None:
        self.dependency = dependency


class ConsumerWithUnsupportedAnnotation:
    def __init__(self, dependency: list[Dependency]) -> None:
        self.dependency = dependency


class ConsumerWithUnregisteredDependency:
    def __init__(self, dependency: MissingDependency) -> None:
        self.dependency = dependency


class ConsumerWithProviderDependency:
    def __init__(self, provider: ServiceProvider) -> None:
        self.provider = provider


def test_get_service_returns_none_when_no_registration_matches() -> None:
    provider = ServiceCollection().build_service_provider()

    assert provider.get_service(Service) is None
    assert provider.get_services(Service) == ()


def test_get_service_can_resolve_provider_itself() -> None:
    provider = ServiceCollection().build_service_provider()

    assert provider.get_service(ServiceProvider) is provider
    assert provider.get_service(ServiceResolver) is provider
    assert provider.get_services(ServiceProvider) == ()
    assert provider.get_services(ServiceResolver) == ()


def test_provider_self_resolution_does_not_match_keys() -> None:
    provider = ServiceCollection().build_service_provider()

    assert provider.get_service(ServiceProvider, key="custom") is None


def test_transient_resolution_creates_new_instance_each_time() -> None:
    provider = ServiceCollection().add_transient(Service).build_service_provider()

    first = provider.get_service(Service)
    second = provider.get_service(Service)

    assert isinstance(first, Service)
    assert isinstance(second, Service)
    assert first is not second


def test_singleton_resolution_reuses_instance_within_provider() -> None:
    provider = ServiceCollection().add_singleton(Service).build_service_provider()

    first = provider.get_service(Service)
    second = provider.get_service(Service)

    assert isinstance(first, Service)
    assert first is second


def test_singleton_cache_is_per_provider_snapshot() -> None:
    collection = ServiceCollection().add_singleton(Service)
    first_provider = collection.build_service_provider()
    second_provider = collection.build_service_provider()

    assert first_provider.get_service(Service) is not second_provider.get_service(
        Service
    )


def test_get_service_returns_last_matching_registration() -> None:
    provider = (
        ServiceCollection()
        .add_transient(Service, FirstService)
        .add_transient(Service, SecondService)
        .build_service_provider()
    )

    assert isinstance(provider.get_service(Service), SecondService)


def test_get_services_returns_all_matching_registrations_in_order() -> None:
    provider = (
        ServiceCollection()
        .add_transient(Service, FirstService)
        .add_transient(Service, SecondService)
        .build_service_provider()
    )

    services = provider.get_services(Service)

    assert len(services) == 2
    assert isinstance(services[0], FirstService)
    assert isinstance(services[1], SecondService)


def test_keyed_resolution_filters_registrations_by_key() -> None:
    provider = (
        ServiceCollection()
        .add_singleton(Service, FirstService, key="first")
        .add_singleton(Service, SecondService, key="second")
        .build_service_provider()
    )

    assert provider.get_service(Service) is None
    assert isinstance(provider.get_service(Service, key="first"), FirstService)
    assert isinstance(provider.get_service(Service, key="second"), SecondService)


def test_keyed_get_services_returns_only_matching_key() -> None:
    provider = (
        ServiceCollection()
        .add_transient(Service, FirstService, key="selected")
        .add_transient(Service, SecondService, key="selected")
        .add_transient(Service, Service, key="other")
        .build_service_provider()
    )

    services = provider.get_services(Service, key="selected")

    assert len(services) == 2
    assert isinstance(services[0], FirstService)
    assert isinstance(services[1], SecondService)


def test_factory_receives_provider_and_can_resolve_dependencies() -> None:
    def create_consumer(provider: ServiceResolver) -> Consumer:
        dependency = provider.get_service(Dependency)
        assert dependency is not None
        return Consumer(dependency)

    provider = (
        ServiceCollection()
        .add_singleton(Dependency)
        .add_transient(Consumer, factory=create_consumer)
        .build_service_provider()
    )

    consumer = provider.get_service(Consumer)
    assert consumer is not None
    assert consumer.dependency is provider.get_service(Dependency)


def test_constructor_injection_resolves_required_annotated_parameters() -> None:
    provider = (
        ServiceCollection()
        .add_singleton(Dependency)
        .add_transient(Consumer)
        .build_service_provider()
    )

    consumer = provider.get_service(Consumer)

    assert consumer is not None
    assert consumer.dependency is provider.get_service(Dependency)


def test_constructor_injection_can_resolve_provider_itself() -> None:
    provider = (
        ServiceCollection()
        .add_transient(ConsumerWithProviderDependency)
        .build_service_provider()
    )

    consumer = provider.get_service(ConsumerWithProviderDependency)

    assert consumer is not None
    assert consumer.provider is provider


def test_constructor_injection_leaves_default_parameters_untouched() -> None:
    provider = (
        ServiceCollection().add_transient(ConsumerWithDefault).build_service_provider()
    )

    consumer = provider.get_service(ConsumerWithDefault)

    assert consumer is not None
    assert consumer.dependency is None


def test_constructor_injection_ignores_variadic_parameters() -> None:
    provider = (
        ServiceCollection()
        .add_transient(ConsumerWithVariadicParameters)
        .build_service_provider()
    )

    consumer = provider.get_service(ConsumerWithVariadicParameters)
    assert consumer is not None
    assert consumer.args == ()
    assert consumer.kwargs == {}


def test_missing_constructor_annotation_raises_type_error() -> None:
    provider = (
        ServiceCollection()
        .add_transient(ConsumerWithMissingAnnotation)
        .build_service_provider()
    )

    with pytest.raises(TypeError, match="missing type annotation"):
        provider.get_service(ConsumerWithMissingAnnotation)


def test_unsupported_constructor_annotation_raises_type_error() -> None:
    provider = (
        ServiceCollection()
        .add_transient(ConsumerWithUnsupportedAnnotation)
        .build_service_provider()
    )

    with pytest.raises(TypeError, match="annotation must be a type"):
        provider.get_service(ConsumerWithUnsupportedAnnotation)


def test_unregistered_constructor_dependency_raises_lookup_error() -> None:
    provider = (
        ServiceCollection()
        .add_transient(ConsumerWithUnregisteredDependency)
        .build_service_provider()
    )

    with pytest.raises(LookupError, match="No service registered"):
        provider.get_service(ConsumerWithUnregisteredDependency)


def test_scoped_lifetime_requires_scope() -> None:
    descriptor: ServiceDescriptor[object] = ServiceDescriptor(
        service_type=Service,
        lifetime=ServiceLifetime.SCOPED,
        implementation_type=Service,
    )
    provider = ServiceProvider((descriptor,))

    with pytest.raises(ScopedResolutionError, match="requires an active scope"):
        provider.get_service(Service)
