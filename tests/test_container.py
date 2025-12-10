from abc import ABC, abstractmethod

import pytest

from pydico.core.container import Container
from pydico.exceptions import (
    AbstractDependencyError,
    CircularDependencyError,
    ImplementationMismatchError,
    MissingTypeHintError,
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
    Container.clean()


def test_add_transient_01():
    Container.add_transient(ILogger, ConsoleLogger)

    instance1 = Container.get(ILogger)
    instance2 = Container.get(ConsoleLogger)

    assert isinstance(instance1, ConsoleLogger)
    assert isinstance(instance2, ConsoleLogger)
    assert instance1 is not instance2


def test_add_transient_02():
    Container.add_transient("logger", ConsoleLogger)

    instance1 = Container.get("logger")
    instance2 = Container.get("logger")

    assert isinstance(instance1, ConsoleLogger)
    assert isinstance(instance2, ConsoleLogger)
    assert instance1 is not instance2


def test_add_transient_fails_on_abstract_dependency():
    with pytest.raises(AbstractDependencyError):
        Container.add_transient(ABC, AbstractTest)


def test_add_transient_fails_on_implementation_mismatch():
    with pytest.raises(ImplementationMismatchError):
        Container.add_transient(ILogger, ServiceA)


def test_add_singleton_01():
    Container.add_singleton(ILogger, ConsoleLogger)

    instance1 = Container.get(ILogger)
    instance2 = Container.get(ConsoleLogger)

    assert isinstance(instance1, ConsoleLogger)
    assert isinstance(instance2, ConsoleLogger)
    assert instance1 is instance2


def test_add_singleton_02():
    Container.add_singleton("logger", ConsoleLogger)

    instance1 = Container.get("logger")
    instance2 = Container.get(ConsoleLogger)

    assert isinstance(instance1, ConsoleLogger)
    assert isinstance(instance2, ConsoleLogger)
    assert instance1 is instance2


def test_add_singleton_03():
    Container.add_singleton(ConsoleLogger)

    instance1 = Container.get(ConsoleLogger)
    instance2 = Container.get(ConsoleLogger)

    assert isinstance(instance1, ConsoleLogger)
    assert isinstance(instance2, ConsoleLogger)
    assert instance1 is instance2


def test_add_singleton_fails_on_abstract_dependency_01():
    with pytest.raises(AbstractDependencyError):
        Container.add_singleton(ABC, AbstractTest)


def test_add_singleton_fails_on_abstract_dependency_02():
    with pytest.raises(AbstractDependencyError):
        Container.add_singleton(AbstractTest)


def test_add_singleton_fails_on_implementation_mismatch():
    with pytest.raises(ImplementationMismatchError):
        Container.add_singleton(ILogger, ServiceA)


def test_get_01():
    instance1 = Container.get(ServiceA)
    instance2 = Container.get(ServiceA)

    assert isinstance(instance1, ServiceA)
    assert isinstance(instance2, ServiceA)
    assert instance1 is not instance2


def test_get_02():
    Container.add_singleton(ServiceA)

    instance_b = Container.get(ServiceB)

    assert isinstance(instance_b, ServiceB)

    instance_a_via_b = instance_b.service_a
    instance_a_direct = Container.get(ServiceA)

    assert isinstance(instance_a_direct, ServiceA)
    assert instance_a_via_b is instance_a_direct


def test_get_fails_on_missing_type_hint():
    with pytest.raises(MissingTypeHintError):
        Container.get(UnresolvedDep)


def test_get_fails_on_circular_dependency():
    Container.add_singleton(CircularDepA)
    Container.add_singleton(CircularDepB)

    with pytest.raises(CircularDependencyError):
        Container.get(CircularDepA)


def test_get_fails_on_unregistered_dependency_01():
    with pytest.raises(UnregisteredDependencyError):
        Container.get(ILogger)


def test_get_fails_on_unregistered_dependency_02():
    with pytest.raises(UnregisteredDependencyError):
        Container.get("logger")
