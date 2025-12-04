from abc import ABC, abstractmethod

import pytest

from pydico.core.container import Container


class ILogger(ABC):
    @abstractmethod
    def log(self, message: str) -> str:
        pass


class ConsoleLogger(ILogger):
    def log(self, message: str) -> str:
        return f"Logged: {message}"


class HeavyLogger(ILogger):
    def log(self, message: str) -> str:
        return f"Heavy Log: {message}"


class ServiceA:
    def execute(self) -> str:
        return "Service A"


class ServiceB:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a

    def run(self) -> str:
        return f"B ran with {self.service_a.execute()}"


class KeyedProcessor:
    def process(self) -> str:
        return "Processed Keyed"


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


@pytest.fixture(autouse=True)
def clean_container_storage():
    yield

    Container._transients.clear()  # pyright: ignore[reportPrivateUsage]
    Container._singletons.clear()  # pyright: ignore[reportPrivateUsage]
    Container._singleton_instances.clear()  # pyright: ignore[reportPrivateUsage]
    Container._keyed_transients.clear()  # pyright: ignore[reportPrivateUsage]
    Container._keyed_singletons.clear()  # pyright: ignore[reportPrivateUsage]
    Container._keyed_singleton_instances.clear()  # pyright: ignore[reportPrivateUsage]


def test_registration_fails_on_abstract_dependency():
    with pytest.raises(
        TypeError,
        match="Implementation AbstractTest must be a subclass of interface ILogger.",
    ):
        Container.add_transient(ILogger, AbstractTest)

    with pytest.raises(
        TypeError,
        match="Cannot register abstract class AbstractTest as a concrete dependency",
    ):
        Container.add_transient(ABC, AbstractTest)


def test_registration_fails_on_non_subclass():
    with pytest.raises(
        TypeError,
        match="Implementation ServiceA must be a subclass of interface ILogger",
    ):
        Container.add_transient(ILogger, ServiceA)


def test_add_singleton_self_fails_on_abstract():
    with pytest.raises(
        TypeError,
        match="Cannot register abstract class AbstractTest for self-registration",
    ):
        Container.add_singleton_self(AbstractTest)


def test_add_transient_and_resolve_new_instance_each_time():
    Container.add_transient(ILogger, ConsoleLogger)

    instance1 = Container.get(ILogger)
    instance2 = Container.get(ILogger)

    assert isinstance(instance1, ConsoleLogger)
    assert instance1 is not instance2
    assert instance1.log("T1") == "Logged: T1"


def test_add_singleton_and_resolve_same_instance():
    Container.add_singleton(ILogger, HeavyLogger)

    instance1 = Container.get(ILogger)
    instance2 = Container.get(ILogger)

    assert isinstance(instance1, HeavyLogger)
    assert instance1 is instance2
    assert instance1.log("S1") == "Heavy Log: S1"


def test_add_singleton_self_and_resolve_same_instance():
    Container.add_singleton_self(ServiceA)

    instance1 = Container.get(ServiceA)
    instance2 = Container.get(ServiceA)

    assert isinstance(instance1, ServiceA)
    assert isinstance(instance2, ServiceA)
    assert instance1 is instance2
    assert instance1.execute() == "Service A"


def test_constructor_injection_with_singleton_self_dependency():
    Container.add_singleton_self(ServiceA)

    instance_b = Container.get(ServiceB)

    assert isinstance(instance_b, ServiceB)
    assert instance_b.run() == "B ran with Service A"

    instance_a_via_b = instance_b.service_a
    instance_a_direct = Container.get(ServiceA)
    assert instance_a_via_b is instance_a_direct


def test_unregistered_dependency_resolves_as_transient():
    instance1 = Container.get(ServiceA)
    instance2 = Container.get(ServiceA)

    assert isinstance(instance1, ServiceA)
    assert instance1 is not instance2


def test_fails_on_missing_type_hint():
    with pytest.raises(
        ValueError,
        match="Parameter 'missing_param' in UnresolvedDep's constructor requires a type hint",
    ):
        Container.get(UnresolvedDep)


def test_fails_on_circular_dependency():
    Container.add_singleton_self(CircularDepA)
    Container.add_singleton_self(CircularDepB)

    with pytest.raises(
        RecursionError, match="Circular dependency detected while resolving"
    ):
        Container.get(CircularDepA)


def test_add_keyed_transient_and_resolve_new_instance_each_time():
    Container.add_keyed_transient("proc_t", KeyedProcessor)

    instance1 = Container.get("proc_t")
    instance2 = Container.get("proc_t")

    assert isinstance(instance1, KeyedProcessor)
    assert instance1 is not instance2


def test_add_keyed_singleton_and_resolve_same_instance():
    Container.add_keyed_singleton("proc_s", KeyedProcessor)

    instance1 = Container.get("proc_s")
    instance2 = Container.get("proc_s")

    assert isinstance(instance1, KeyedProcessor)
    assert instance1 is instance2


def test_fails_on_unregistered_keyed_service():
    with pytest.raises(
        LookupError, match="No keyed service registered for key: 'non_existent_key'"
    ):
        Container.get("non_existent_key")
