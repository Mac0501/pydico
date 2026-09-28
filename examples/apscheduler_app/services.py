from examples.apscheduler_app.resources import AsyncJobConnection
from examples.apscheduler_app.settings import WorkerSettings


class CleanupJob:
    def __init__(
        self,
        connection: AsyncJobConnection,
        settings: WorkerSettings,
    ) -> None:
        self._connection = connection
        self._settings = settings

    async def run(self) -> str:
        deleted = await self._connection.execute_cleanup(self._settings.retention_days)
        return f"connection={self._connection.id} deleted={deleted}"
