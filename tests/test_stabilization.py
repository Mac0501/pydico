from __future__ import annotations

from threading import Event, Thread
from time import monotonic, sleep
from typing import cast

import pytest

from pydico import (
    CircularDependencyError,
    CloseDuringResolutionError,
    ScopeRequiredError,
    ServiceCollection,
    ServiceProvider,
    ServiceProviderValidationError,
    ServiceResolver,
    ServiceScope,
    inject,
)

# pyright: reportPrivateUsage=false


class Dependency:
    pass


class Resource:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_provider_close_is_reentrant_during_disposal() -> None:
    closes = 0

    class ReentrantResource:
        def __init__(self, provider: ServiceProvider) -> None:
            self.provider = provider

        def close(self) -> None:
            nonlocal closes
            closes += 1
            self.provider.close()

    provider = (
        ServiceCollection().add_singleton(ReentrantResource).build_service_provider()
    )
    provider.get_service(ReentrantResource)

    provider.close()

    assert closes == 1


def test_resolution_cannot_wait_on_a_concurrent_provider_close() -> None:
    entered = Event()
    proceed = Event()
    close_errors: list[CloseDuringResolutionError] = []
    thread_errors: list[BaseException] = []

    def factory(resolver: ServiceResolver) -> Dependency:
        entered.set()
        assert proceed.wait(timeout=5)
        try:
            cast(ServiceProvider, resolver).close()
        except CloseDuringResolutionError as error:
            close_errors.append(error)
        return Dependency()

    provider = (
        ServiceCollection()
        .add_transient(Dependency, factory=factory)
        .build_service_provider()
    )

    def resolve() -> None:
        try:
            provider.get_service(Dependency)
        except BaseException as error:
            thread_errors.append(error)

    def close() -> None:
        try:
            provider.close()
        except BaseException as error:
            thread_errors.append(error)

    resolving = Thread(target=resolve, daemon=True)
    resolving.start()
    assert entered.wait(timeout=5)
    closing = Thread(target=close, daemon=True)
    closing.start()

    deadline = monotonic() + 5
    while not provider._closing and monotonic() < deadline:
        sleep(0.001)
    assert provider._closing
    proceed.set()

    resolving.join(timeout=5)
    closing.join(timeout=5)
    assert not resolving.is_alive()
    assert not closing.is_alive()
    assert thread_errors == []
    assert len(close_errors) == 1


def test_scope_cannot_close_during_its_own_factory() -> None:
    created: list[Resource] = []

    def factory(resolver: ServiceResolver) -> Resource:
        scope = cast(ServiceScope, resolver)
        with pytest.raises(CloseDuringResolutionError):
            scope.close()
        resource = Resource()
        created.append(resource)
        return resource

    scope = (
        ServiceCollection()
        .add_scoped(Resource, factory=factory)
        .build_service_provider()
        .create_scope()
    )

    assert scope.get_service(Resource) is created[0]
    scope.close()
    assert created[0].closed


def test_singleton_ambient_injection_uses_the_root_provider() -> None:
    class ScopedDependency:
        pass

    class Singleton:
        def __init__(self, dependency: ScopedDependency) -> None:
            self.dependency = dependency

    def resolve_dependency(dependency: object) -> object:
        return dependency

    resolve_dependency.__annotations__["dependency"] = ScopedDependency
    resolve = inject(resolve_dependency)

    provider = (
        ServiceCollection()
        .add_scoped(ScopedDependency)
        .add_singleton(
            Singleton,
            factory=lambda _: Singleton(cast(ScopedDependency, resolve())),
        )
        .build_service_provider()
    )

    with provider.create_scope() as scope:
        with pytest.raises(ScopeRequiredError):
            scope.get_service(Singleton)


def test_explicit_parameter_annotation_is_not_evaluated() -> None:
    def action(explicit: object, dependency: Dependency) -> Dependency:
        return dependency

    action.__annotations__["explicit"] = "UndefinedExplicitType"
    provider = ServiceCollection().add_singleton(Dependency).build_service_provider()
    wrapped = inject(provider)(action)

    assert wrapped(object()) is provider.get_service(Dependency)


def test_build_validation_deduplicates_cycles_and_preserves_entry_path() -> None:
    class Cyclic:
        def __init__(self, first: object, second: object) -> None:
            self.first = first
            self.second = second

    class Root:
        def __init__(self, dependency: Cyclic) -> None:
            self.dependency = dependency

    Cyclic.__init__.__annotations__["first"] = Cyclic
    Cyclic.__init__.__annotations__["second"] = Cyclic
    Root.__init__.__annotations__["dependency"] = Cyclic
    services = ServiceCollection().add_transient(Root).add_transient(Cyclic)

    with pytest.raises(ServiceProviderValidationError) as caught:
        services.build_service_provider(validate=True)

    assert len(caught.value.issues) == 1
    issue = caught.value.issues[0]
    assert isinstance(issue.error, CircularDependencyError)
    assert tuple(identifier.service_type for identifier in issue.path) == (
        Root,
        Cyclic,
        Cyclic,
    )
    assert tuple(identifier.service_type for identifier in issue.error.chain) == (
        Cyclic,
        Cyclic,
    )
