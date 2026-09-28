from discord import Intents
from discord.ext import commands

from examples.discord_bot.container import build_provider
from examples.discord_bot.services import AuditLog, GreetingService
from examples.discord_bot.settings import BotSettings
from pydico import ServiceProvider


class PydicoBot(commands.Bot):
    def __init__(self, provider: ServiceProvider, settings: BotSettings) -> None:
        intents = Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=settings.command_prefix, intents=intents)
        self.provider = provider

    async def close(self) -> None:
        try:
            await super().close()
        finally:
            await self.provider.aclose()


def create_bot(provider: ServiceProvider, settings: BotSettings) -> PydicoBot:
    bot = PydicoBot(provider, settings)

    @bot.command()
    async def hello(ctx: commands.Context[commands.Bot]) -> None:
        async with provider.create_scope() as scope:
            service = scope.get_service(GreetingService)
            if service is None:
                raise RuntimeError("GreetingService is not registered.")
            await ctx.send(service.greet(ctx.author.display_name))

    @bot.command()
    async def recent(ctx: commands.Context[commands.Bot]) -> None:
        audit_log = provider.get_service(AuditLog)
        if audit_log is None:
            raise RuntimeError("AuditLog is not registered.")
        entries = audit_log.recent()
        await ctx.send("\n".join(entries) if entries else "No commands recorded yet.")

    return bot


def main() -> None:
    settings = BotSettings.from_environment()
    provider = build_provider()
    bot = create_bot(provider, settings)
    bot.run(settings.token)


if __name__ == "__main__":
    main()
