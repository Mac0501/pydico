from examples.fastapi_app.infrastructure import ReportStore, RequestUnitOfWork
from examples.fastapi_app.services import ReportRepository, ReportService
from pydico import ServiceCollection, ServiceProvider


def build_provider() -> ServiceProvider:
    service_collection = ServiceCollection()
    service_collection.add_singleton(ReportStore)
    service_collection.add_scoped(RequestUnitOfWork)
    service_collection.add_scoped(ReportRepository)
    service_collection.add_transient(ReportService)
    return service_collection.build_service_provider(validate=True)
