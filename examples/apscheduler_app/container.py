from examples.apscheduler_app.resources import AsyncJobConnection
from examples.apscheduler_app.services import CleanupJob
from examples.apscheduler_app.settings import WorkerSettings
from pydico import ServiceCollection, ServiceProvider


def build_provider(settings: WorkerSettings) -> ServiceProvider:
    service_collection = ServiceCollection()
    service_collection.add_instance(WorkerSettings, settings)
    service_collection.add_scoped(AsyncJobConnection)
    service_collection.add_transient(CleanupJob)
    return service_collection.build_service_provider(validate=True)
