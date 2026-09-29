from examples.click_cli.repository import UserRepository
from examples.click_cli.services import UserService
from pydico import ServiceCollection, ServiceProvider


def build_provider() -> ServiceProvider:
    service_collection = ServiceCollection()
    service_collection.add_scoped(UserRepository)
    service_collection.add_transient(UserService)
    return service_collection.build_service_provider(validate=True)
