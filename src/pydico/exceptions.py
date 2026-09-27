from collections.abc import Sequence

from pydico.descriptors import ServiceDescriptor


class InjectionError(RuntimeError):
    """A required function argument could not be injected."""


class ScopedResolutionError(RuntimeError):
    """A scoped service was requested outside a scope."""


class ScopeClosedError(RuntimeError):
    """A closed scope cannot resolve services."""


class CircularDependencyError(RuntimeError):
    def __init__(self, chain: Sequence[ServiceDescriptor[object]]) -> None:
        self.chain = tuple(chain)
        names = (
            descriptor.service_type.__qualname__
            + (f"[key={descriptor.key!r}]" if descriptor.key is not None else "")
            for descriptor in self.chain
        )
        super().__init__("Circular dependency detected: " + " -> ".join(names))
