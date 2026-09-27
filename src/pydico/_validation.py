"""Static validation of service descriptors without creating services."""

from __future__ import annotations

from collections.abc import Sequence

from pydico._dependencies import DependencyPlan, DependencyRequest
from pydico.descriptors import ServiceDescriptor
from pydico.exceptions import (
    CircularDependencyError,
    InjectionError,
    PydicoError,
    ResolutionError,
    ServiceNotRegisteredError,
)
from pydico.identifiers import ServiceIdentifier
from pydico.validation import ValidationIssue


def validate_descriptors(
    descriptors: Sequence[ServiceDescriptor[object]],
) -> tuple[ValidationIssue, ...]:
    """Return deterministic issues from every statically visible graph."""
    return _ServiceGraphValidator(descriptors).validate()


class _ServiceGraphValidator:
    def __init__(self, descriptors: Sequence[ServiceDescriptor[object]]) -> None:
        self._descriptors = tuple(descriptors)
        self._issues: list[ValidationIssue] = []
        self._processed: set[int] = set()
        self._stack: list[ServiceDescriptor[object]] = []
        self._plans: dict[type[object], DependencyPlan] = {}
        self._reported_cycles: set[tuple[int, ...]] = set()

    def validate(self) -> tuple[ValidationIssue, ...]:
        for descriptor in self._descriptors:
            self._validate_descriptor(descriptor)
        return tuple(self._issues)

    def _validate_descriptor(self, descriptor: ServiceDescriptor[object]) -> None:
        descriptor_id = id(descriptor)
        if descriptor_id in self._processed:
            return

        for index, active in enumerate(self._stack):
            if active is descriptor:
                cycle_descriptors = (*self._stack[index:], descriptor)
                cycle_key = _normalize_cycle(
                    tuple(id(item) for item in cycle_descriptors[:-1])
                )
                if cycle_key in self._reported_cycles:
                    return
                self._reported_cycles.add(cycle_key)
                cycle = tuple(
                    ServiceIdentifier(item.service_type, item.key)
                    for item in cycle_descriptors
                )
                self._issues.append(
                    ValidationIssue(
                        CircularDependencyError(cycle),
                        (
                            *self._current_path(),
                            ServiceIdentifier(descriptor.service_type, descriptor.key),
                        ),
                    )
                )
                return

        self._stack.append(descriptor)
        try:
            if descriptor.factory is not None or descriptor.instance is not None:
                return

            implementation_type = descriptor.implementation_type
            if implementation_type is None:
                self._add_issue(
                    ResolutionError(
                        f"Service type {descriptor.service_type} has no "
                        "implementation, factory, or instance."
                    )
                )
                return

            plan = self._get_plan(implementation_type)
            if plan is None:
                return

            for parameter in plan.required_parameters():
                try:
                    request = plan.requests((parameter,))[0]
                except PydicoError as error:
                    self._add_issue(error)
                    if type(error) is InjectionError and error.__cause__ is not None:
                        break
                    continue
                self._validate_request(request, implementation_type)
        finally:
            self._stack.pop()
            self._processed.add(descriptor_id)

    def _get_plan(self, implementation_type: type[object]) -> DependencyPlan | None:
        plan = self._plans.get(implementation_type)
        if plan is not None:
            return plan
        try:
            plan = DependencyPlan(
                implementation_type.__init__, error_target=implementation_type
            )
        except (TypeError, ValueError) as error:
            injection_error = InjectionError(
                f"Cannot inspect constructor for {implementation_type.__qualname__}."
            )
            injection_error.__cause__ = error
            self._add_issue(injection_error)
            return None
        self._plans[implementation_type] = plan
        return plan

    def _validate_request(
        self,
        request: DependencyRequest,
        target: type[object],
    ) -> None:
        matches = tuple(
            descriptor
            for descriptor in self._descriptors
            if descriptor.service_type is request.service_type
            and descriptor.key == request.key
        )

        if request.collection_kind is not None:
            for descriptor in matches:
                self._validate_descriptor(descriptor)
            return

        if request.key is None and _is_builtin_service(request.service_type):
            return

        if not matches:
            dependency = ServiceIdentifier(request.service_type, request.key)
            self._issues.append(
                ValidationIssue(
                    ServiceNotRegisteredError(
                        request.service_type,
                        key=request.key,
                        target=target,
                        parameter_name=request.parameter_name,
                    ),
                    (*self._current_path(), dependency),
                )
            )
            return

        self._validate_descriptor(matches[-1])

    def _add_issue(self, error: PydicoError) -> None:
        self._issues.append(ValidationIssue(error, self._current_path()))

    def _current_path(self) -> tuple[ServiceIdentifier, ...]:
        return tuple(
            ServiceIdentifier(descriptor.service_type, descriptor.key)
            for descriptor in self._stack
        )


def _is_builtin_service(service_type: type[object]) -> bool:
    # Imported lazily to avoid collection/provider/scope import cycles.
    from pydico.provider import ServiceProvider
    from pydico.resolver import ServiceResolver
    from pydico.scope import ServiceScope

    return service_type in (ServiceProvider, ServiceResolver, ServiceScope)


def _normalize_cycle(descriptor_ids: tuple[int, ...]) -> tuple[int, ...]:
    rotations = tuple(
        descriptor_ids[index:] + descriptor_ids[:index]
        for index in range(len(descriptor_ids))
    )
    return min(rotations)
