# APScheduler example

The scheduler owns timing and execution. Each job run opens its own async
pydico scope, resolves a job service, and asynchronously closes the scoped
connection afterward.

This example targets APScheduler 3.x. Install it and start the worker from the
repository root:

```shell
python -m pip install "apscheduler>=3.10,<4"
python -m examples.apscheduler_app.main
```

The cleanup job runs once at startup and then every ten seconds. Stop it with
Ctrl+C.
