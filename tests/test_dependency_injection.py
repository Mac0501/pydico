from __future__ import annotations

from typing import Any

import pytest

import pydico._dependencies as dependencies_module
from pydico import ServiceCollection, inject
from pydico.exceptions import (
    InjectionError,
    MissingTypeAnnotationError,
    ServiceNotRegisteredError,
    UnsupportedTypeAnnotationError,
)

# The missing annotations in this module are deliberate runtime error cases.
# pyright: reportMissingParameterType=false, reportUnknownParameterType=false
# pyright: reportUnknownVariableType=false


class Dependency:
    pass


class MissingDependency:
    pass


def test_constructor_supports_positional_only_and_keyword_only_dependencies() -> None:
    class Consumer:
        def __init__(self, first: Dependency, /, *, second: Dependency) -> None:
            self.first = first
            self.second = second

    provider = (
        ServiceCollection()
        .add_singleton(Dependency)
        .add_transient(Consumer)
        .build_service_provider()
    )

    consumer = provider.get_service(Consumer)

    assert consumer is not None
    assert consumer.first is consumer.second is provider.get_service(Dependency)


def test_constructor_and_function_report_same_missing_annotation_context() -> None:
    class Consumer:
        def __init__(self, dependency) -> None:
            self.dependency = dependency

    def action(dependency):
        return dependency

    provider = ServiceCollection().add_transient(Consumer).build_service_provider()

    with pytest.raises(MissingTypeAnnotationError) as constructor_error:
        provider.get_service(Consumer)
    with pytest.raises(MissingTypeAnnotationError) as function_error:
        inject(provider)(action)()

    assert constructor_error.value.target is Consumer
    assert function_error.value.target is action
    assert constructor_error.value.parameter_name == "dependency"
    assert function_error.value.parameter_name == "dependency"


@pytest.mark.parametrize(
    "annotation",
    [Any, Dependency | None],
)
def test_constructor_and_function_reject_the_same_ambiguous_annotations(
    annotation: object,
) -> None:
    class Consumer:
        def __init__(self, dependency: object) -> None:
            self.dependency = dependency

    def action(dependency: object):
        return dependency

    Consumer.__init__.__annotations__["dependency"] = annotation
    action.__annotations__["dependency"] = annotation
    provider = ServiceCollection().add_transient(Consumer).build_service_provider()

    with pytest.raises(UnsupportedTypeAnnotationError) as constructor_error:
        provider.get_service(Consumer)
    with pytest.raises(UnsupportedTypeAnnotationError) as function_error:
        inject(provider)(action)()

    assert constructor_error.value.annotation == annotation
    assert function_error.value.annotation == annotation


def test_constructor_and_function_report_missing_registration_context() -> None:
    class Consumer:
        def __init__(self, dependency: MissingDependency) -> None:
            self.dependency = dependency

    def action(dependency: MissingDependency):
        return dependency

    provider = ServiceCollection().add_transient(Consumer).build_service_provider()

    with pytest.raises(ServiceNotRegisteredError) as constructor_error:
        provider.get_service(Consumer)
    with pytest.raises(ServiceNotRegisteredError) as function_error:
        inject(provider)(action)()

    for error, target in (
        (constructor_error.value, Consumer),
        (function_error.value, action),
    ):
        assert error.service_type is MissingDependency
        assert error.target is target
        assert error.parameter_name == "dependency"


def test_constructor_and_function_resolve_forward_annotations() -> None:
    class Consumer:
        def __init__(self, dependency: "Dependency") -> None:
            self.dependency = dependency

    def action(dependency: "Dependency"):
        return dependency

    provider = (
        ServiceCollection()
        .add_singleton(Dependency)
        .add_transient(Consumer)
        .build_service_provider()
    )

    consumer = provider.get_service(Consumer)
    assert consumer is not None
    assert consumer.dependency is provider.get_service(Dependency)
    assert inject(provider)(action)() is provider.get_service(Dependency)


def test_annotation_resolution_errors_preserve_the_original_cause() -> None:
    class Consumer:
        def __init__(self, dependency: object) -> None:
            self.dependency = dependency

    Consumer.__init__.__annotations__["dependency"] = "UndefinedDependency"

    provider = ServiceCollection().add_transient(Consumer).build_service_provider()

    with pytest.raises(InjectionError, match="annotations") as caught:
        provider.get_service(Consumer)

    assert isinstance(caught.value.__cause__, NameError)


def test_explicit_arguments_and_defaults_are_not_analyzed() -> None:
    def action(explicit, optional: list[Dependency] | None = None):
        return explicit, optional

    wrapped = inject(ServiceCollection().build_service_provider())(action)

    assert wrapped("value") == ("value", None)


def test_type_hints_are_cached_per_constructor_and_decorated_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = dependencies_module.get_type_hints
    calls: list[object] = []

    def counting_get_type_hints(target: object, *args: Any, **kwargs: Any):
        calls.append(target)
        return original(target, *args, **kwargs)

    monkeypatch.setattr(dependencies_module, "get_type_hints", counting_get_type_hints)

    class Consumer:
        def __init__(self, dependency: Dependency) -> None:
            self.dependency = dependency

    def action(dependency: Dependency):
        return dependency

    provider = (
        ServiceCollection()
        .add_singleton(Dependency)
        .add_transient(Consumer)
        .build_service_provider()
    )
    wrapped = inject(provider)(action)

    provider.get_service(Consumer)
    provider.get_service(Consumer)
    wrapped()
    wrapped()

    assert calls.count(Consumer.__init__) == 1
    assert calls.count(action) == 1
