from abc import ABC, abstractmethod
from unittest.mock import MagicMock

import pytest

from pydico.core.container import Container
from pydico.core.depends import Depends
from pydico.decorator import inject


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


@pytest.fixture(autouse=True, scope="module")
def clean_container_storage():
    Container.add_singleton(ILogger, ConsoleLogger)
    Container.add_transient("test", KeyedProcessor)


def test_inject_decorator_01():

    @inject
    def process_data(logger: ILogger = Depends[ILogger]):
        assert isinstance(logger, ConsoleLogger)
        return

    process_data()


def test_inject_decorator_02():

    @inject
    def process_data(logger: ConsoleLogger = Depends[ConsoleLogger]):
        assert isinstance(logger, ConsoleLogger)
        return

    process_data()


def test_inject_decorator_03():

    @inject
    def process_data(keyed_processor: KeyedProcessor = Depends[KeyedProcessor, "test"]):
        assert isinstance(keyed_processor, KeyedProcessor)
        return

    process_data()


def test_inject_decorator_04():

    text = "Report 42"

    @inject
    def process_data(data: str, logger: ILogger = Depends[ILogger]):
        assert isinstance(logger, ConsoleLogger)
        assert text == data
        return

    process_data(text)


def test_inject_decorator_05():

    text = "Report 42"
    number = 10

    @inject
    def process_data(data: str, logger: ILogger = Depends[ILogger], num: int = 1):
        assert isinstance(logger, ConsoleLogger)
        assert num == number
        assert text == data
        return

    process_data(text, num=number)


def test_inject_decorator_06():

    mock_logger = MagicMock(spec=ILogger)
    mock_logger.log.return_value = "Mock Log"

    number1 = 10
    number2 = 20

    @inject
    def calculate(a: int, logger: ILogger = Depends[ILogger], b: int = number2):
        assert logger is mock_logger
        assert a is number1
        assert b is number2
        return

    calculate(a=number1, logger=mock_logger)


def test_inject_decorator_07():

    class MyHandler:

        @inject
        def __init__(self, logger: ILogger = Depends[ILogger]) -> None:
            self.logger = logger

    handler = MyHandler()
    assert isinstance(handler.logger, ILogger)


def test_inject_decorator_08():
    number = 10

    class MyHandler:

        @inject
        def __init__(self, num: int, logger: ILogger = Depends[ILogger]) -> None:
            self.num = num
            self.logger = logger

    handler = MyHandler(number)
    assert isinstance(handler.logger, ILogger)
    assert handler.num == number
