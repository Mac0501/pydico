from collections.abc import Hashable
from typing import Protocol, TypeVar

T = TypeVar("T")


class ServiceResolver(Protocol):
    """Resolve services in the current root or scope context."""

    def get_service(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> T | None: ...

    def get_services(
        self, service_type: type[T], *, key: Hashable | None = None
    ) -> tuple[T, ...]: ...
