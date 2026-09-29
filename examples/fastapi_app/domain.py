from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Report:
    id: int
    title: str
