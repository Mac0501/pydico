"""Type-based injection for synchronous and asynchronous functions."""

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast, overload

from pydico._context import current_resolver
from pydico._dependencies import DependencyPlan, resolve_dependency
from pydico.exceptions import InjectionError, NoActiveScopeError
from pydico.resolver import ServiceResolver

R = TypeVar("R")


@overload
def inject(target: Callable[..., R]) -> Callable[..., R]: ...


@overload
def inject(
    target: ServiceResolver | None = None,
) -> Callable[[Callable[..., R]], Callable[..., R]]: ...


def inject(target: object = None) -> Callable[..., Any]:
    """Inject missing required arguments via a bound or context resolver.

    Supports @inject, @inject(), and @inject(resolver). Explicit arguments and
    defaults take precedence. Plain, keyed, and collection annotations resolve.
    """
    if target is None or (
        callable(getattr(target, "get_service", None))
        and callable(getattr(target, "get_services", None))
    ):
        resolver = cast(ServiceResolver | None, target)

        def decorator(function: Callable[..., R]) -> Callable[..., R]:
            return _decorate(function, resolver)

        return decorator
    if callable(target):
        return _decorate(target, None)
    raise TypeError("inject expects a function or a ServiceResolver")


def _decorate(
    function: Callable[..., R], resolver: ServiceResolver | None
) -> Callable[..., R]:
    if inspect.isgeneratorfunction(function) or inspect.isasyncgenfunction(function):
        raise InjectionError("inject does not support generator functions")
    plan = DependencyPlan(function)
    signature = plan.signature

    def arguments(
        args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> inspect.BoundArguments:
        bound = signature.bind_partial(*args, **kwargs)
        missing = tuple(
            parameter
            for parameter in plan.required_parameters()
            if parameter.name not in bound.arguments
        )
        if missing:
            active = resolver if resolver is not None else current_resolver()
            if active is None:
                raise NoActiveScopeError(function)
            for request in plan.requests(missing):
                bound.arguments[request.parameter_name] = resolve_dependency(
                    request, resolver=active, target=function
                )
        signature.bind(*bound.args, **bound.kwargs)
        return bound

    if inspect.iscoroutinefunction(function):

        @wraps(function)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = arguments(args, kwargs)
            return await function(*bound.args, **bound.kwargs)

        return cast(Callable[..., R], async_wrapper)

    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> R:
        bound = arguments(args, kwargs)
        return function(*bound.args, **bound.kwargs)

    return wrapper
