from examples.apscheduler_app.services import CleanupJob
from pydico import ServiceProvider


async def run_cleanup(provider: ServiceProvider) -> None:
    async with provider.create_scope() as scope:
        job = scope.get_service(CleanupJob)
        if job is None:
            raise RuntimeError("CleanupJob is not registered.")
        result = await job.run()
        print(result)
