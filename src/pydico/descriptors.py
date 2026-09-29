from collections.abc import Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydico._typing import ServiceFactory
from pydico.lifetimes import ServiceLifetime

TService_co = TypeVar("TService_co", covariant=True)


@dataclass(frozen=True)
class ServiceDescriptor(Generic[TService_co]):
    service_type: type[TService_co]
    lifetime: ServiceLifetime
    implementation_type: type[TService_co] | None = None
    factory: ServiceFactory[TService_co] | None = None
    instance: TService_co | None = None
    key: Hashable | None = None
