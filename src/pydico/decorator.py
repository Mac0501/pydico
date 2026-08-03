import functools
import inspect
from typing import Callable, ParamSpec, TypeVar, get_type_hints

from pydico.exceptions import MissingTypeHintError
from pydico.types import Resolver

from .core.depends import DependencyMarker

P = ParamSpec("P")
R = TypeVar("R")


def inject(resolver: Resolver) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        signature = inspect.signature(func)
        resolved_hints = get_type_hints(func)
        dependencies: dict[str, str | type[object]] = {}

        for name, parameter in signature.parameters.items():
            marker = parameter.default
            if not isinstance(marker, DependencyMarker):
                continue

            if marker.key is not None:
                dependencies[name] = marker.key
                continue

            if parameter.annotation is inspect.Parameter.empty:
                raise MissingTypeHintError(func, name)

            dependencies[name] = resolved_hints[name]

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            bound = signature.bind_partial(*args, **kwargs)

            for name, dependency_key in dependencies.items():
                if name in bound.arguments:
                    continue

                bound.arguments[name] = resolver.resolve(dependency_key)

            return func(*bound.args, **bound.kwargs)

        return wrapper

    return decorator
