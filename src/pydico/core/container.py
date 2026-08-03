from __future__ import annotations

import inspect
from typing import Callable, TypeGuard, TypeVar, get_type_hints, overload

from pydico.exceptions import (
    AbstractDependencyError,
    CircularDependencyError,
    ImplementationMismatchError,
    InstanceTypeError,
    MissingTypeHintError,
    ScopeRequiredError,
    UnregisteredDependencyError,
)
from pydico.lifetime import Lifetime
from pydico.scope import Scope
from pydico.types import Dependency, Key, Resolver, ServiceFactory

from .descriptor import ServiceDescriptor

T = TypeVar("T")


class _ResolutionContext:
    def __init__(self, resolve_key: Callable[[Key], object]) -> None:
        self._resolve_key = resolve_key

    @overload
    def resolve(self, key: type[T]) -> T: ...

    @overload
    def resolve(self, key: str) -> object: ...

    def resolve(self, key: Key) -> object:
        return self._resolve_key(key)


class _ScopeState:
    def __init__(self) -> None:
        self._instances: dict[Key, tuple[ServiceDescriptor, object]] = {}

    def get(self, descriptor: ServiceDescriptor) -> tuple[bool, object]:
        cached = self._instances.get(descriptor.key)
        if cached is None or cached[0] is not descriptor:
            return False, None
        return True, cached[1]

    def set(self, descriptor: ServiceDescriptor, instance: object) -> None:
        self._instances[descriptor.key] = (descriptor, instance)

    def clear(self) -> None:
        self._instances.clear()


class Container:
    def __init__(self) -> None:
        self._registrations: dict[Key, ServiceDescriptor] = {}

    @overload
    def register_transient(self, key: Dependency) -> None: ...

    @overload
    def register_transient(self, key: Key, implementation: Dependency) -> None: ...

    def register_transient(
        self, key: Key, implementation: Dependency | None = None
    ) -> None:
        implementation = self._validate_registration(key, implementation)
        self._registrations[key] = ServiceDescriptor(
            key=key,
            implementation=implementation,
            lifetime=Lifetime.TRANSIENT,
        )

    @overload
    def register_singleton(self, key: Dependency) -> None: ...

    @overload
    def register_singleton(self, key: Key, implementation: Dependency) -> None: ...

    def register_singleton(
        self, key: Key, implementation: Dependency | None = None
    ) -> None:
        implementation = self._validate_registration(key, implementation)
        self._registrations[key] = ServiceDescriptor(
            key=key,
            implementation=implementation,
            lifetime=Lifetime.SINGLETON,
        )

    @overload
    def register_scoped(self, key: Dependency) -> None: ...

    @overload
    def register_scoped(self, key: Key, implementation: Dependency) -> None: ...

    def register_scoped(
        self, key: Key, implementation: Dependency | None = None
    ) -> None:
        implementation = self._validate_registration(key, implementation)
        self._registrations[key] = ServiceDescriptor(
            key=key,
            implementation=implementation,
            lifetime=Lifetime.SCOPED,
        )

    @overload
    def register_instance(self, key: type[T], instance: T) -> None: ...

    @overload
    def register_instance(self, key: str, instance: object) -> None: ...

    def register_instance(self, key: Key, instance: object) -> None:
        if not isinstance(key, str) and not isinstance(instance, key):
            raise InstanceTypeError(key, instance)

        self._registrations[key] = ServiceDescriptor(
            key=key,
            implementation=type(instance),
            lifetime=Lifetime.SINGLETON,
            instance=instance,
        )

    @overload
    def register_factory(
        self,
        key: type[T],
        factory: Callable[[Resolver], T],
        *,
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> None: ...

    @overload
    def register_factory(
        self,
        key: str,
        factory: ServiceFactory,
        *,
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> None: ...

    def register_factory(
        self,
        key: Key,
        factory: ServiceFactory,
        *,
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> None:
        self._registrations[key] = ServiceDescriptor(
            key=key,
            factory=factory,
            lifetime=lifetime,
        )

    @overload
    def resolve(self, key: type[T]) -> T: ...

    @overload
    def resolve(self, key: str) -> object: ...

    def resolve(self, key: Key) -> object:
        return self._resolve(key)

    def create_scope(self) -> Scope:
        state = _ScopeState()
        return Scope(
            resolve_key=lambda key: self._resolve(key, scope_state=state),
            close_scope=state.clear,
        )

    def clear(self) -> None:
        self._registrations.clear()

    def _resolve(
        self,
        key: Key,
        resolution_stack: tuple[Key, ...] = (),
        scope_state: _ScopeState | None = None,
    ) -> object:
        if key in resolution_stack:
            cycle_start = resolution_stack.index(key)
            raise CircularDependencyError([*resolution_stack[cycle_start:], key])

        resolution_stack = (*resolution_stack, key)
        descriptor = self._registrations.get(key)
        if descriptor is not None:
            return self._resolve_descriptor(
                descriptor,
                resolution_stack,
                scope_state,
            )

        if self._can_autowire(key):
            return self._create_instance(key, resolution_stack, scope_state)

        raise UnregisteredDependencyError(key)

    def _resolve_dependencies(
        self,
        implementation: Dependency,
        resolution_stack: tuple[Key, ...],
        scope_state: _ScopeState | None,
    ) -> tuple[tuple[object, ...], dict[str, object]]:
        signature = inspect.signature(implementation.__init__)
        resolved_hints = get_type_hints(implementation.__init__)
        positional_dependencies: list[object] = []
        keyword_dependencies: dict[str, object] = {}

        for name, parameter in signature.parameters.items():
            if name == "self":
                continue

            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            if parameter.default is not inspect.Parameter.empty:
                continue

            if parameter.annotation is inspect.Parameter.empty:
                raise MissingTypeHintError(implementation, name)

            dependency_key = resolved_hints[name]
            dependency = self._resolve(
                dependency_key,
                resolution_stack,
                scope_state,
            )
            if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
                positional_dependencies.append(dependency)
            else:
                keyword_dependencies[name] = dependency

        return tuple(positional_dependencies), keyword_dependencies

    def _create_instance(
        self,
        implementation: Dependency,
        resolution_stack: tuple[Key, ...],
        scope_state: _ScopeState | None,
    ) -> object:
        positional_dependencies, keyword_dependencies = self._resolve_dependencies(
            implementation,
            resolution_stack,
            scope_state,
        )
        return implementation(*positional_dependencies, **keyword_dependencies)

    def _resolve_descriptor(
        self,
        descriptor: ServiceDescriptor,
        resolution_stack: tuple[Key, ...],
        scope_state: _ScopeState | None,
    ) -> object:
        if descriptor.lifetime is Lifetime.SINGLETON:
            if descriptor.has_instance:
                return descriptor.instance

            instance = self._create_from_descriptor(
                descriptor,
                resolution_stack,
                None,
            )
            descriptor.instance = instance
            return instance

        if descriptor.lifetime is Lifetime.SCOPED:
            if scope_state is None:
                raise ScopeRequiredError(descriptor.key)

            found, instance = scope_state.get(descriptor)
            if found:
                return instance

            instance = self._create_from_descriptor(
                descriptor,
                resolution_stack,
                scope_state,
            )
            scope_state.set(descriptor, instance)
            return instance

        return self._create_from_descriptor(
            descriptor,
            resolution_stack,
            scope_state,
        )

    def _create_from_descriptor(
        self,
        descriptor: ServiceDescriptor,
        resolution_stack: tuple[Key, ...],
        scope_state: _ScopeState | None,
    ) -> object:
        if descriptor.factory is not None:
            context = _ResolutionContext(
                lambda key: self._resolve(key, resolution_stack, scope_state)
            )
            instance = descriptor.factory(context)
            if not isinstance(descriptor.key, str) and not isinstance(
                instance, descriptor.key
            ):
                raise InstanceTypeError(descriptor.key, instance)
            return instance

        assert descriptor.implementation is not None
        return self._create_instance(
            descriptor.implementation,
            resolution_stack,
            scope_state,
        )

    @staticmethod
    def _can_autowire(key: Key) -> TypeGuard[Dependency]:
        return (
            isinstance(key, type)
            and key.__module__ != "builtins"
            and not inspect.isabstract(key)
        )

    @staticmethod
    def _validate_registration(
        key: Key, implementation: Dependency | None
    ) -> Dependency:
        if implementation is None:
            if isinstance(key, str):
                raise ValueError(
                    "An implementation is required when registering a string key: "
                    f"{key!r}."
                )
            implementation = key

        if inspect.isabstract(implementation):
            raise AbstractDependencyError(implementation)

        if not isinstance(key, str) and not issubclass(implementation, key):
            raise ImplementationMismatchError(key, implementation)

        return implementation
