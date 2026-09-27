from typing import Protocol, runtime_checkable


@runtime_checkable
class SupportsClose(Protocol):
    """A service with synchronous resources owned by its DI lifetime."""

    def close(self) -> None: ...
