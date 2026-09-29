import inspect
from typing import Any

import pytest

from pydico import inject
from pydico.collection import ServiceCollection
from pydico.exceptions import (
    InjectionError,
    MissingTypeAnnotationError,
    NoActiveScopeError,
    ServiceNotRegisteredError,
    UnsupportedTypeAnnotationError,
)


class Dependency:
    pass


def test_explicit_resolver_and_lifetimes() -> None:
    for lifetime in ("add_transient", "add_singleton"):
        services = ServiceCollection()
        getattr(services, lifetime)(Dependency)

        @inject(services.build_service_provider())
        def action(dependency: Dependency) -> Dependency:
            return dependency

        first, second = action(), action()
        assert isinstance(first, Dependency)
        assert (first is second) == (lifetime == "add_singleton")


def test_explicit_arguments_defaults_and_variadic_arguments() -> None:
    @inject
    def action(
        dependency: Dependency, /, *items: int, flag: bool = True, **extras: int
    ):
        return dependency, items, flag, extras

    assert action(None, 1, 2, flag=False, extra=3) == (
        None,
        (1, 2),
        False,
        {"extra": 3},
    )

    @inject()
    def defaults(dependency: Dependency | None = None):
        return dependency

    assert defaults() is None


def test_positional_only_and_keyword_only_injection() -> None:
    provider = ServiceCollection().add_singleton(Dependency).build_service_provider()

    @inject(provider)
    def action(first: Dependency, /, label: str = "default", *, second: Dependency):
        return first, label, second

    first, label, second = action()
    assert first is second is provider.get_service(Dependency)
    assert label == "default"


def test_invalid_call_fails_before_factory_execution() -> None:
    calls = []
    provider = (
        ServiceCollection()
        .add_transient(Dependency, factory=lambda _: calls.append(1) or Dependency())
        .build_service_provider()
    )

    @inject(provider)
    def action(dependency: Dependency):
        return dependency

    with pytest.raises(TypeError):
        action(Dependency(), dependency=Dependency())
    with pytest.raises(TypeError):
        action(unexpected=1)
    assert calls == []


def test_methods_and_metadata() -> None:
    provider = ServiceCollection().add_singleton(Dependency).build_service_provider()

    class Consumer:
        @inject(provider)
        def method(self, dependency: Dependency):
            """Original documentation."""
            return self, dependency

        @classmethod
        @inject(provider)
        def class_method(cls, dependency: Dependency):
            return cls, dependency

    consumer = Consumer()
    assert consumer.method() == (consumer, provider.get_service(Dependency))
    assert Consumer.class_method() == (Consumer, provider.get_service(Dependency))
    assert Consumer.method.__name__ == "method"
    assert Consumer.method.__doc__ == "Original documentation."
    assert tuple(inspect.signature(Consumer.method).parameters) == (
        "self",
        "dependency",
    )
    with pytest.raises(TypeError):
        Consumer.method()


@pytest.mark.parametrize("annotation", [None, Dependency | None, Any])
def test_unsupported_or_missing_annotations(annotation: object) -> None:
    def action(dependency: object):
        return dependency

    action.__annotations__.clear()
    if annotation is not None:
        action.__annotations__["dependency"] = annotation
    wrapped = inject(ServiceCollection().build_service_provider())(action)
    error_type = (
        MissingTypeAnnotationError
        if annotation is None
        else UnsupportedTypeAnnotationError
    )
    with pytest.raises(error_type, match="dependency"):
        wrapped()
    assert wrapped("explicit") == "explicit"


def test_missing_resolver_and_registration() -> None:
    @inject
    def action(dependency: Dependency):
        return dependency

    with pytest.raises(NoActiveScopeError, match="no service scope is active"):
        action()
    wrapped = inject(ServiceCollection().build_service_provider())(
        inspect.unwrap(action)
    )
    with pytest.raises(
        ServiceNotRegisteredError, match="No registration was found.*dependency"
    ):
        wrapped()


def test_forward_annotations_and_annotation_errors() -> None:
    provider = ServiceCollection().add_singleton(Dependency).build_service_provider()

    @inject(provider)
    def action(dependency: "Dependency"):
        return dependency

    assert isinstance(action(), Dependency)

    def invalid(dependency: object):
        return dependency

    invalid.__annotations__["dependency"] = "UndefinedDependency"
    with pytest.raises(InjectionError, match="annotations") as caught:
        inject(provider)(invalid)()
    assert isinstance(caught.value.__cause__, NameError)


def test_factory_and_function_errors_propagate() -> None:
    error = ValueError("original")

    def fail(_):
        raise error

    provider = (
        ServiceCollection()
        .add_transient(Dependency, factory=fail)
        .build_service_provider()
    )

    @inject(provider)
    def action(dependency: Dependency):
        raise error

    for arguments in ((), (Dependency(),)):
        with pytest.raises(ValueError) as caught:
            action(*arguments)
        assert caught.value is error


def test_generators_are_rejected() -> None:
    def generator():
        yield 1

    async def async_generator():
        yield 1

    for function in (generator, async_generator):
        with pytest.raises(InjectionError, match="generator"):
            inject(function)


def test_invalid_decorator_target_is_rejected() -> None:
    with pytest.raises(TypeError, match="function or a ServiceResolver"):
        inject(42)  # pyright: ignore[reportArgumentType, reportCallIssue]
