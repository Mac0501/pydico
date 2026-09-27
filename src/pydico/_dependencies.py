"""Shared dependency analysis for constructor and function injection."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from threading import RLock
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from pydico.exceptions import (
    CollectionMaterializationError,
    ConflictingInjectKeyError,
    InjectionError,
    MissingTypeAnnotationError,
    ServiceNotRegisteredError,
    UnsupportedTypeAnnotationError,
)
from pydico.metadata import InjectKey
from pydico.resolver import ServiceResolver


@dataclass(frozen=True, slots=True)
class DependencyRequest:
    """A single, unambiguous dependency required by a callable."""

    parameter_name: str
    service_type: type[object]
    positional_only: bool
    key: Hashable | None
    collection_kind: CollectionKind | None


class CollectionKind(Enum):
    """Internal representation of a requested collection shape."""

    LIST = auto()
    TUPLE = auto()
    SET = auto()
    FROZENSET = auto()


class DependencyPlan:
    """Lazily parse and cache the injectable parameters of a callable."""

    def __init__(
        self,
        callable_target: Callable[..., object],
        *,
        error_target: object | None = None,
    ) -> None:
        self.callable_target = callable_target
        self.error_target = callable_target if error_target is None else error_target
        self.signature = inspect.signature(callable_target)
        self._type_hints: dict[str, Any] | None = None
        self._type_hints_lock = RLock()

    def required_parameters(self) -> tuple[inspect.Parameter, ...]:
        """Return required parameters that are candidates for injection."""
        return tuple(
            parameter
            for parameter in self.signature.parameters.values()
            if parameter.name not in ("self", "cls")
            and parameter.default is inspect.Parameter.empty
            and parameter.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        )

    def requests(
        self, parameters: Sequence[inspect.Parameter]
    ) -> tuple[DependencyRequest, ...]:
        """Validate parameters and convert them to dependency requests."""
        if not parameters:
            return ()

        type_hints = self._get_type_hints()
        requests: list[DependencyRequest] = []
        for parameter in parameters:
            if parameter.name not in type_hints:
                raise MissingTypeAnnotationError(self.error_target, parameter.name)

            annotation = type_hints[parameter.name]
            service_type, key, collection_kind = _parse_dependency_annotation(
                annotation,
                target=self.error_target,
                parameter_name=parameter.name,
            )

            requests.append(
                DependencyRequest(
                    parameter_name=parameter.name,
                    service_type=service_type,
                    positional_only=parameter.kind is inspect.Parameter.POSITIONAL_ONLY,
                    key=key,
                    collection_kind=collection_kind,
                )
            )
        return tuple(requests)

    def _get_type_hints(self) -> dict[str, Any]:
        with self._type_hints_lock:
            if self._type_hints is None:
                try:
                    self._type_hints = get_type_hints(
                        self.callable_target, include_extras=True
                    )
                except Exception as error:
                    name = getattr(
                        self.error_target, "__qualname__", repr(self.error_target)
                    )
                    raise InjectionError(
                        f"Cannot resolve type annotations for {name}."
                    ) from error
            return self._type_hints


def _parse_dependency_annotation(
    annotation: object,
    *,
    target: object,
    parameter_name: str,
) -> tuple[type[object], Hashable | None, CollectionKind | None]:
    dependency_annotation = annotation
    key: Hashable | None = None

    if get_origin(annotation) is Annotated:
        dependency_annotation, *metadata = get_args(annotation)
        inject_keys = tuple(
            item.key for item in metadata if isinstance(item, InjectKey)
        )
        if len(inject_keys) > 1:
            raise ConflictingInjectKeyError(target, parameter_name, inject_keys)
        if inject_keys:
            key = inject_keys[0]

    origin: Any = get_origin(dependency_annotation)
    collection_kind = _collection_kind(origin)
    if collection_kind is not None:
        arguments = get_args(dependency_annotation)
        if origin is tuple:
            valid_shape = len(arguments) == 2 and arguments[1] is Ellipsis
        else:
            valid_shape = len(arguments) == 1

        if not valid_shape:
            raise UnsupportedTypeAnnotationError(target, parameter_name, annotation)

        service_type = arguments[0]
        if not isinstance(service_type, type) or service_type is Any:
            raise UnsupportedTypeAnnotationError(target, parameter_name, annotation)
        return service_type, key, collection_kind

    if not isinstance(dependency_annotation, type) or dependency_annotation is Any:
        raise UnsupportedTypeAnnotationError(target, parameter_name, annotation)

    return dependency_annotation, key, None


def _collection_kind(origin: Any) -> CollectionKind | None:
    if origin is list:
        return CollectionKind.LIST
    if origin is tuple or origin is Sequence or origin is Iterable:
        return CollectionKind.TUPLE
    if origin is set:
        return CollectionKind.SET
    if origin is frozenset:
        return CollectionKind.FROZENSET
    return None


def resolve_dependency(
    request: DependencyRequest,
    *,
    resolver: ServiceResolver,
    target: object,
) -> object:
    """Resolve one request and turn a missing registration into an injection error."""
    if request.collection_kind is not None:
        services = resolver.get_services(request.service_type, key=request.key)
        try:
            return _materialize_collection(services, request.collection_kind)
        except TypeError as error:
            raise CollectionMaterializationError(
                target,
                request.parameter_name,
                _collection_type(request.collection_kind),
            ) from error

    dependency = resolver.get_service(request.service_type, key=request.key)
    if dependency is None:
        raise ServiceNotRegisteredError(
            request.service_type,
            key=request.key,
            target=target,
            parameter_name=request.parameter_name,
        )
    return dependency


def _materialize_collection(
    services: tuple[object, ...], kind: CollectionKind
) -> object:
    if kind is CollectionKind.LIST:
        return list(services)
    if kind is CollectionKind.TUPLE:
        return services
    if kind is CollectionKind.SET:
        return set(services)
    return frozenset(services)


def _collection_type(kind: CollectionKind) -> type[object]:
    if kind is CollectionKind.LIST:
        return list
    if kind is CollectionKind.TUPLE:
        return tuple
    if kind is CollectionKind.SET:
        return set
    return frozenset
