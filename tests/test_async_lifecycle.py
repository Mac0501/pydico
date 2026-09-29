from __future__ import annotations

import asyncio
from threading import Event

import pytest

from pydico import (
    AsyncDisposalRequiredError,
    DisposalError,
    InjectionError,
    ProviderClosedError,
    ScopeClosedError,
    ServiceCollection,
    ServiceProvider,
    SupportsAsyncClose,
    inject,
)

# pyright: reportPrivateUsage=false


class AsyncResource:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        await asyncio.sleep(0)
        self.closed = True


def test_supports_async_close_is_a_structural_runtime_protocol() -> None:
    assert isinstance(AsyncResource(), SupportsAsyncClose)
    assert not isinstance(object(), SupportsAsyncClose)


def test_async_scope_closes_mixed_resources_in_reverse_creation_order() -> None:
    events: list[str] = []

    class SyncDependency:
        def close(self) -> None:
            events.append("sync")

    class AsyncConsumer:
        def __init__(self, dependency: SyncDependency) -> None:
            self.dependency = dependency

        async def aclose(self) -> None:
            await asyncio.sleep(0)
            events.append("async")

    AsyncConsumer.__init__.__annotations__["dependency"] = SyncDependency

    async def run() -> None:
        provider = (
            ServiceCollection()
            .add_scoped(SyncDependency)
            .add_scoped(AsyncConsumer)
            .build_service_provider()
        )
        scope = provider.create_scope()
        consumer = scope.get_service(AsyncConsumer)
        assert consumer is not None
        assert consumer.dependency is scope.get_service(SyncDependency)

        await scope.aclose()
        await scope.aclose()
        provider.close()

    asyncio.run(run())
    assert events == ["async", "sync"]


def test_async_disposal_prefers_aclose_when_service_supports_both() -> None:
    events: list[str] = []

    class DualResource:
        def close(self) -> None:
            events.append("close")

        async def aclose(self) -> None:
            events.append("aclose")

    async def run() -> None:
        provider = (
            ServiceCollection().add_singleton(DualResource).build_service_provider()
        )
        provider.get_service(DualResource)
        await provider.aclose()

    asyncio.run(run())
    assert events == ["aclose"]


def test_sync_close_rejects_async_only_resources_without_partial_disposal() -> None:
    async def run() -> None:
        provider = (
            ServiceCollection().add_singleton(AsyncResource).build_service_provider()
        )
        resource = provider.get_service(AsyncResource)
        assert resource is not None

        with pytest.raises(AsyncDisposalRequiredError) as caught:
            provider.close()

        assert caught.value.resources == (resource,)
        assert not resource.closed
        assert provider.get_service(AsyncResource) is resource

        await provider.aclose()
        assert resource.closed
        with pytest.raises(ProviderClosedError):
            provider.get_service(AsyncResource)

    asyncio.run(run())


def test_async_context_managers_close_scope_and_provider() -> None:
    async def run() -> tuple[AsyncResource, AsyncResource]:
        services = (
            ServiceCollection()
            .add_scoped(AsyncResource)
            .add_singleton(AsyncResource, key="singleton")
        )
        async with services.build_service_provider() as provider:
            singleton = provider.get_service(AsyncResource, key="singleton")
            assert singleton is not None
            async with provider.create_scope() as scope:
                scoped = scope.get_service(AsyncResource)
                assert scoped is not None
            assert scoped.closed
            with pytest.raises(ScopeClosedError):
                scope.get_service(AsyncResource)
            assert not singleton.closed
        return scoped, singleton

    scoped, singleton = asyncio.run(run())
    assert scoped.closed
    assert singleton.closed


def test_async_disposal_aggregates_errors_and_continues() -> None:
    events: list[str] = []

    class First:
        async def aclose(self) -> None:
            events.append("first")
            raise ValueError("first failure")

    class Second:
        async def aclose(self) -> None:
            events.append("second")
            raise RuntimeError("second failure")

    async def run() -> None:
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
            await scope.aclose()

        assert [str(error) for error in caught.value.errors] == [
            "second failure",
            "first failure",
        ]
        with pytest.raises(ScopeClosedError):
            scope.get_service(First)
        await scope.aclose()

    asyncio.run(run())
    assert events == ["second", "first"]


def test_concurrent_async_close_waits_for_the_same_disposal() -> None:
    entered: asyncio.Event
    release: asyncio.Event
    closes = 0

    class SlowResource:
        async def aclose(self) -> None:
            nonlocal closes
            closes += 1
            entered.set()
            await release.wait()

    async def run() -> None:
        nonlocal entered, release
        entered = asyncio.Event()
        release = asyncio.Event()
        provider = (
            ServiceCollection().add_singleton(SlowResource).build_service_provider()
        )
        provider.get_service(SlowResource)

        first = asyncio.create_task(provider.aclose())
        await entered.wait()
        second = asyncio.create_task(provider.aclose())
        await asyncio.sleep(0)
        assert not second.done()

        release.set()
        await asyncio.gather(first, second)

    asyncio.run(run())
    assert closes == 1


def test_cancelled_async_close_finishes_after_in_flight_resolution() -> None:
    entered = Event()
    release = Event()

    class Dependency:
        pass

    def factory(_) -> Dependency:
        entered.set()
        assert release.wait(timeout=5)
        return Dependency()

    async def run() -> None:
        provider = (
            ServiceCollection()
            .add_transient(Dependency, factory=factory)
            .build_service_provider()
        )
        resolving = asyncio.create_task(
            asyncio.to_thread(provider.get_service, Dependency)
        )
        assert await asyncio.to_thread(entered.wait, 5)

        closing = asyncio.create_task(provider.aclose())
        while not provider._closing:
            await asyncio.sleep(0)
        closing.cancel()
        await asyncio.sleep(0)
        assert not closing.done()

        release.set()
        assert isinstance(await resolving, Dependency)
        with pytest.raises(asyncio.CancelledError):
            await closing
        with pytest.raises(ProviderClosedError):
            provider.get_service(Dependency)

    asyncio.run(run())


def test_async_scope_context_is_task_local_for_injection() -> None:
    class Dependency:
        pass

    async def resolve_dependency(dependency: Dependency) -> Dependency:
        await asyncio.sleep(0)
        return dependency

    resolve_dependency.__annotations__["dependency"] = Dependency
    resolve = inject(resolve_dependency)

    async def work(provider: ServiceProvider) -> Dependency:
        async with provider.create_scope() as scope:
            await asyncio.sleep(0)
            dependency = await resolve()
            assert dependency is scope.get_service(Dependency)
            return dependency

    async def run() -> tuple[Dependency, Dependency]:
        provider = ServiceCollection().add_scoped(Dependency).build_service_provider()
        try:
            first, second = await asyncio.gather(work(provider), work(provider))
            return first, second
        finally:
            provider.close()

    first, second = asyncio.run(run())
    assert first is not second
    with pytest.raises(InjectionError, match="no service scope is active"):
        asyncio.run(resolve())
