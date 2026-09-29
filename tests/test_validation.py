from __future__ import annotations

from typing import Annotated

import pytest

from pydico import (
    CircularDependencyError,
    InjectionError,
    InjectKey,
    MissingTypeAnnotationError,
    ScopeRequiredError,
    ServiceCollection,
    ServiceNotRegisteredError,
    ServiceProvider,
    ServiceProviderValidationError,
    ServiceResolver,
    ServiceScope,
    UnsupportedTypeAnnotationError,
)


class Dependency:
    pass


class MissingDependency:
    pass


class Consumer:
    def __init__(self, dependency: Dependency) -> None:
        self.dependency = dependency


class KeyedConsumer:
    def __init__(
        self,
        dependency: Annotated[Dependency, InjectKey("primary")],
    ) -> None:
        self.dependency = dependency


class CollectionConsumer:
    def __init__(self, dependencies: list[Dependency]) -> None:
        self.dependencies = dependencies


class MissingConsumer:
    def __init__(self, dependency: MissingDependency) -> None:
        self.dependency = dependency


def test_valid_graph_builds_without_creating_services() -> None:
    creations = 0

    class CountedDependency(Dependency):
        def __init__(self) -> None:
            nonlocal creations
            creations += 1

    provider = (
        ServiceCollection()
        .add_singleton(Dependency, CountedDependency)
        .add_transient(Consumer)
        .add_transient(CollectionConsumer)
        .build_service_provider(validate=True)
    )

    assert creations == 0
    assert isinstance(provider, ServiceProvider)
    assert provider.get_service(Consumer) is not None
    assert creations == 1


def test_validation_aggregates_independent_configuration_errors() -> None:
    class InvalidAnnotations:
        def __init__(self, missing: object, unsupported: dict[str, Dependency]) -> None:
            self.missing = missing
            self.unsupported = unsupported

    del InvalidAnnotations.__init__.__annotations__["missing"]

    services = (
        ServiceCollection()
        .add_transient(MissingConsumer)
        .add_transient(InvalidAnnotations)
    )

    with pytest.raises(ServiceProviderValidationError) as caught:
        services.build_service_provider(validate=True)

    errors = tuple(type(issue.error) for issue in caught.value.issues)
    assert errors == (
        ServiceNotRegisteredError,
        MissingTypeAnnotationError,
        UnsupportedTypeAnnotationError,
    )
    assert "3 issues" in str(caught.value)


def test_missing_dependency_issue_contains_the_complete_path() -> None:
    class Root:
        def __init__(self, consumer: MissingConsumer) -> None:
            self.consumer = consumer

    services = ServiceCollection().add_transient(Root).add_transient(MissingConsumer)

    with pytest.raises(ServiceProviderValidationError) as caught:
        services.build_service_provider(validate=True)

    issue = caught.value.issues[0]
    assert tuple(identifier.service_type for identifier in issue.path) == (
        Root,
        MissingConsumer,
        MissingDependency,
    )
    assert isinstance(issue.error, ServiceNotRegisteredError)


def test_keyed_dependencies_are_validated_with_their_key() -> None:
    valid = (
        ServiceCollection()
        .add_transient(KeyedConsumer)
        .add_transient(Dependency, key="primary")
    )
    assert isinstance(
        valid.build_service_provider(validate=True),
        ServiceProvider,
    )

    with pytest.raises(ServiceProviderValidationError) as caught:
        ServiceCollection().add_transient(KeyedConsumer).build_service_provider(
            validate=True
        )

    issue = caught.value.issues[0]
    assert isinstance(issue.error, ServiceNotRegisteredError)
    assert issue.error.key == "primary"
    assert issue.path[-1].key == "primary"


def test_empty_collection_dependency_is_valid() -> None:
    provider = (
        ServiceCollection()
        .add_transient(CollectionConsumer)
        .build_service_provider(validate=True)
    )

    consumer = provider.get_service(CollectionConsumer)
    assert consumer is not None
    assert consumer.dependencies == []


def test_every_collection_registration_is_validated() -> None:
    class Handler:
        pass

    class Dispatcher:
        def __init__(self, handlers: object) -> None:
            self.handlers = handlers

    class InvalidHandler(Handler):
        def __init__(self, dependency: MissingDependency) -> None:
            self.dependency = dependency

    Dispatcher.__init__.__annotations__["handlers"] = list[Handler]
    services = (
        ServiceCollection()
        .add_transient(Dispatcher)
        .add_transient(Handler, Handler)
        .add_transient(Handler, InvalidHandler)
    )

    with pytest.raises(ServiceProviderValidationError) as caught:
        services.build_service_provider(validate=True)

    issue = caught.value.issues[0]
    assert tuple(identifier.service_type for identifier in issue.path) == (
        Dispatcher,
        Handler,
        MissingDependency,
    )


def test_constructor_cycle_is_detected_without_resolution() -> None:
    class First:
        def __init__(self, second: object) -> None:
            self.second = second

    class Second:
        def __init__(self, first: object) -> None:
            self.first = first

    First.__init__.__annotations__["second"] = Second
    Second.__init__.__annotations__["first"] = First
    services = ServiceCollection().add_transient(First).add_transient(Second)

    with pytest.raises(ServiceProviderValidationError) as caught:
        services.build_service_provider(validate=True)

    issue = caught.value.issues[0]
    assert isinstance(issue.error, CircularDependencyError)
    assert tuple(identifier.service_type for identifier in issue.path) == (
        First,
        Second,
        First,
    )


def test_collection_cycle_is_detected() -> None:
    class Handler:
        pass

    class CompositeHandler(Handler):
        def __init__(self, handlers: object) -> None:
            self.handlers = handlers

    CompositeHandler.__init__.__annotations__["handlers"] = list[Handler]
    services = ServiceCollection().add_transient(Handler, CompositeHandler)

    with pytest.raises(ServiceProviderValidationError) as caught:
        services.build_service_provider(validate=True)

    assert isinstance(caught.value.issues[0].error, CircularDependencyError)


def test_factory_is_an_opaque_leaf_and_is_not_executed() -> None:
    calls = 0

    def factory(_: ServiceResolver) -> Dependency:
        nonlocal calls
        calls += 1
        raise AssertionError("factory must not run during validation")

    provider = (
        ServiceCollection()
        .add_transient(Dependency, factory=factory)
        .add_transient(Consumer)
        .build_service_provider(validate=True)
    )

    assert isinstance(provider, ServiceProvider)
    assert calls == 0


def test_prebuilt_instance_is_an_opaque_leaf() -> None:
    instance = Dependency()
    provider = (
        ServiceCollection()
        .add_instance(Dependency, instance)
        .add_transient(Consumer)
        .build_service_provider(validate=True)
    )

    assert provider.get_service(Consumer) is not None


def test_default_build_remains_lazy() -> None:
    provider = (
        ServiceCollection().add_transient(MissingConsumer).build_service_provider()
    )

    with pytest.raises(ServiceNotRegisteredError):
        provider.get_service(MissingConsumer)


def test_validate_false_remains_lazy() -> None:
    provider = (
        ServiceCollection()
        .add_transient(MissingConsumer)
        .build_service_provider(validate=False)
    )

    with pytest.raises(ServiceNotRegisteredError):
        provider.get_service(MissingConsumer)


def test_unresolvable_forward_reference_preserves_its_cause() -> None:
    class InvalidForwardReference:
        def __init__(self, dependency: object) -> None:
            self.dependency = dependency

    InvalidForwardReference.__init__.__annotations__["dependency"] = (
        "UndefinedDependency"
    )

    with pytest.raises(ServiceProviderValidationError) as caught:
        (
            ServiceCollection()
            .add_transient(InvalidForwardReference)
            .build_service_provider(validate=True)
        )

    error = caught.value.issues[0].error
    assert type(error) is InjectionError
    assert isinstance(error.__cause__, NameError)


def test_builtin_resolver_types_are_statically_available() -> None:
    class BuiltinConsumer:
        def __init__(
            self,
            provider: ServiceProvider,
            resolver: ServiceResolver,
            scope: ServiceScope,
        ) -> None:
            self.provider = provider
            self.resolver = resolver
            self.scope = scope

    provider = (
        ServiceCollection()
        .add_transient(BuiltinConsumer)
        .build_service_provider(validate=True)
    )

    assert isinstance(provider, ServiceProvider)


def test_scope_compatibility_remains_a_runtime_rule() -> None:
    class Database:
        pass

    class Repository:
        def __init__(self, database: Database) -> None:
            self.database = database

    Repository.__init__.__annotations__["database"] = Database

    provider = (
        ServiceCollection()
        .add_scoped(Database)
        .add_singleton(Repository)
        .build_service_provider(validate=True)
    )

    with pytest.raises(ScopeRequiredError):
        provider.get_service(Repository)
