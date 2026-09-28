# pydico framework examples

These examples show how to place pydico inside an application without making
the container responsible for starting the framework.

| Directory | Integration | Lifetime boundary |
| --- | --- | --- |
| `fastapi_app` | FastAPI | One scope per request |
| `discord_bot` | discord.py | One scope per command |
| `click_cli` | Click | One scope per command invocation |
| `apscheduler_app` | APScheduler | One scope per job execution |

Run the commands in each example's README from the repository root. The
framework packages are optional example dependencies and are deliberately not
runtime dependencies of pydico.
