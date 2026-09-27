"""Context-local resolver activation for function injection."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

from pydico.resolver import ServiceResolver

_current_resolver: ContextVar[ServiceResolver | None] = ContextVar(
    "pydico_current_resolver", default=None
)


def get_current_resolver() -> ServiceResolver | None:
    return _current_resolver.get()


@contextmanager
def use_resolver(resolver: ServiceResolver) -> Generator[ServiceResolver]:
    """Activate temporarily; ownership and closing stay with the caller."""
    token = _current_resolver.set(resolver)
    try:
        yield resolver
    finally:
        _current_resolver.reset(token)
