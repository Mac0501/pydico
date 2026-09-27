from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, cast

import pytest

from pydico import (
    CircularDependencyError,
    CollectionMaterializationError,
    InjectKey,
    ScopeRequiredError,
    ServiceCollection,
    ServiceProvider,
    UnsupportedTypeAnnotationError,
    inject,
)


class Handler:
    pass


class FirstHandler(Handler):
    pass


class SecondHandler(Handler):
    pass


def create_handlers() -> ServiceProvider:
    return (
        ServiceCollection()
        .add_transient(Handler, FirstHandler)
        .add_transient(Handler, SecondHandler)
        .build_service_provider()
    )


@pytest.mark.parametrize(
    ("annotation", "expected_type"),
    [
        (list[Handler], list),
        (tuple[Handler, ...], tuple),
        (set[Handler], set),
        (frozenset[Handler], frozenset),
        (Sequence[Handler], tuple),
        (Iterable[Handler], tuple),
    ],
)
def test_function_injection_materializes_supported_collections(
    annotation: object,
    expected_type: type[object],
) -> None:
    def action(handlers: object) -> object:
        return handlers

    action.__annotations__["handlers"] = annotation
    result = inject(create_handlers())(action)()

    assert type(result) is expected_type
    assert {type(handler) for handler in result} == {  # type: ignore[union-attr]
        FirstHandler,
        SecondHandler,
    }
    if expected_type in (list, tuple):
        assert [type(handler) for handler in result] == [  # type: ignore[union-attr]
            FirstHandler,
            SecondHandler,
        ]


def test_constructor_injection_resolves_a_list_in_registration_order() -> None:
    class Consumer:
        def __init__(self, handlers: object) -> None:
            self.handlers = handlers

    Consumer.__init__.__annotations__["handlers"] = list[Handler]
    provider = (
        ServiceCollection()
        .add_transient(Handler, FirstHandler)
        .add_transient(Handler, SecondHandler)
        .add_transient(Handler, FirstHandler)
        .add_transient(Consumer)
        .build_service_provider()
    )

    consumer = provider.get_service(Consumer)

    assert consumer is not None
    assert isinstance(consumer.handlers, list)
    handlers = cast(list[object], consumer.handlers)
    assert [type(handler) for handler in handlers] == [
        FirstHandler,
        SecondHandler,
        FirstHandler,
    ]


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (list[Handler], []),
        (tuple[Handler, ...], ()),
        (set[Handler], set()),
        (frozenset[Handler], frozenset()),
        (Sequence[Handler], ()),
        (Iterable[Handler], ()),
    ],
)
def test_missing_collection_registrations_produce_empty_values(
    annotation: object,
    expected: object,
) -> None:
    def action(handlers: object) -> object:
        return handlers

    action.__annotations__["handlers"] = annotation

    assert inject(ServiceCollection().build_service_provider())(action)() == expected


@pytest.mark.parametrize(
    ("annotation", "expected_type"),
    [
        (Annotated[list[Handler], InjectKey("commands")], list),
        (Annotated[tuple[Handler, ...], InjectKey("commands")], tuple),
        (Annotated[set[Handler], InjectKey("commands")], set),
        (Annotated[frozenset[Handler], InjectKey("commands")], frozenset),
        (Annotated[Sequence[Handler], InjectKey("commands")], tuple),
        (Annotated[Iterable[Handler], InjectKey("commands")], tuple),
    ],
)
def test_keyed_collection_injection_filters_registrations(
    annotation: object,
    expected_type: type[object],
) -> None:
    def action(handlers: object) -> object:
        return handlers

    action.__annotations__["handlers"] = annotation
    provider = (
        ServiceCollection()
        .add_transient(Handler, FirstHandler)
        .add_transient(Handler, SecondHandler, key="commands")
        .build_service_provider()
    )

    result = inject(provider)(action)()

    assert type(result) is expected_type
    assert len(result) == 1  # type: ignore[arg-type]
    assert isinstance(next(iter(result)), SecondHandler)  # type: ignore[arg-type]


def test_missing_keyed_collection_produces_an_empty_list() -> None:
    provider = ServiceCollection().add_transient(Handler).build_service_provider()

    @inject(provider)
    def action(
        handlers: Annotated[list[Handler], InjectKey("missing")],
    ) -> list[Handler]:
        return handlers

    assert action() == []


def test_collection_elements_preserve_transient_and_singleton_lifetimes() -> None:
    provider = (
        ServiceCollection()
        .add_transient(Handler, FirstHandler, key="transient")
        .add_singleton(Handler, SecondHandler, key="singleton")
        .build_service_provider()
    )

    @inject(provider)
    def transients(
        handlers: Annotated[list[Handler], InjectKey("transient")],
    ) -> list[Handler]:
        return handlers

    @inject(provider)
    def singletons(
        handlers: Annotated[list[Handler], InjectKey("singleton")],
    ) -> list[Handler]:
        return handlers

    first_transients, second_transients = transients(), transients()
    first_singletons, second_singletons = singletons(), singletons()

    assert first_transients is not second_transients
    assert first_transients[0] is not second_transients[0]
    assert first_singletons is not second_singletons
    assert first_singletons[0] is second_singletons[0]


def test_collection_elements_are_reused_only_within_their_scope() -> None:
    class Consumer:
        def __init__(self, handlers: object) -> None:
            self.handlers = handlers

    Consumer.__init__.__annotations__["handlers"] = list[Handler]
    provider = (
        ServiceCollection()
        .add_scoped(Handler, FirstHandler)
        .add_transient(Consumer)
        .build_service_provider()
    )

    with provider.create_scope() as first_scope:
        first = first_scope.get_service(Consumer)
        again = first_scope.get_service(Consumer)
        assert first is not None and again is not None
        assert first.handlers is not again.handlers
        first_handlers = cast(list[object], first.handlers)
        again_handlers = cast(list[object], again.handlers)
        assert first_handlers[0] is again_handlers[0]

    with provider.create_scope() as second_scope:
        second = second_scope.get_service(Consumer)
        assert second is not None
        second_handlers = cast(list[object], second.handlers)
        assert second_handlers[0] is not first_handlers[0]

    with pytest.raises(ScopeRequiredError):
        provider.get_service(Consumer)


@pytest.mark.parametrize(
    "annotation",
    [
        list[Any],
        list[Handler | None],
        list[list[Handler]],
        tuple[Handler],
        tuple[Handler, SecondHandler],
        list[Annotated[Handler, InjectKey("inner")]],
        dict[str, Handler],
    ],
)
def test_unsupported_collection_shapes_are_rejected(annotation: object) -> None:
    def action(handlers: object) -> object:
        return handlers

    action.__annotations__["handlers"] = annotation

    with pytest.raises(UnsupportedTypeAnnotationError):
        inject(ServiceCollection().build_service_provider())(action)()


@dataclass
class UnhashableHandler(Handler):
    name: str


@pytest.mark.parametrize(
    ("annotation", "collection_type"),
    [(set[Handler], set), (frozenset[Handler], frozenset)],
)
def test_unhashable_services_raise_collection_materialization_error(
    annotation: object,
    collection_type: type[object],
) -> None:
    instance = UnhashableHandler("handler")
    provider = (
        ServiceCollection().add_instance(Handler, instance).build_service_provider()
    )

    def action(handlers: object) -> object:
        return handlers

    action.__annotations__["handlers"] = annotation

    with pytest.raises(CollectionMaterializationError) as caught:
        inject(provider)(action)()

    assert caught.value.target is action
    assert caught.value.parameter_name == "handlers"
    assert caught.value.collection_type is collection_type
    assert isinstance(caught.value.__cause__, TypeError)


def test_collection_dependency_participates_in_cycle_detection() -> None:
    class CompositeHandler(Handler):
        def __init__(self, handlers: object) -> None:
            self.handlers = handlers

    CompositeHandler.__init__.__annotations__["handlers"] = list[Handler]
    provider = (
        ServiceCollection()
        .add_transient(Handler, CompositeHandler)
        .build_service_provider()
    )

    with pytest.raises(CircularDependencyError):
        provider.get_service(Handler)


def test_explicit_collection_and_collection_default_are_not_injected() -> None:
    provider = ServiceCollection().build_service_provider()
    explicit = [Handler()]

    @inject(provider)
    def action(
        handlers: list[Handler],
        optional: list[Handler] | None = None,
    ) -> tuple[list[Handler], list[Handler] | None]:
        return handlers, optional

    assert action(explicit) == (explicit, None)


def test_bare_list_remains_a_single_service_annotation() -> None:
    instance: list[object] = []
    provider = ServiceCollection().add_instance(list, instance).build_service_provider()

    def action(value: object) -> object:
        return value

    action.__annotations__["value"] = list
    wrapped = inject(provider)(action)

    assert wrapped() is instance


def test_builtin_services_are_not_implicitly_collection_registrations() -> None:
    provider = ServiceCollection().build_service_provider()

    @inject(provider)
    def action(providers: list[ServiceProvider]) -> list[ServiceProvider]:
        return providers

    assert action() == []
