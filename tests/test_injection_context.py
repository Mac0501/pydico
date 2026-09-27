import asyncio
import inspect
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from pydico import get_current_resolver, inject, use_resolver
from pydico.collection import ServiceCollection
from pydico.exceptions import ScopeClosedError, ScopedResolutionError


class Dependency:
    pass


@inject
def resolve(dependency: Dependency) -> Dependency:
    return dependency


def test_nested_context_restoration_on_exception_and_scope_isolation() -> None:
    provider = ServiceCollection().add_scoped(Dependency).build_service_provider()
    assert get_current_resolver() is None
    with provider.create_scope() as first, provider.create_scope() as second:
        with use_resolver(first):
            original = resolve()
            assert resolve() is original
            with pytest.raises(ValueError):
                with use_resolver(second):
                    assert resolve() is not original
                    raise ValueError("body")
            assert get_current_resolver() is first
            assert resolve() is original
        assert get_current_resolver() is None
        assert first.get_service(Dependency) is original


def test_explicit_resolver_precedes_context_and_closed_scope_is_respected() -> None:
    provider = ServiceCollection().add_scoped(Dependency).build_service_provider()
    with provider.create_scope() as scope, use_resolver(scope):
        root_bound = inject(provider)(inspect.unwrap(resolve))
        with pytest.raises(ScopedResolutionError):
            root_bound()
        scope_bound = inject(scope)(inspect.unwrap(resolve))
        assert scope_bound() is resolve()
    with pytest.raises(ScopeClosedError):
        scope_bound()
    explicit = Dependency()
    assert scope_bound(explicit) is explicit


def test_thread_contexts_are_independent() -> None:
    provider = ServiceCollection().add_scoped(Dependency).build_service_provider()
    barrier = Barrier(4)

    def work():
        assert get_current_resolver() is None
        with provider.create_scope() as scope, use_resolver(scope):
            barrier.wait(timeout=5)
            result = resolve()
            assert result is scope.get_service(Dependency)
        assert get_current_resolver() is None
        return result

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(work) for _ in range(4)]
        results = [future.result(timeout=5) for future in futures]
    assert len({id(result) for result in results}) == 4


def test_async_tasks_resolve_at_execution_and_preserve_context() -> None:
    provider = ServiceCollection().add_scoped(Dependency).build_service_provider()

    @inject()
    async def action(dependency: Dependency):
        await asyncio.sleep(0)
        assert resolve() is dependency
        return dependency

    assert inspect.iscoroutinefunction(action)

    async def work():
        coroutine = action()
        with provider.create_scope() as scope, use_resolver(scope):
            result = await coroutine
            assert result is scope.get_service(Dependency)
            return result

    async def run():
        return await asyncio.gather(work(), work())

    first, second = asyncio.run(run())
    assert first is not second
    assert get_current_resolver() is None
