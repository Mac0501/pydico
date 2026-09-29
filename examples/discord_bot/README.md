# discord.py example

The bot owns one provider and opens a separate pydico scope for every command.
That keeps command resources isolated while shared services remain singletons.

Install discord.py, configure a token, and run the bot from the repository root:

```shell
python -m pip install discord.py
$env:DISCORD_TOKEN = "your-token"
python -m examples.discord_bot.bot
```

Enable the message-content intent for the bot in the Discord developer portal,
then use `!hello` or `!recent` in a channel visible to the bot.
