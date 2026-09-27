"""Static registration contracts checked by Pyright, not executed by Pytest."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import assert_type

from pydico import (
    ServiceCollection,
    ServiceDescriptor,
    ServiceLifetime,
    ServiceProvider,
    ServiceResolver,
    ServiceScope,
)


class Repository(ABC):
    @abstractmethod
    def save(self) -> None: ...


class SqlRepository(Repository):
    def save(self) -> None:
        pass


class OtherRepository(Repository):
    def save(self) -> None:
        pass


class Logger:
    pass


def create_repository(_: ServiceResolver) -> Repository:
    return SqlRepository()


def create_sql_repository(_: ServiceResolver) -> SqlRepository:
    return SqlRepository()


def create_logger(_: ServiceResolver) -> Logger:
    return Logger()


services = ServiceCollection()

# Every supported registration form accepts a concrete subtype for an ABC.
services.add_transient(Repository, SqlRepository)
services.add_transient(Repository, factory=create_repository)
services.add_scoped(Repository, SqlRepository)
services.add_scoped(Repository, factory=create_sql_repository)
services.add_singleton(Repository, SqlRepository)
services.add_singleton(Repository, factory=create_repository)
services.add_instance(Repository, SqlRepository())

# Keys separate registrations without changing their static service type.
services.add_scoped(Repository, OtherRepository, key="other")

# The component contracts themselves reject unrelated types. At a direct
# two-type registration call, Python type checkers may infer their common base
# object; pydico therefore also enforces this relationship at runtime.
invalid_implementation: type[Repository] = (
    Logger  # pyright: ignore[reportAssignmentType]
)
invalid_factory: Callable[[ServiceResolver], Repository] = (
    create_logger  # pyright: ignore[reportAssignmentType]
)
invalid_instance: Repository = Logger()  # pyright: ignore[reportAssignmentType]
assert_type(invalid_implementation, type[Repository])
assert_type(invalid_factory, Callable[[ServiceResolver], Repository])
assert_type(invalid_instance, Repository)

# Frozen descriptors are safe to widen from a concrete type to its base type.
concrete_descriptor = ServiceDescriptor(
    service_type=SqlRepository,
    implementation_type=SqlRepository,
    lifetime=ServiceLifetime.SCOPED,
)
general_descriptor: ServiceDescriptor[Repository] = concrete_descriptor


def accept_general_descriptor(_: ServiceDescriptor[Repository]) -> None:
    pass


accept_general_descriptor(concrete_descriptor)


def check_resolution_types(
    provider: ServiceProvider,
    scope: ServiceScope,
) -> None:
    assert_type(provider.get_service(Repository), Repository | None)
    assert_type(provider.get_services(Repository), tuple[Repository, ...])
    assert_type(scope.get_service(Repository), Repository | None)
    assert_type(scope.get_services(Repository), tuple[Repository, ...])
