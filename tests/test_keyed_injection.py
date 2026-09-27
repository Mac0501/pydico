from __future__ import annotations

import asyncio
from typing import Annotated

import pytest

from pydico import (
    ConflictingInjectKeyError,
    InjectKey,
    ServiceCollection,
    ServiceNotRegisteredError,
    ServiceProvider,
    UnsupportedTypeAnnotationError,
    inject,
)


class Logger:
    pass


class ConsoleLogger(Logger):
    pass


class FileLogger(Logger):
    pass


class KeyedConsumer:
    def __init__(
        self,
        logger: Annotated[Logger, InjectKey("file")],
    ) -> None:
        self.logger = logger


class ScopedDependency:
    pass


class ScopedConsumer:
    def __init__(
        self,
        dependency: Annotated[ScopedDependency, InjectKey("primary")],
    ) -> None:
        self.dependency = dependency


def create_provider() -> ServiceProvider:
    return (
        ServiceCollection()
        .add_singleton(Logger, ConsoleLogger)
        .add_singleton(Logger, ConsoleLogger, key="console")
        .add_singleton(Logger, FileLogger, key="file")
        .add_transient(KeyedConsumer)
        .build_service_provider()
    )


def test_constructor_injection_selects_keyed_registration() -> None:
    provider = create_provider()

    consumer = provider.get_service(KeyedConsumer)

    assert consumer is not None
    assert consumer.logger is provider.get_service(Logger, key="file")
    assert isinstance(consumer.logger, FileLogger)


def test_function_injection_keeps_keyed_and_unkeyed_services_separate() -> None:
    provider = create_provider()

    @inject(provider)
    def action(
        default: Logger,
        console: Annotated[Logger, InjectKey("console")],
        file: Annotated[Logger, InjectKey("file")],
    ) -> tuple[Logger, Logger, Logger]:
        return default, console, file

    default, console, file = action()

    assert default is provider.get_service(Logger)
    assert console is provider.get_service(Logger, key="console")
    assert file is provider.get_service(Logger, key="file")
    assert default is not console
    assert console is not file


def test_keyed_function_injection_supports_async_functions() -> None:
    provider = create_provider()

    @inject(provider)
    async def action(
        logger: Annotated[Logger, InjectKey("file")],
    ) -> Logger:
        return logger

    assert asyncio.run(action()) is provider.get_service(Logger, key="file")


def test_keyed_scoped_dependency_is_isolated_between_scopes() -> None:
    provider = (
        ServiceCollection()
        .add_scoped(ScopedDependency, key="primary")
        .add_transient(ScopedConsumer)
        .build_service_provider()
    )

    with provider.create_scope() as first:
        first_consumer = first.get_service(ScopedConsumer)
        again = first.get_service(ScopedConsumer)
        assert first_consumer is not None and again is not None
        assert first_consumer.dependency is again.dependency

    with provider.create_scope() as second:
        second_consumer = second.get_service(ScopedConsumer)
        assert second_consumer is not None
        assert second_consumer.dependency is not first_consumer.dependency


def test_keyed_transient_and_singleton_keep_their_lifetimes() -> None:
    provider = (
        ServiceCollection()
        .add_transient(Logger, ConsoleLogger, key="transient")
        .add_singleton(Logger, FileLogger, key="singleton")
        .build_service_provider()
    )

    @inject(provider)
    def transient(
        logger: Annotated[Logger, InjectKey("transient")],
    ) -> Logger:
        return logger

    @inject(provider)
    def singleton(
        logger: Annotated[Logger, InjectKey("singleton")],
    ) -> Logger:
        return logger

    assert transient() is not transient()
    assert singleton() is singleton()


def test_missing_keyed_registration_exposes_complete_context() -> None:
    def action(
        logger: Annotated[Logger, InjectKey("missing")],
    ) -> Logger:
        return logger

    provider = ServiceCollection().add_singleton(Logger).build_service_provider()

    with pytest.raises(ServiceNotRegisteredError) as caught:
        inject(provider)(action)()

    assert caught.value.service_type is Logger
    assert caught.value.key == "missing"
    assert caught.value.target is action
    assert caught.value.parameter_name == "logger"
    assert "key='missing'" in str(caught.value)


def test_multiple_inject_keys_are_rejected_for_constructor_and_function() -> None:
    annotation = Annotated[Logger, InjectKey("first"), InjectKey("second")]

    class Consumer:
        def __init__(self, logger: Logger) -> None:
            self.logger = logger

    def action(logger: Logger) -> Logger:
        return logger

    Consumer.__init__.__annotations__["logger"] = annotation
    action.__annotations__["logger"] = annotation
    provider = ServiceCollection().add_transient(Consumer).build_service_provider()

    with pytest.raises(ConflictingInjectKeyError) as constructor_error:
        provider.get_service(Consumer)
    with pytest.raises(ConflictingInjectKeyError) as function_error:
        inject(provider)(action)()

    assert constructor_error.value.keys == ("first", "second")
    assert function_error.value.keys == ("first", "second")
    assert constructor_error.value.target is Consumer
    assert function_error.value.target is action


def test_unrelated_annotated_metadata_is_ignored() -> None:
    provider = create_provider()

    @inject(provider)
    def action(
        logger: Annotated[Logger, "external metadata", InjectKey("file")],
    ) -> Logger:
        return logger

    assert action() is provider.get_service(Logger, key="file")


def test_annotated_generic_base_remains_unsupported() -> None:
    provider = ServiceCollection().build_service_provider()

    @inject(provider)
    def action(
        loggers: Annotated[list[list[Logger]], InjectKey("file")],
    ) -> list[list[Logger]]:
        return loggers

    with pytest.raises(UnsupportedTypeAnnotationError):
        action()


def test_keyed_builtin_resolver_requires_explicit_registration() -> None:
    provider = ServiceCollection().build_service_provider()

    @inject(provider)
    def action(
        dependency: Annotated[ServiceProvider, InjectKey("custom")],
    ) -> ServiceProvider:
        return dependency

    with pytest.raises(ServiceNotRegisteredError) as caught:
        action()

    assert caught.value.key == "custom"


def test_inject_key_rejects_reserved_and_unhashable_keys() -> None:
    with pytest.raises(ValueError, match="non-None"):
        InjectKey(None)
    with pytest.raises(TypeError, match="hashable"):
        InjectKey([])  # pyright: ignore[reportArgumentType]
