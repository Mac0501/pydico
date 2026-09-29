import asyncio

from examples.apscheduler_app.container import build_provider as build_worker_provider
from examples.apscheduler_app.resources import AsyncJobConnection
from examples.apscheduler_app.services import CleanupJob
from examples.apscheduler_app.settings import WorkerSettings
from examples.click_cli.container import build_provider as build_cli_provider
from examples.click_cli.services import UserService
from examples.discord_bot.container import build_provider as build_bot_provider
from examples.discord_bot.resources import CommandSession
from examples.discord_bot.services import GreetingService
from examples.fastapi_app.container import build_provider as build_api_provider
from examples.fastapi_app.services import ReportService


def test_fastapi_example_uses_independent_request_scopes() -> None:
    with build_api_provider() as provider:
        with provider.create_scope() as first_scope:
            first_service = first_scope.get_service(ReportService)
            assert first_service is not None
            assert first_service.create("Weekly").id == 1

        with provider.create_scope() as second_scope:
            second_service = second_scope.get_service(ReportService)
            assert second_service is not None
            assert [report.title for report in second_service.list()] == ["Weekly"]


def test_discord_example_isolates_command_sessions() -> None:
    with build_bot_provider() as provider:
        with provider.create_scope() as first_scope:
            first_session = first_scope.get_service(CommandSession)
            greeting = first_scope.get_service(GreetingService)
            assert first_session is not None
            assert greeting is not None
            assert first_session.id in greeting.greet("Ada")

        assert first_session.closed

        with provider.create_scope() as second_scope:
            second_session = second_scope.get_service(CommandSession)
            assert second_session is not None
            assert second_session is not first_session


def test_click_example_creates_a_repository_per_command_scope() -> None:
    with build_cli_provider() as provider:
        with provider.create_scope() as scope:
            service = scope.get_service(UserService)
            assert service is not None
            assert [user.name for user in service.list()] == ["Ada", "Grace"]


def test_apscheduler_example_closes_async_job_resources() -> None:
    async def run() -> None:
        settings = WorkerSettings()
        async with build_worker_provider(settings) as provider:
            async with provider.create_scope() as scope:
                connection = scope.get_service(AsyncJobConnection)
                job = scope.get_service(CleanupJob)
                assert connection is not None
                assert job is not None
                assert "deleted=10" in await job.run()

            assert connection.closed

    asyncio.run(run())
