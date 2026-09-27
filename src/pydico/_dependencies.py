"""Shared dependency analysis for constructor and function injection."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from threading import RLock
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from pydico.exceptions import (
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
            service_type, key = _parse_dependency_annotation(
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
) -> tuple[type[object], Hashable | None]:
    service_type = annotation
    key: Hashable | None = None

    if get_origin(annotation) is Annotated:
        service_type, *metadata = get_args(annotation)
        inject_keys = tuple(
            item.key for item in metadata if isinstance(item, InjectKey)
        )
        if len(inject_keys) > 1:
            raise ConflictingInjectKeyError(target, parameter_name, inject_keys)
        if inject_keys:
            key = inject_keys[0]

    if not isinstance(service_type, type) or service_type is Any:
        raise UnsupportedTypeAnnotationError(target, parameter_name, annotation)

    return service_type, key


def resolve_dependency(
    request: DependencyRequest,
    *,
    resolver: ServiceResolver,
    target: object,
) -> object:
    """Resolve one request and turn a missing registration into an injection error."""
    dependency = resolver.get_service(request.service_type, key=request.key)
    if dependency is None:
        raise ServiceNotRegisteredError(
            request.service_type,
            key=request.key,
            target=target,
            parameter_name=request.parameter_name,
        )
    return dependency
