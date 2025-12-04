from abc import ABC, abstractmethod
from unittest.mock import MagicMock, patch

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


class UserService:
    def __init__(self, logger: ILogger):
        self.logger = logger

    def greet(self, name: str) -> str:
        return self.logger.log(f"Greeting {name}")


class ConfigService:
    def get_setting(self) -> str:
        return "Production"


@pytest.fixture(autouse=True)
def clean_container_storage():
    yield
    Container._transients.clear()  # pyright: ignore[reportPrivateUsage]
    Container._singletons.clear()  # pyright: ignore[reportPrivateUsage]
    Container._singleton_instances.clear()  # pyright: ignore[reportPrivateUsage]
    Container._keyed_transients.clear()  # pyright: ignore[reportPrivateUsage]
    Container._keyed_singletons.clear()  # pyright: ignore[reportPrivateUsage]
    Container._keyed_singleton_instances.clear()  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
def registered_container():
    Container.add_singleton(ILogger, ConsoleLogger)
    Container.add_singleton_self(ConfigService)
    return Container


def test_01_inject_resolves_dependency_correctly(registered_container: Container):

    @inject
    def process_data(
        data: str,
        config: ConfigService = Depends[ConfigService],
    ):
        setting = config.get_setting()
        return f"Processing {data} in {setting} mode."

    result = process_data("Report 42")

    assert isinstance(registered_container.get(ConfigService), ConfigService)
    assert result == "Processing Report 42 in Production mode."


def test_02_inject_uses_explicitly_passed_argument():

    mock_logger = MagicMock(spec=ILogger)
    mock_logger.log.return_value = "Mock Log"

    @inject
    def calculate(a: int, logger: ILogger = Depends[ILogger], b: int = 10) -> str:
        return f"Result: {a + b} | {logger.log('Called')}"

    result = calculate(a=5, logger=mock_logger)

    assert result == "Result: 15 | Mock Log"
    mock_logger.log.assert_called_once_with("Called")


def test_03_inject_with_mixed_dependencies_and_regular_args(
    registered_container: Container,
):

    @inject
    def send_notification(
        message: str,
        target: str,
        logger: ILogger = Depends[ILogger],
        priority: str = "low",
    ) -> str:
        log_msg = logger.log(f"Sending to {target} with {priority} priority.")
        return f"{log_msg} Body: {message}"

    result = send_notification("Update required", "user@example.com", priority="high")

    assert (
        result
        == "Logged: Sending to user@example.com with high priority. Body: Update required"
    )


def test_04_inject_handles_dependencies_in_class_methods():

    Container.add_singleton_self(ConfigService)

    class MyHandler:
        @inject
        def handle_request(self, config: ConfigService = Depends[ConfigService]) -> str:
            return f"Handled by {self.__class__.__name__} with {config.get_setting()}"

    handler = MyHandler()
    result = handler.handle_request()

    assert result == "Handled by MyHandler with Production"


@patch.object(Container, "get", side_effect=Container.get)
def test_05_inject_avoids_unnecessary_calls(
    mock_get: MagicMock, registered_container: Container
):
    class TestDep:
        pass

    Container.add_singleton_self(TestDep)

    @inject
    def func_to_test(
        a: int,
        dep_c: ConfigService = Depends[ConfigService],
        dep_t: TestDep = Depends[TestDep],
    ):
        pass

    func_to_test(a=1, dep_c=ConfigService())

    assert mock_get.call_count == 1
    mock_get.assert_called_once_with(TestDep)
