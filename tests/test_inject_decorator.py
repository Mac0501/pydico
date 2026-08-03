from abc import ABC, abstractmethod
from unittest.mock import MagicMock

import pytest

from pydico import Container, Depends, inject
from pydico.exceptions import MissingTypeHintError


class ILogger(ABC):
    @abstractmethod
    def log(self, message: str) -> str:
        pass


class ConsoleLogger(ILogger):
    def log(self, message: str) -> str:
        return f"Logged: {message}"


class KeyedProcessor:
    def process(self) -> str:
        return "Processed Keyed"


@pytest.fixture
def container() -> Container:
    container = Container()
    container.register_singleton(ILogger, ConsoleLogger)
    container.register_transient("test", KeyedProcessor)
    return container


def test_injects_interface_dependency(container: Container):
    @inject(container)
    def process_data(logger: ILogger = Depends()) -> None:
        assert isinstance(logger, ConsoleLogger)

    process_data()


def test_injects_autowired_concrete_dependency(container: Container):
    @inject(container)
    def process_data(logger: ConsoleLogger = Depends()) -> None:
        assert isinstance(logger, ConsoleLogger)

    process_data()


def test_injects_keyed_dependency(container: Container):
    @inject(container)
    def process_data(
        keyed_processor: KeyedProcessor = Depends("test"),
    ) -> None:
        assert isinstance(keyed_processor, KeyedProcessor)

    process_data()


def test_preserves_regular_arguments(container: Container):
    text = "Report 42"

    @inject(container)
    def process_data(data: str, logger: ILogger = Depends()) -> None:
        assert isinstance(logger, ConsoleLogger)
        assert text == data

    process_data(text)


def test_preserves_explicit_default_arguments(container: Container):
    text = "Report 42"
    number = 10

    @inject(container)
    def process_data(
        data: str,
        logger: ILogger = Depends(),
        num: int = 1,
    ) -> None:
        assert isinstance(logger, ConsoleLogger)
        assert num == number
        assert text == data

    process_data(text, num=number)


def test_explicit_dependency_overrides_injection(container: Container):
    mock_logger = MagicMock(spec=ILogger)

    @inject(container)
    def calculate(
        number: int,
        logger: ILogger = Depends(),
    ) -> None:
        assert logger is mock_logger
        assert number == 10

    calculate(10, logger=mock_logger)


def test_injects_constructor_dependency(container: Container):
    class MyHandler:
        @inject(container)
        def __init__(self, logger: ILogger = Depends()) -> None:
            self.logger = logger

    handler = MyHandler()

    assert isinstance(handler.logger, ConsoleLogger)


def test_injects_constructor_with_regular_argument(container: Container):
    class MyHandler:
        @inject(container)
        def __init__(
            self,
            number: int,
            logger: ILogger = Depends(),
        ) -> None:
            self.number = number
            self.logger = logger

    handler = MyHandler(10)

    assert isinstance(handler.logger, ConsoleLogger)
    assert handler.number == 10


def test_decorators_can_use_different_containers():
    first = Container()
    second = Container()
    logger = ConsoleLogger()

    first.register_singleton(ILogger, ConsoleLogger)
    second.register_instance(ILogger, logger)

    @inject(first)
    def resolve_first(value: ILogger = Depends()) -> ILogger:
        return value

    @inject(second)
    def resolve_second(value: ILogger = Depends()) -> ILogger:
        return value

    assert resolve_first() is not logger
    assert resolve_second() is logger


def test_unkeyed_dependency_requires_type_hint(container: Container):
    def process_data(
        logger=Depends(),  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
    ) -> None:
        pass

    with pytest.raises(MissingTypeHintError):
        inject(container)(process_data)


def test_inject_can_use_scope():
    container = Container()
    container.register_scoped(ILogger, ConsoleLogger)

    with container.create_scope() as scope:

        @inject(scope)
        def resolve_logger(logger: ILogger = Depends()) -> ILogger:
            return logger

        first = resolve_logger()
        second = resolve_logger()

    assert first is second
