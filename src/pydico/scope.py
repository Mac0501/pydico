from __future__ import annotations

from types import TracebackType
from typing import Callable, TypeVar, overload

from pydico.exceptions import ScopeClosedError
from pydico.types import Key

T = TypeVar("T")


class Scope:
    def __init__(
        self,
        resolve_key: Callable[[Key], object],
        close_scope: Callable[[], None],
    ) -> None:
        self._resolve_key = resolve_key
        self._close_scope = close_scope
        self._is_closed = False

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    @overload
    def resolve(self, key: type[T]) -> T: ...

    @overload
    def resolve(self, key: str) -> object: ...

    def resolve(self, key: Key) -> object:
        self._ensure_open()
        return self._resolve_key(key)

    def close(self) -> None:
        if self._is_closed:
            return

        self._is_closed = True
        self._close_scope()

    def __enter__(self) -> Scope:
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._is_closed:
            raise ScopeClosedError()
