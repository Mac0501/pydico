from __future__ import annotations

import inspect
from abc import ABC
from typing import TypeVar, cast, get_type_hints, overload

from pydico.exceptions import (
    AbstractDependencyError,
    CircularDependencyError,
    ImplementationMismatchError,
    InstanceTypeError,
    MissingTypeHintError,
    UnregisteredDependencyError,
)
from pydico.types import Dependency, Interface, Key

T = TypeVar("T")


class Container:
    _transients: dict[str | Interface, Dependency] = {}
    _singletons: dict[Key, Dependency] = {}
    _singleton_instances: dict[Key, object] = {}

    @overload
    @classmethod
    def add_transient(cls, key: str, d: Dependency) -> None: ...

    @overload
    @classmethod
    def add_transient(cls, key: Interface, d: Dependency) -> None: ...

    @classmethod
    def add_transient(cls, key: str | Interface, d: Dependency) -> None:
        cls._validate_registration(key, d)
        cls._transients[key] = d

    @overload
    @classmethod
    def add_singleton(cls, key: Dependency) -> None: ...

    @overload
    @classmethod
    def add_singleton(cls, key: str, d: Dependency) -> None: ...

    @overload
    @classmethod
    def add_singleton(cls, key: Interface, d: Dependency) -> None: ...

    @classmethod
    def add_singleton(cls, key: Key, d: Dependency | None = None) -> None:
        cls._validate_registration(key, d)
        if d:
            cls._singletons[key] = d
            return
        if not isinstance(key, str) and not inspect.isabstract(key):
            cls._singletons[key] = key
            return

    @classmethod
    def add_singleton_instance(cls, key: Key, o: object) -> None:
        if not isinstance(key, str) and not isinstance(o, key):
            raise InstanceTypeError(key, o)
        cls._singleton_instances[key] = o

    @overload
    @classmethod
    def get(cls, key: type[T]) -> T: ...

    @overload
    @classmethod
    def get(cls, key: str) -> object: ...

    @overload
    @classmethod
    def get(cls, key: str, type: type[T]) -> T: ...

    @classmethod
    def get(cls, key: str | type[T], type: type[T] = object) -> T:
        instance = cls._get(key)
        return cast(T, instance)

    @classmethod
    def clean(cls) -> None:
        cls._transients.clear()
        cls._singletons.clear()
        cls._singleton_instances.clear()

    @classmethod
    def _get(cls, key: Key) -> object:

        instance = cls._get_singleton(key)
        if instance is not None:
            return instance

        instance = cls._get_transient(key)
        if instance is not None:
            return instance

        raise UnregisteredDependencyError(key)

    @classmethod
    def _validate_registration(cls, key: Key, d: Dependency | None) -> None:
        if isinstance(key, str):
            if d is None:
                raise ValueError(
                    f"A Dependency (the implementation class) cannot be None "
                    f"when registering with a string key: '{key}'. "
                    f"You must provide a concrete class."
                )
            return

        if d is None:
            d = key
        if inspect.isabstract(d):
            raise AbstractDependencyError(d)
        if key == d:
            return
        if not issubclass(d, key):
            raise ImplementationMismatchError(key, d)

    @classmethod
    def _resolve_dependencies(cls, implementation: Dependency) -> dict[str, object]:
        try:
            signature = inspect.signature(implementation.__init__)

            resolved_hints = get_type_hints(implementation.__init__)
            dependencies: dict[str, object] = {}

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

        except RecursionError:
            raise CircularDependencyError([implementation])
        except CircularDependencyError as e:
            raise CircularDependencyError([implementation, *e.chain])

    @classmethod
    def _get_instance(cls, d: Dependency) -> object:
        kwargs = cls._resolve_dependencies(d)
        instance: object = d(**kwargs)
        return instance

    @classmethod
    def _get_singleton(cls, key: Key) -> object | None:
        if key in cls._singleton_instances:
            return cls._singleton_instances[key]

        if key in cls._singletons:
            implementation = cls._singletons[key]
            instance = cls._get_instance(implementation)
            cls.add_singleton_instance(key, instance)
            return instance

        if not isinstance(key, str) and not inspect.isabstract(key):
            for _, v in cls._singleton_instances.items():
                if type(v) is key:
                    return v

            for k, v in cls._singletons.items():
                if v is key:
                    instance: object = cls._get_instance(v)
                    cls.add_singleton_instance(k, instance)
                    return instance

        return None

    @classmethod
    def _get_transient(cls, key: Key) -> object | None:

        if isinstance(key, str) or (inspect.isabstract(key) and issubclass(key, ABC)):
            if key in cls._transients:
                implementation = cls._transients[key]
                instance: object = cls._get_instance(implementation)
                return instance
        else:
            instance: object = cls._get_instance(key)
            return instance

        return None
