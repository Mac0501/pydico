from __future__ import annotations

import inspect
from abc import ABC
from typing import Any, TypeAlias, TypeVar, get_type_hints

# --- Type Aliases (Based on previous context and DI needs) ---
Interface: TypeAlias = type[ABC]  # Typically an Abstract Base Class (ABC)
Dependency: TypeAlias = type[Any]  # The concrete class implementing the interface
T = TypeVar("T")


class Container:
    """
    A simplified, class-based Dependency Injection Container
    inspired by the .NET IServiceCollection/IServiceProvider patterns.
    """

    _transients: dict[Interface, Dependency] = {}
    _singletons: dict[Interface | Dependency, Dependency] = {}
    _singleton_instances: dict[Interface | Dependency, Any] = {}

    _keyed_transients: dict[str, Dependency] = {}
    _keyed_singletons: dict[str, Dependency] = {}
    _keyed_singleton_instances: dict[str, Any] = {}

    @classmethod
    def _validate_registration(cls, i: Interface, d: Dependency) -> None:
        if not issubclass(d, i):
            raise TypeError(
                f"Implementation {d.__name__} must be a subclass of interface {i.__name__}."
            )
        if inspect.isabstract(d):
            raise TypeError(
                f"Cannot register abstract class {d.__name__} as a concrete dependency."
            )

    @classmethod
    def add_transient(cls, i: Interface, d: Dependency) -> None:
        cls._validate_registration(i, d)
        cls._transients[i] = d

    @classmethod
    def add_singleton_self(cls, d: Dependency) -> None:
        if inspect.isabstract(d):
            raise TypeError(
                f"Cannot register abstract class {d.__name__} for self-registration."
            )
        cls._singletons[d] = d

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
                    raise ValueError(
                        f"Parameter '{name}' in {implementation.__name__}'s constructor requires a type hint "
                        f"to be resolved by the container."
                    )

                dependency_interface = resolved_hints[name]
                dependencies[name] = cls.get(dependency_interface)

            return dependencies

        except ValueError as ve:
            raise ve
        except RecursionError:
            raise RecursionError(
                f"Circular dependency detected while resolving {implementation.__name__}"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to resolve dependencies for {implementation.__name__}: {e}"
            )

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
            raise LookupError(f"No keyed service registered for key: '{key}'")

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
            raise LookupError(f"No service registered for interface: {i.__name__}")

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
