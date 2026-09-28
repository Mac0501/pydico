from examples.discord_bot.resources import CommandSession
from examples.discord_bot.services import AuditLog, GreetingService
from pydico import ServiceCollection, ServiceProvider


def build_provider() -> ServiceProvider:
    service_collection = ServiceCollection()
    service_collection.add_singleton(AuditLog)
    service_collection.add_scoped(CommandSession)
    service_collection.add_transient(GreetingService)
    return service_collection.build_service_provider(validate=True)
