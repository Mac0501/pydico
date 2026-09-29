from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class User:
    id: int
    name: str
    active: bool = True
