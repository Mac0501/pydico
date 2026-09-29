from typing import Protocol, runtime_checkable


@runtime_checkable
class SupportsClose(Protocol):
    """A service with synchronous resources owned by its DI lifetime."""

    def close(self) -> None: ...


@runtime_checkable
class SupportsAsyncClose(Protocol):
    """A service with asynchronous resources owned by its DI lifetime."""

    async def aclose(self) -> None: ...


type OwnedResource = SupportsClose | SupportsAsyncClose
