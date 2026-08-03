from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from pydico.lifetime import Lifetime
from pydico.types import Dependency, Key, ServiceFactory

_UNRESOLVED: Final = object()


@dataclass(slots=True)
class ServiceDescriptor:
    key: Key
    lifetime: Lifetime
    implementation: Dependency | None = None
    factory: ServiceFactory | None = None
    instance: object = field(default=_UNRESOLVED, repr=False)

    def __post_init__(self) -> None:
        if (self.implementation is None) == (self.factory is None):
            raise ValueError(
                "A service descriptor requires either an implementation or a factory."
            )

    @property
    def has_instance(self) -> bool:
        return self.instance is not _UNRESOLVED
