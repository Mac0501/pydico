"""Type-based injection for synchronous and asynchronous functions."""

import inspect
from collections.abc import Callable
from functools import wraps
from threading import RLock
from typing import Any, TypeVar, cast, get_type_hints, overload

from pydico._context import current_resolver
from pydico.exceptions import (
    InjectionError,
    MissingTypeAnnotationError,
    NoActiveScopeError,
    ServiceNotRegisteredError,
    UnsupportedTypeAnnotationError,
)
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
    defaults take precedence. Only unkeyed class annotations resolve.
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
    signature = inspect.signature(function)
    name = function.__qualname__
    hints: dict[str, Any] | None = None
    hints_lock = RLock()

    def arguments(
        args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> inspect.BoundArguments:
        nonlocal hints
        bound = signature.bind_partial(*args, **kwargs)
        missing = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.name not in bound.arguments
            and parameter.name not in ("self", "cls")
            and parameter.default is inspect.Parameter.empty
            and parameter.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        if missing:
            active = resolver if resolver is not None else current_resolver()
            if active is None:
                raise NoActiveScopeError(function)
            with hints_lock:
                if hints is None:
                    try:
                        hints = get_type_hints(function, include_extras=True)
                    except Exception as error:
                        raise InjectionError(
                            f"{name}: cannot resolve type annotations"
                        ) from error
                resolved_hints = hints
            types: list[type[Any]] = []
            for parameter in missing:
                annotation = resolved_hints.get(parameter.name)
                if annotation is None:
                    raise MissingTypeAnnotationError(function, parameter.name)
                if not isinstance(annotation, type) or annotation is Any:
                    raise UnsupportedTypeAnnotationError(
                        function, parameter.name, annotation
                    )
                types.append(annotation)
            for parameter, service_type in zip(missing, types):
                value = active.get_service(service_type)
                if value is None:
                    raise ServiceNotRegisteredError(
                        service_type,
                        target=function,
                        parameter_name=parameter.name,
                    )
                bound.arguments[parameter.name] = value
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
