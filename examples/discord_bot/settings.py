import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BotSettings:
    token: str
    command_prefix: str = "!"

    @classmethod
    def from_environment(cls) -> "BotSettings":
        token = os.environ.get("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("Set DISCORD_TOKEN before starting the bot.")
        return cls(token=token)
