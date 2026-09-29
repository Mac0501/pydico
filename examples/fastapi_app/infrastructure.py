from threading import RLock

from examples.fastapi_app.domain import Report


class ReportStore:
    """Application-wide in-memory storage used by the example."""

    def __init__(self) -> None:
        self._reports: list[Report] = []
        self._lock = RLock()

    def add(self, title: str) -> Report:
        with self._lock:
            report = Report(id=len(self._reports) + 1, title=title)
            self._reports.append(report)
            return report

    def list(self) -> tuple[Report, ...]:
        with self._lock:
            return tuple(self._reports)


class RequestUnitOfWork:
    """A request-owned resource that records whether it was completed."""

    def __init__(self) -> None:
        self.completed = False
        self.closed = False

    def complete(self) -> None:
        self.completed = True

    def close(self) -> None:
        self.closed = True
