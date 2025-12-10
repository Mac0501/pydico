import functools
import inspect
from typing import TYPE_CHECKING, Any, Callable, ParamSpec, TypeVar

from .core.container import Container
from .core.depends import Depends

P = ParamSpec("P")
R = TypeVar("R")


if TYPE_CHECKING:
    DependsT = Depends[type[Any]]
else:
    DependsT = Depends


def inject(func: Callable[P, R]) -> Callable[P, R]:
    sig = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        bound = sig.bind_partial(*args, **kwargs)

        for name, param in sig.parameters.items():
            if name in ("self", "cls"):
                continue

            if (
                name in bound.arguments
                and bound.arguments[name] is not inspect.Parameter.empty
            ):
                continue

            default = param.default

            if isinstance(default, DependsT):
                if default.key != None:
                    key_or_provider = default.key
                else:
                    key_or_provider = default.t

                instance = Container.get(key_or_provider)

                bound.arguments[name] = instance

        return func(*bound.args, **bound.kwargs)

    return wrapper
