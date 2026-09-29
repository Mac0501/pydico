import asyncio
from uuid import uuid4


class AsyncJobConnection:
    """An async-only resource owned by one scheduled job scope."""

    def __init__(self) -> None:
        self.id = uuid4().hex[:8]
        self.closed = False

    async def execute_cleanup(self, retention_days: int) -> int:
        await asyncio.sleep(0.05)
        return retention_days // 3

    async def aclose(self) -> None:
        await asyncio.sleep(0)
        self.closed = True
