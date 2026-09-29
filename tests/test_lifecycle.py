from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from pydico import (
    DisposalError,
    ProviderClosedError,
    ServiceCollection,
    ServiceResolver,
    SupportsClose,
)


class Dependency:
    events: list[str] = []

    def close(self) -> None:
        self.events.append("dependency")


class Consumer:
    events: list[str] = []

    def __init__(self, dependency: Dependency) -> None:
        self.dependency = dependency

    def close(self) -> None:
        self.events.append("consumer")


class TransientResource:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class ExternalResource:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_supports_close_is_a_structural_runtime_protocol() -> None:
    assert isinstance(Dependency(), SupportsClose)
    assert not isinstance(object(), SupportsClose)


def test_scope_closes_owned_services_once_in_reverse_creation_order() -> None:
    events: list[str] = []
    Dependency.events = events
    Consumer.events = events
    provider = (
        ServiceCollection()
        .add_scoped(Dependency)
        .add_scoped(Consumer)
        .build_service_provider()
    )
    scope = provider.create_scope()

    with scope:
        consumer = scope.get_service(Consumer)
        assert consumer is not None
        assert consumer.dependency is scope.get_service(Dependency)

    scope.close()
    assert events == ["consumer", "dependency"]


def test_provider_closes_owned_singletons_in_reverse_creation_order() -> None:
    events: list[str] = []
    Dependency.events = events
    Consumer.events = events
    provider = (
        ServiceCollection()
        .add_singleton(Dependency)
        .add_singleton(Consumer)
        .build_service_provider()
    )

    with provider:
        consumer = provider.get_service(Consumer)
        assert consumer is not None
        assert consumer.dependency is provider.get_service(Dependency)

    provider.close()
    assert events == ["consumer", "dependency"]


def test_transient_and_external_instances_are_not_container_owned() -> None:
    external = ExternalResource()
    provider = (
        ServiceCollection()
        .add_transient(TransientResource)
        .add_instance(ExternalResource, external)
        .build_service_provider()
    )

    transient = provider.get_service(TransientResource)
    assert transient is not None
    assert provider.get_service(ExternalResource) is external
    provider.close()

    assert not transient.closed
    assert not external.closed


def test_factory_results_are_owned_and_duplicate_instances_close_once() -> None:
    shared = Dependency()
    events: list[str] = []
    Dependency.events = events
    provider = (
        ServiceCollection()
        .add_singleton(Dependency, factory=lambda _: shared, key="first")
        .add_singleton(Dependency, factory=lambda _: shared, key="second")
        .build_service_provider()
    )

    provider.get_service(Dependency, key="first")
    provider.get_service(Dependency, key="second")
    provider.close()

    assert events == ["dependency"]


def test_disposal_continues_after_errors_and_scope_stays_closed() -> None:
    events: list[str] = []

    class First:
        def close(self) -> None:
            events.append("first")
            raise ValueError("first failure")

    class Second:
        def close(self) -> None:
            events.append("second")
            raise RuntimeError("second failure")

    scope = (
        ServiceCollection()
        .add_scoped(First)
        .add_scoped(Second)
        .build_service_provider()
        .create_scope()
    )
    scope.get_service(First)
    scope.get_service(Second)

    with pytest.raises(DisposalError) as caught:
        scope.close()

    assert events == ["second", "first"]
    assert [str(error) for error in caught.value.errors] == [
        "second failure",
        "first failure",
    ]
    scope.close()


def test_closed_provider_rejects_resolution_and_scope_creation() -> None:
    provider = ServiceCollection().add_singleton(Dependency).build_service_provider()
    scope = provider.create_scope()
    provider.close()

    operations = (
        lambda: provider.get_service(Dependency),
        lambda: provider.get_services(Dependency),
        provider.create_scope,
        lambda: scope.get_service(Dependency),
    )
    for operation in operations:
        with pytest.raises(ProviderClosedError):
            operation()
    scope.close()


def test_provider_close_waits_for_in_flight_resolution() -> None:
    entered, release, closing = Event(), Event(), Event()

    def factory(_: ServiceResolver) -> TransientResource:
        entered.set()
        assert release.wait(timeout=5)
        return TransientResource()

    provider = (
        ServiceCollection()
        .add_transient(TransientResource, factory=factory)
        .build_service_provider()
    )

    def close() -> None:
        closing.set()
        provider.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        resolving = executor.submit(provider.get_service, TransientResource)
        assert entered.wait(timeout=5)
        closed = executor.submit(close)
        try:
            assert closing.wait(timeout=5)
            assert not closed.done()
        finally:
            release.set()
        assert isinstance(resolving.result(timeout=5), TransientResource)
        closed.result(timeout=5)

    with pytest.raises(ProviderClosedError):
        provider.get_service(TransientResource)
