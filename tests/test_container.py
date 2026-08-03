from abc import ABC, abstractmethod

import pytest

from pydico import Container, Lifetime, Resolver
from pydico.exceptions import (
    AbstractDependencyError,
    CircularDependencyError,
    ImplementationMismatchError,
    InstanceTypeError,
    MissingTypeHintError,
    ScopeClosedError,
    ScopeRequiredError,
    UnregisteredDependencyError,
)


class ILogger(ABC):
    @abstractmethod
    def log(self, message: str) -> str:
        pass


class ConsoleLogger(ILogger):
    def log(self, message: str) -> str:
        return f"Logged: {message}"


class ServiceA:
    def execute(self) -> str:
        return "Service A"


class ServiceB:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a

    def run(self) -> str:
        return f"B ran with {self.service_a.execute()}"


class CircularDepA:
    def __init__(self, b: "CircularDepB"):
        self.b = b


class CircularDepB:
    def __init__(self, a: CircularDepA):
        self.a = a


class AbstractTest(ABC):
    @abstractmethod
    def required_method(self) -> None:
        pass


class UnresolvedDep:
    def __init__(
        self,
        missing_param,  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
    ):
        pass


class ServiceWithDefault:
    def __init__(self, retries: int = 3):
        self.retries = retries


class ServiceWithPositionalDependency:
    def __init__(self, service_a: ServiceA, /):
        self.service_a = service_a


class FactoryService:
    def __init__(self, service_a: ServiceA, name: str):
        self.service_a = service_a
        self.name = name


class RequestContext:
    pass


class AlternateRequestContext(RequestContext):
    pass


class ScopedConsumer:
    def __init__(self, context: RequestContext):
        self.context = context


class SingletonWithScopedDependency:
    def __init__(self, context: RequestContext):
        self.context = context


@pytest.fixture
def container() -> Container:
    return Container()


def test_register_transient_interface(container: Container):
    container.register_transient(ILogger, ConsoleLogger)

    instance1 = container.resolve(ILogger)
    instance2 = container.resolve(ILogger)

    assert isinstance(instance1, ConsoleLogger)
    assert isinstance(instance2, ConsoleLogger)
    assert instance1 is not instance2


def test_register_transient_concrete_class(container: Container):
    container.register_transient(ServiceA)

    assert container.resolve(ServiceA) is not container.resolve(ServiceA)


def test_register_transient_string_key(container: Container):
    container.register_transient("logger", ConsoleLogger)

    instance1 = container.resolve("logger")
    instance2 = container.resolve("logger")

    assert isinstance(instance1, ConsoleLogger)
    assert isinstance(instance2, ConsoleLogger)
    assert instance1 is not instance2


def test_register_transient_fails_on_abstract_implementation(container: Container):
    with pytest.raises(AbstractDependencyError):
        container.register_transient("abstract", AbstractTest)


def test_register_transient_fails_on_implementation_mismatch(container: Container):
    with pytest.raises(ImplementationMismatchError):
        container.register_transient(ILogger, ServiceA)


def test_register_singleton_interface(container: Container):
    container.register_singleton(ILogger, ConsoleLogger)

    instance1 = container.resolve(ILogger)
    instance2 = container.resolve(ILogger)

    assert isinstance(instance1, ConsoleLogger)
    assert instance1 is instance2


def test_registration_only_applies_to_its_key(container: Container):
    container.register_singleton(ILogger, ConsoleLogger)

    interface_instance = container.resolve(ILogger)
    concrete_instance1 = container.resolve(ConsoleLogger)
    concrete_instance2 = container.resolve(ConsoleLogger)

    assert concrete_instance1 is not interface_instance
    assert concrete_instance1 is not concrete_instance2


def test_register_singleton_string_key(container: Container):
    container.register_singleton("logger", ConsoleLogger)

    instance1 = container.resolve("logger")
    instance2 = container.resolve("logger")

    assert isinstance(instance1, ConsoleLogger)
    assert instance1 is instance2


def test_register_singleton_concrete_class(container: Container):
    container.register_singleton(ConsoleLogger)

    assert container.resolve(ConsoleLogger) is container.resolve(ConsoleLogger)


def test_register_instance(container: Container):
    logger = ConsoleLogger()
    container.register_instance(ILogger, logger)

    assert container.resolve(ILogger) is logger


def test_register_instance_supports_none_with_string_key(container: Container):
    container.register_instance("optional-value", None)

    assert container.resolve("optional-value") is None


def test_register_instance_validates_its_type(container: Container):
    with pytest.raises(InstanceTypeError):
        container.register_instance(
            ILogger, ServiceA()
        )  # pyright: ignore[reportCallIssue]


def test_register_transient_factory(container: Container):
    container.register_singleton(ServiceA)

    def create_service(resolver: Resolver) -> FactoryService:
        return FactoryService(resolver.resolve(ServiceA), "transient")

    container.register_factory(FactoryService, create_service)

    instance1 = container.resolve(FactoryService)
    instance2 = container.resolve(FactoryService)

    assert instance1 is not instance2
    assert instance1.service_a is instance2.service_a
    assert instance1.name == "transient"


def test_register_singleton_factory(container: Container):
    call_count = 0

    def create_service(resolver: Resolver) -> FactoryService:
        nonlocal call_count
        call_count += 1
        return FactoryService(resolver.resolve(ServiceA), "singleton")

    container.register_factory(
        FactoryService,
        create_service,
        lifetime=Lifetime.SINGLETON,
    )

    instance1 = container.resolve(FactoryService)
    instance2 = container.resolve(FactoryService)

    assert instance1 is instance2
    assert call_count == 1


def test_register_factory_supports_string_key_and_none(container: Container):
    container.register_factory(
        "optional-value",
        lambda resolver: None,
        lifetime=Lifetime.SINGLETON,
    )

    assert container.resolve("optional-value") is None
    assert container.resolve("optional-value") is None


def test_register_factory_validates_result_type(container: Container):
    container.register_factory(
        ILogger,
        lambda resolver: ServiceA(),  # pyright: ignore[reportArgumentType, reportReturnType]
    )

    with pytest.raises(InstanceTypeError):
        container.resolve(ILogger)


def test_resolve_reports_factory_cycle(container: Container):
    container.register_factory("a", lambda resolver: resolver.resolve("b"))
    container.register_factory("b", lambda resolver: resolver.resolve("a"))

    with pytest.raises(CircularDependencyError) as exc_info:
        container.resolve("a")

    assert exc_info.value.chain == ["a", "b", "a"]


def test_scoped_instance_is_reused_within_scope(container: Container):
    container.register_scoped(RequestContext)

    with container.create_scope() as scope:
        instance1 = scope.resolve(RequestContext)
        instance2 = scope.resolve(RequestContext)

    assert instance1 is instance2


def test_scoped_instances_are_isolated_between_scopes(container: Container):
    container.register_scoped(RequestContext)

    with container.create_scope() as first_scope:
        first = first_scope.resolve(RequestContext)

    with container.create_scope() as second_scope:
        second = second_scope.resolve(RequestContext)

    assert first is not second


def test_transients_share_scoped_dependencies_within_scope(container: Container):
    container.register_scoped(RequestContext)

    with container.create_scope() as scope:
        consumer1 = scope.resolve(ScopedConsumer)
        consumer2 = scope.resolve(ScopedConsumer)

    assert consumer1 is not consumer2
    assert consumer1.context is consumer2.context


def test_scoped_factory_is_cached_per_scope(container: Container):
    call_count = 0

    def create_service(resolver: Resolver) -> FactoryService:
        nonlocal call_count
        call_count += 1
        return FactoryService(resolver.resolve(ServiceA), "scoped")

    container.register_factory(
        FactoryService,
        create_service,
        lifetime=Lifetime.SCOPED,
    )

    with container.create_scope() as first_scope:
        first = first_scope.resolve(FactoryService)
        assert first_scope.resolve(FactoryService) is first

    with container.create_scope() as second_scope:
        second = second_scope.resolve(FactoryService)

    assert first is not second
    assert call_count == 2


def test_scoped_dependency_requires_scope(container: Container):
    container.register_scoped(RequestContext)

    with pytest.raises(ScopeRequiredError):
        container.resolve(RequestContext)


def test_singleton_cannot_capture_scoped_dependency(container: Container):
    container.register_scoped(RequestContext)
    container.register_singleton(SingletonWithScopedDependency)

    with container.create_scope() as scope:
        with pytest.raises(ScopeRequiredError):
            scope.resolve(SingletonWithScopedDependency)


def test_singleton_is_shared_between_root_and_scopes(container: Container):
    container.register_singleton(ServiceA)
    root_instance = container.resolve(ServiceA)

    with container.create_scope() as scope:
        scoped_resolution = scope.resolve(ServiceA)

    assert scoped_resolution is root_instance


def test_closed_scope_cannot_resolve(container: Container):
    scope = container.create_scope()
    scope.close()
    scope.close()

    assert scope.is_closed
    with pytest.raises(ScopeClosedError):
        scope.resolve(ServiceA)


def test_scope_uses_new_descriptor_after_reregistration(container: Container):
    container.register_scoped(RequestContext)

    with container.create_scope() as scope:
        original = scope.resolve(RequestContext)
        container.register_scoped(RequestContext, AlternateRequestContext)
        replacement = scope.resolve(RequestContext)

    assert type(original) is RequestContext
    assert type(replacement) is AlternateRequestContext


def test_later_registration_replaces_previous_lifetime(container: Container):
    container.register_singleton(ILogger, ConsoleLogger)
    singleton = container.resolve(ILogger)

    container.register_transient(ILogger, ConsoleLogger)
    transient1 = container.resolve(ILogger)
    transient2 = container.resolve(ILogger)

    assert transient1 is not singleton
    assert transient1 is not transient2


def test_register_singleton_fails_on_abstract_implementation(container: Container):
    with pytest.raises(AbstractDependencyError):
        container.register_singleton(AbstractTest)


def test_register_singleton_fails_on_implementation_mismatch(container: Container):
    with pytest.raises(ImplementationMismatchError):
        container.register_singleton(ILogger, ServiceA)


def test_unregistered_concrete_class_is_autowired(container: Container):
    instance1 = container.resolve(ServiceA)
    instance2 = container.resolve(ServiceA)

    assert isinstance(instance1, ServiceA)
    assert instance1 is not instance2


def test_autowiring_uses_registered_dependencies(container: Container):
    container.register_singleton(ServiceA)

    service_b = container.resolve(ServiceB)

    assert service_b.service_a is container.resolve(ServiceA)


def test_autowiring_preserves_constructor_defaults(container: Container):
    service = container.resolve(ServiceWithDefault)

    assert service.retries == 3


def test_autowiring_supports_positional_only_dependencies(container: Container):
    service = container.resolve(ServiceWithPositionalDependency)

    assert isinstance(service.service_a, ServiceA)


def test_builtin_types_are_not_autowired(container: Container):
    with pytest.raises(UnregisteredDependencyError):
        container.resolve(str)


def test_resolve_fails_on_missing_type_hint(container: Container):
    with pytest.raises(MissingTypeHintError):
        container.resolve(UnresolvedDep)


def test_resolve_fails_on_registered_circular_dependency(container: Container):
    container.register_singleton(CircularDepA)
    container.register_singleton(CircularDepB)

    with pytest.raises(CircularDependencyError):
        container.resolve(CircularDepA)


def test_resolve_reports_complete_unregistered_cycle(container: Container):
    with pytest.raises(CircularDependencyError) as exc_info:
        container.resolve(CircularDepA)

    assert exc_info.value.chain == [CircularDepA, CircularDepB, CircularDepA]


def test_resolve_fails_on_unregistered_abstract_dependency(container: Container):
    with pytest.raises(UnregisteredDependencyError):
        container.resolve(ILogger)


def test_resolve_fails_on_unregistered_string_key(container: Container):
    with pytest.raises(UnregisteredDependencyError):
        container.resolve("logger")


def test_containers_are_isolated():
    first = Container()
    second = Container()
    first.register_singleton(ILogger, ConsoleLogger)

    assert isinstance(first.resolve(ILogger), ConsoleLogger)
    with pytest.raises(UnregisteredDependencyError):
        second.resolve(ILogger)


def test_clear_removes_registrations(container: Container):
    container.register_singleton(ILogger, ConsoleLogger)

    container.clear()

    with pytest.raises(UnregisteredDependencyError):
        container.resolve(ILogger)
