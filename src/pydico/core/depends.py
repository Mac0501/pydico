from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DependencyMarker:
    key: str | None = None


def Depends(key: str | None = None) -> Any:
    return DependencyMarker(key)
