from abc import ABC
from typing import TYPE_CHECKING, Any, Protocol, Self, TypeAlias, TypeVar

Interface: TypeAlias = type[ABC]
Dependency: TypeAlias = type[Any]

T = TypeVar("T")

if TYPE_CHECKING:

    class _Marker(Protocol):
        __IS_MARKER__: bool
        t: Interface | Dependency
        key: str | None

        def __call__(self) -> Self: ...
        def __getattr__(self, key: str) -> Self: ...
        def __getitem__(self, key: tuple[type[T], str] | type[T]) -> T: ...
        def __repr__(self) -> str: ...

    Depends: _Marker
else:

    class _Marker:
        __IS_MARKER__ = True
        t: Interface | Dependency
        key: str | None

        def __init__(
            self, t: str | Interface | Dependency, key: str | None = None
        ) -> None:
            self.t = t
            self.key = key

        def __class_getitem__(
            cls, key: tuple[Interface | Dependency, str] | Interface | Dependency
        ) -> Self:
            if isinstance(key, tuple):
                return cls(key[0], key[1])
            return cls(key)

        def __call__(self) -> Self:
            return self

        def __repr__(self) -> str:
            cls_name = self.__class__.__name__
            return f"{cls_name}(t={self.t!r}, key={self.key!r})"

    class Depends(_Marker): ...
