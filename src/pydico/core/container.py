from __future__ import annotations

import inspect
from abc import ABC
from typing import Any, TypeAlias, TypeVar, get_type_hints

from pydico.exceptions import (
    AbstractDependencyError,
    CircularDependencyError,
    ContainerError,
    ImplementationMismatchError,
    InstanceTypeError,
    InstantiationError,
    MissingTypeHintError,
    UnregisteredDependencyError,
)

Interface: TypeAlias = type[ABC]
Dependency: TypeAlias = type[object]
T = TypeVar("T")


class Container:
    _transients: dict[Interface, Dependency] = {}
    _singletons: dict[Interface | Dependency, Dependency] = {}
    _singleton_instances: dict[Interface | Dependency, object] = {}

    _keyed_transients: dict[str, Dependency] = {}
    _keyed_singletons: dict[str, Dependency] = {}
    _keyed_singleton_instances: dict[str, object] = {}

    @classmethod
    def _validate_registration(cls, i: Interface, d: Dependency) -> None:
        if inspect.isabstract(d):
            raise AbstractDependencyError(i, d)
        if not issubclass(d, i):
            raise ImplementationMismatchError(i, d)

    @classmethod
    def add_transient(cls, i: Interface, d: Dependency) -> None:
        cls._validate_registration(i, d)
        cls._transients[i] = d

    @classmethod
    def add_singleton_self(cls, d: Dependency) -> None:
        if inspect.isabstract(d):
            raise AbstractDependencyError(d, d)
        cls._singletons[d] = d

    @classmethod
    def add_singleton_instance(cls, i: Interface | Dependency, o: object) -> None:
        if not isinstance(o, i):
            InstanceTypeError(i, o)
        cls._singleton_instances[i] = o

    @classmethod
    def add_singleton(cls, i: Interface, d: Dependency) -> None:
        cls._validate_registration(i, d)
        cls._singletons[i] = d

    @classmethod
    def add_keyed_transient(cls, key: str, d: Dependency) -> None:
        cls._keyed_transients[key] = d

    @classmethod
    def add_keyed_singleton(cls, key: str, d: Dependency) -> None:
        cls._keyed_singletons[key] = d

    @classmethod
    def _resolve_dependencies(cls, implementation: Dependency) -> dict[str, Any]:
        try:
            signature = inspect.signature(implementation.__init__)

            resolved_hints = get_type_hints(implementation.__init__)
            dependencies: dict[str, Any] = {}

            for name, param in signature.parameters.items():
                if param.kind in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                ):
                    if name in ("self", "args", "kwargs"):
                        continue

                if param.kind in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                ):
                    continue

                if name == "self":
                    continue

                if param.annotation is inspect.Parameter.empty:
                    raise MissingTypeHintError(implementation, name)

                dependency_interface = resolved_hints[name]
                dependencies[name] = cls.get(dependency_interface)

            return dependencies

        except ContainerError:
            raise
        except RecursionError:
            raise CircularDependencyError(
                implementation,
                "Unbekannt",
            )
        except Exception as e:
            raise InstantiationError(implementation, e)

    @classmethod
    def _get_service_by_key(cls, key: str) -> object:
        if key in cls._keyed_singleton_instances:
            return cls._keyed_singleton_instances[key]

        if key in cls._keyed_singletons:
            implementation = cls._keyed_singletons[key]
            is_singleton = True
        elif key in cls._keyed_transients:
            implementation = cls._keyed_transients[key]
            is_singleton = False
        else:
            raise UnregisteredDependencyError(object, key, object)

        kwargs = cls._resolve_dependencies(implementation)

        instance = implementation(**kwargs)

        if is_singleton:
            cls._keyed_singleton_instances[key] = instance

        return instance

    @classmethod
    def _get_service_by_interface(cls, i: Interface) -> object:
        if i in cls._singleton_instances:
            return cls._singleton_instances[i]

        if i in cls._singletons:
            implementation = cls._singletons[i]
            is_singleton = True
        elif i in cls._transients:
            implementation = cls._transients[i]
            is_singleton = False
        else:
            raise UnregisteredDependencyError(object, i.__name__, i)

        kwargs = cls._resolve_dependencies(implementation)

        instance = implementation(**kwargs)

        if is_singleton:
            cls._singleton_instances[i] = instance

        return instance

    @classmethod
    def _get_service_by_dependency(cls, d: Dependency) -> object:
        if d in cls._singleton_instances:
            return cls._singleton_instances[d]

        if d in cls._singletons:
            implementation = cls._singletons[d]
            is_singleton = True
        else:
            implementation = d
            is_singleton = False

        kwargs = cls._resolve_dependencies(implementation)

        instance = implementation(**kwargs)

        if is_singleton:
            cls._singleton_instances[d] = instance

        return instance

    @classmethod
    def get(cls, key: str | Interface | Dependency) -> object:

        if isinstance(key, str):
            return cls._get_service_by_key(key=key)
        else:
            if issubclass(key, ABC):
                return cls._get_service_by_interface(i=key)
            else:
                return cls._get_service_by_dependency(d=key)

    @classmethod
    def clean(cls) -> None:
        cls._transients.clear()
        cls._singletons.clear()
        cls._singleton_instances.clear()

        cls._keyed_transients.clear()
        cls._keyed_singletons.clear()
        cls._keyed_singleton_instances.clear()
