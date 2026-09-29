from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    retention_days: int = 30
    interval_seconds: int = 10
