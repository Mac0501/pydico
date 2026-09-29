from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

from pydico.collection import ServiceCollection
from pydico.exceptions import (
    CircularDependencyError,
    ScopeClosedError,
    ScopeRequiredError,
)
from pydico.provider import ServiceProvider
from pydico.resolver import ServiceResolver
from pydico.scope import ServiceScope


class Dependency:
    pass


class Consumer:
    def __init__(
        self,
        dependency: Dependency,
        resolver: ServiceResolver,
        provider: ServiceProvider,
        scope: ServiceScope,
    ) -> None:
        self.dependency = dependency
        self.resolver = resolver
        self.provider = provider
        self.scope = scope


def test_scope_isolation_and_constructor_context() -> None:
    provider = (
        ServiceCollection()
        .add_scoped(Dependency)
        .add_transient(Consumer)
        .build_service_provider()
    )
    with provider.create_scope() as first, provider.create_scope() as second:
        a = first.get_service(Consumer)
        b = first.get_service(Consumer)
        c = second.get_service(Consumer)
        assert a is not None and b is not None and c is not None
        assert a is not b
        assert a.dependency is b.dependency
        assert a.dependency is not c.dependency
        assert a.resolver is first and a.scope is first and a.provider is provider
        assert first.get_service(ServiceResolver) is first
        assert first.get_service(ServiceScope, key="custom") is None
    assert provider.get_service(ServiceResolver) is provider
    assert provider.get_service(ServiceScope) is None


def test_keys_and_multiple_registrations_have_independent_caches() -> None:
    provider = (
        ServiceCollection()
        .add_scoped(Dependency)
        .add_scoped(Dependency)
        .add_scoped(Dependency, key="key")
        .build_service_provider()
    )
    with provider.create_scope() as scope:
        values = scope.get_services(Dependency)
        assert len(values) == 2 and values[0] is not values[1]
        assert scope.get_services(Dependency) == values
        assert scope.get_service(Dependency) is values[-1]
        assert scope.get_service(Dependency, key="key") not in values
        assert scope.get_services(str) == ()
        assert scope.get_service(str) is None
    with pytest.raises(ScopeRequiredError):
        provider.get_services(Dependency)


def test_singletons_receive_root_and_are_shared_across_scopes() -> None:
    seen: list[ServiceResolver] = []

    def factory(resolver: ServiceResolver) -> Dependency:
        seen.append(resolver)
        return Dependency()

    provider = (
        ServiceCollection()
        .add_singleton(Dependency, factory=factory)
        .build_service_provider()
    )
    with provider.create_scope() as first, provider.create_scope() as second:
        assert (
            first.get_service(Dependency)
            is second.get_service(Dependency)
            is provider.get_service(Dependency)
        )
    assert seen == [provider]


@pytest.mark.parametrize("indirect", [False, True])
def test_singleton_cannot_capture_scoped_service(indirect: bool) -> None:
    services = ServiceCollection().add_scoped(Dependency)
    services.add_transient(Consumer)

    def factory(resolver: ServiceResolver) -> str:
        resolver.get_service(Consumer if indirect else Dependency)
        return "invalid"

    provider = services.add_singleton(str, factory=factory).build_service_provider()
    with provider.create_scope() as scope, pytest.raises(ScopeRequiredError):
        scope.get_service(str)


def test_failed_factory_can_retry_and_receives_scope() -> None:
    seen: list[ServiceResolver] = []

    def factory(resolver: ServiceResolver) -> Dependency:
        seen.append(resolver)
        if len(seen) == 1:
            raise ValueError("failure")
        return Dependency()

    provider = (
        ServiceCollection()
        .add_scoped(Dependency, factory=factory)
        .build_service_provider()
    )
    with provider.create_scope() as scope:
        with pytest.raises(ValueError):
            scope.get_service(Dependency)
        assert scope.get_service(Dependency) is scope.get_service(Dependency)
        assert seen == [scope, scope]


def test_scoped_cycles_are_detected_and_stack_is_cleaned() -> None:
    def factory(resolver: ServiceResolver) -> Dependency:
        resolver.get_service(Dependency)
        return Dependency()

    provider = (
        ServiceCollection()
        .add_scoped(Dependency, factory=factory)
        .add_transient(str)
        .build_service_provider()
    )
    with provider.create_scope() as scope:
        for _ in range(2):
            with pytest.raises(CircularDependencyError):
                scope.get_service(Dependency)
        assert scope.get_service(str) == ""


def test_context_exception_closes_scope_and_close_is_idempotent() -> None:
    provider = ServiceCollection().build_service_provider()
    scope = provider.create_scope()
    with pytest.raises(ValueError):
        with scope:
            raise ValueError("body")
    scope.close()
    with pytest.raises(ScopeClosedError):
        scope.get_service(ServiceProvider)
    with pytest.raises(ScopeClosedError):
        scope.get_services(str)
    with pytest.raises(ScopeClosedError):
        scope.__enter__()
    with provider.create_scope() as other:
        assert other.get_service(ServiceProvider) is provider


def test_concurrent_resolution_creates_one_scoped_instance() -> None:
    calls: list[ServiceResolver] = []

    def factory(resolver: ServiceResolver) -> Dependency:
        calls.append(resolver)
        return Dependency()

    provider = (
        ServiceCollection()
        .add_scoped(Dependency, factory=factory)
        .build_service_provider()
    )
    start = Barrier(8)
    with provider.create_scope() as scope:

        def resolve() -> Dependency | None:
            start.wait(timeout=5)
            return scope.get_service(Dependency)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(resolve) for _ in range(8)]
            values = [future.result(timeout=5) for future in futures]
        assert len({id(value) for value in values}) == 1
        assert calls == [scope]


def test_separate_scopes_can_construct_in_parallel() -> None:
    entered = Barrier(2)

    def factory(_: ServiceResolver) -> Dependency:
        entered.wait(timeout=5)
        return Dependency()

    provider = (
        ServiceCollection()
        .add_scoped(Dependency, factory=factory)
        .build_service_provider()
    )
    with provider.create_scope() as first, provider.create_scope() as second:
        with ThreadPoolExecutor(max_workers=2) as executor:
            a = executor.submit(first.get_service, Dependency)
            b = executor.submit(second.get_service, Dependency)
            assert a.result(timeout=5) is not b.result(timeout=5)


def test_close_waits_for_in_flight_resolution() -> None:
    entered, release, closing = Event(), Event(), Event()

    def factory(_: ServiceResolver) -> Dependency:
        entered.set()
        assert release.wait(timeout=5)
        return Dependency()

    scope = (
        ServiceCollection()
        .add_scoped(Dependency, factory=factory)
        .build_service_provider()
        .create_scope()
    )

    def close() -> None:
        closing.set()
        scope.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        resolving = executor.submit(scope.get_service, Dependency)
        assert entered.wait(timeout=5)
        closed = executor.submit(close)
        try:
            assert closing.wait(timeout=5)
            assert not closed.done()
        finally:
            release.set()
        assert isinstance(resolving.result(timeout=5), Dependency)
        closed.result(timeout=5)
    with pytest.raises(ScopeClosedError):
        scope.get_service(Dependency)
