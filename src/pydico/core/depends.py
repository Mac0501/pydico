from abc import ABC
from typing import TYPE_CHECKING, Any, Protocol, Self, TypeAlias

# --- Type Aliases (Based on previous context and DI needs) ---
Interface: TypeAlias = type[ABC]  # Typically an Abstract Base Class (ABC)
Dependency: TypeAlias = type[Any]  # The concrete class implementing the interface


if TYPE_CHECKING:

    class _Marker(Protocol):
        __IS_MARKER__: bool

        def __call__(self) -> Self: ...
        def __getattr__(self, item: str) -> Self: ...
        def __getitem__(self, item: Any) -> Any: ...
        def __repr__(self) -> str: ...

    Depends: _Marker
else:

    class _Marker:

        __IS_MARKER__ = True

        def __init__(self, key: str | Interface | Dependency) -> None:
            self.key = key

        def __class_getitem__(cls, key: str | Interface | Dependency) -> Self:
            return cls(key)

        def __call__(self) -> Self:
            return self

        def __repr__(self) -> str:
            cls_name = self.__class__.__name__
            return f"{cls_name}"

    class Depends(_Marker): ...
