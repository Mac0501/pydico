from examples.fastapi_app.domain import Report
from examples.fastapi_app.infrastructure import ReportStore, RequestUnitOfWork


class ReportRepository:
    def __init__(
        self,
        store: ReportStore,
        unit_of_work: RequestUnitOfWork,
    ) -> None:
        self._store = store
        self._unit_of_work = unit_of_work

    def create(self, title: str) -> Report:
        report = self._store.add(title)
        self._unit_of_work.complete()
        return report

    def list(self) -> tuple[Report, ...]:
        return self._store.list()


class ReportService:
    def __init__(self, repository: ReportRepository) -> None:
        self._repository = repository

    def create(self, title: str) -> Report:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("A report title is required.")
        return self._repository.create(normalized_title)

    def list(self) -> tuple[Report, ...]:
        return self._repository.list()
