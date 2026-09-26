from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydico.lifetimes import ServiceLifetime
from pydico.resolver import ServiceResolver

TService = TypeVar("TService")


@dataclass(frozen=True)
class ServiceDescriptor(Generic[TService]):
    service_type: type[TService]
    lifetime: ServiceLifetime
    implementation_type: type[TService] | None = None
    factory: Callable[[ServiceResolver], TService] | None = None
    instance: TService | None = None
    key: Hashable | None = None
