from collections.abc import Hashable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServiceIdentifier:
    """Public, immutable identity of a service registration."""

    service_type: type[object]
    key: Hashable | None = None

    def __str__(self) -> str:
        name = self.service_type.__qualname__
        if self.key is None:
            return name
        return f"{name}[key={self.key!r}]"
