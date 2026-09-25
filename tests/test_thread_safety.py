from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from typing import Callable, TypeVar, cast

import pytest

from pydico.collection import ServiceCollection
from pydico.exceptions import CircularDependencyError
from pydico.provider import ServiceProvider

T = TypeVar("T")


class Service:
    pass


class OtherService:
    pass


class ConstructorA:
    def __init__(self, dependency: ConstructorB) -> None:
        self.dependency = dependency


class ConstructorB:
    def __init__(self, dependency: ConstructorA) -> None:
        self.dependency = dependency


def run_concurrently(worker: Callable[[], T], count: int) -> list[T]:
    start = Barrier(count)

    def run() -> T:
        start.wait(timeout=5)
        return worker()

    with ThreadPoolExecutor(max_workers=count) as executor:
        futures = [executor.submit(run) for _ in range(count)]
        return [future.result(timeout=5) for future in futures]


def test_singleton_is_constructed_once_for_concurrent_resolutions() -> None:
    calls = 0
    calls_lock = Lock()

    def factory(_: ServiceProvider) -> Service:
        nonlocal calls
        with calls_lock:
            calls += 1
        return Service()

    provider = (
        ServiceCollection()
        .add_singleton(Service, factory=factory)
        .build_service_provider()
    )

    services = run_concurrently(lambda: provider.get_service(Service), 8)

    assert len({id(service) for service in services}) == 1
    assert calls == 1


def test_get_services_uses_singleton_cache_under_concurrency() -> None:
    calls: list[str] = []
    calls_lock = Lock()

    def factory(name: str) -> Callable[[ServiceProvider], Service]:
        def create(_: ServiceProvider) -> Service:
            with calls_lock:
                calls.append(name)
            return Service()

        return create

    provider = (
        ServiceCollection()
        .add_singleton(Service, factory=factory("first"))
        .add_singleton(Service, factory=factory("second"))
        .build_service_provider()
    )

    service_sets = run_concurrently(lambda: provider.get_services(Service), 8)

    assert all(len(services) == 2 for services in service_sets)
    assert all(services == service_sets[0] for services in service_sets)
    assert sorted(calls) == ["first", "second"]


def test_nested_singleton_factories_can_resolve_other_singletons() -> None:
    class Outer:
        def __init__(self, inner: Service) -> None:
            self.inner = inner

    def create_outer(service_provider: ServiceProvider) -> Outer:
        inner = service_provider.get_service(Service)
        assert inner is not None
        return Outer(inner)

    provider = (
        ServiceCollection()
        .add_singleton(Service)
        .add_singleton(Outer, factory=create_outer)
        .build_service_provider()
    )

    outer = provider.get_service(Outer)
    assert outer is not None
    assert outer.inner is provider.get_service(Service)


def test_transient_factories_can_run_in_parallel() -> None:
    entered = Barrier(2)

    def factory(_: ServiceProvider) -> Service:
        entered.wait(timeout=5)
        return Service()

    provider = (
        ServiceCollection()
        .add_transient(Service, factory=factory)
        .build_service_provider()
    )

    first, second = run_concurrently(lambda: provider.get_service(Service), 2)

    assert first is not second


def test_independent_providers_do_not_share_singleton_locks_or_instances() -> None:
    entered = Barrier(2)

    def factory(_: ServiceProvider) -> Service:
        entered.wait(timeout=5)
        return Service()

    collection = ServiceCollection().add_singleton(Service, factory=factory)
    first_provider = collection.build_service_provider()
    second_provider = collection.build_service_provider()

    start = Barrier(2)

    def resolve(provider: ServiceProvider) -> Service | None:
        start.wait(timeout=5)
        return provider.get_service(Service)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(resolve, first_provider)
        second_future = executor.submit(resolve, second_provider)
        first = first_future.result(timeout=5)
        second = second_future.result(timeout=5)

    assert first is not second


def test_singleton_factory_failure_is_not_cached_and_stack_is_cleaned() -> None:
    calls = 0

    def factory(_: ServiceProvider) -> Service:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("boom")
        return Service()

    provider = (
        ServiceCollection()
        .add_singleton(Service, factory=factory)
        .build_service_provider()
    )

    with pytest.raises(ValueError, match="boom"):
        provider.get_service(Service)

    assert isinstance(provider.get_service(Service), Service)
    assert calls == 2


def test_provider_uses_collection_snapshot() -> None:
    collection = ServiceCollection().add_singleton(Service)
    first_provider = collection.build_service_provider()

    collection.add_singleton(OtherService)
    second_provider = collection.build_service_provider()

    assert isinstance(first_provider.get_service(Service), Service)
    assert first_provider.get_service(OtherService) is None
    assert isinstance(second_provider.get_service(OtherService), OtherService)


def test_circular_dependency_in_factories_raises_clear_error() -> None:
    provider = (
        ServiceCollection()
        .add_transient(
            Service,
            factory=lambda service_provider: cast(
                Service, service_provider.get_service(OtherService)
            ),
        )
        .add_transient(
            OtherService,
            factory=lambda service_provider: cast(
                OtherService, service_provider.get_service(Service)
            ),
        )
        .build_service_provider()
    )

    with pytest.raises(CircularDependencyError) as error:
        provider.get_service(Service)

    assert [descriptor.service_type for descriptor in error.value.chain] == [
        Service,
        OtherService,
        Service,
    ]


def test_circular_dependency_detection_distinguishes_keys() -> None:
    provider = (
        ServiceCollection()
        .add_transient(
            Service,
            factory=lambda service_provider: cast(
                Service, service_provider.get_service(OtherService, key="b")
            ),
            key="a",
        )
        .add_transient(
            OtherService,
            factory=lambda service_provider: cast(
                OtherService, service_provider.get_service(Service, key="a")
            ),
            key="b",
        )
        .build_service_provider()
    )

    with pytest.raises(CircularDependencyError, match="key='a'"):
        provider.get_service(Service, key="a")


def test_circular_dependency_in_constructors_raises_clear_error() -> None:
    provider = (
        ServiceCollection()
        .add_transient(ConstructorA)
        .add_transient(ConstructorB)
        .build_service_provider()
    )

    with pytest.raises(CircularDependencyError) as error:
        provider.get_service(ConstructorA)

    assert [descriptor.service_type for descriptor in error.value.chain] == [
        ConstructorA,
        ConstructorB,
        ConstructorA,
    ]


def test_resolution_stack_is_thread_local() -> None:
    entered = Barrier(2)

    def factory(_: ServiceProvider) -> Service:
        entered.wait(timeout=5)
        return Service()

    provider = (
        ServiceCollection()
        .add_transient(Service, factory=factory)
        .build_service_provider()
    )

    first, second = run_concurrently(lambda: provider.get_service(Service), 2)

    assert isinstance(first, Service)
    assert isinstance(second, Service)
    assert first is not second
