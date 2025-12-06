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


class AbstractTest(ABC):
    @abstractmethod
    def required_method(self) -> None:
        pass


@pytest.fixture(autouse=True, scope="module")
def clean_container_storage():
    Container.add_singleton(ILogger, ConsoleLogger)
    Container.add_keyed_transient("test", KeyedProcessor)


def test_01_inject_resolves_dependency_correctly():

    @inject
    def process_data(
        data: str,
        logger: ILogger = Depends[ILogger],
    ):
        assert isinstance(logger, ConsoleLogger)
        return data

    process_data("Report 42")


def test_02_inject_uses_explicitly_passed_argument():

    mock_logger = MagicMock(spec=ILogger)
    mock_logger.log.return_value = "Mock Log"

    @inject
    def calculate(a: int, logger: ILogger = Depends[ILogger], b: int = 10) -> str:
        assert logger is mock_logger
        return f"{a}"

    calculate(a=5, logger=mock_logger)


def test_03_inject_with_mixed_dependencies_and_regular_args():

    @inject
    def send_notification(
        message: str,
        target: str,
        logger: ILogger = Depends[ILogger],
        priority: str = "low",
    ) -> str:
        assert isinstance(logger, ConsoleLogger)
        log_msg = logger.log(f"Sending to {target} with {priority} priority.")
        return f"{log_msg} Body: {message}"

    send_notification("Update required", "user@example.com", priority="high")


def test_04_inject_handles_dependencies_in_class_init():

    class MyHandler:

        @inject
        def __init__(self, logger: ILogger = Depends[ILogger]) -> None:
            self.logger = logger

    handler = MyHandler()
    assert isinstance(handler.logger, ILogger)


def test_05_inject_avoids_unnecessary_calls():

    @inject
    def func_to_test(
        a: int, keyed_processor: KeyedProcessor = Depends[KeyedProcessor, "test"]
    ):
        assert isinstance(keyed_processor, KeyedProcessor)

    func_to_test(10)
