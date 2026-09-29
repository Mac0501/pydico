"""Public metadata used to configure dependency injection."""

from collections.abc import Hashable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InjectKey:
    """Select a keyed registration for an ``Annotated`` dependency."""

    key: Hashable

    def __post_init__(self) -> None:
        if self.key is None:
            raise ValueError("InjectKey requires a non-None key.")
        try:
            hash(self.key)
        except TypeError as error:
            raise TypeError("InjectKey requires a hashable key.") from error
