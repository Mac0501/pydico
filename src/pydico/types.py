from typing import Any, Callable, Protocol, TypeVar, overload

type Dependency = type[Any]
type Key = str | Dependency

T = TypeVar("T")


class Resolver(Protocol):
    @overload
    def resolve(self, key: type[T]) -> T: ...

    @overload
    def resolve(self, key: str) -> object: ...


type ServiceFactory = Callable[[Resolver], object]
