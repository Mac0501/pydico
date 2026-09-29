import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from examples.apscheduler_app.container import build_provider
from examples.apscheduler_app.jobs import run_cleanup
from examples.apscheduler_app.settings import WorkerSettings


async def run_worker() -> None:
    settings = WorkerSettings()
    provider = build_provider(settings)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_cleanup,
        "interval",
        seconds=settings.interval_seconds,
        args=(provider,),
        max_instances=1,
    )
    scheduler.start()

    try:
        await run_cleanup(provider)
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await provider.aclose()


def main() -> None:
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
