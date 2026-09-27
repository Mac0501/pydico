"""Internal context-local resolver state used by scopes and injection."""

from contextvars import ContextVar, Token

from pydico.resolver import ServiceResolver

_current_resolver: ContextVar[ServiceResolver | None] = ContextVar(
    "pydico_current_resolver", default=None
)


def current_resolver() -> ServiceResolver | None:
    return _current_resolver.get()


def activate_resolver(
    resolver: ServiceResolver,
) -> Token[ServiceResolver | None]:
    return _current_resolver.set(resolver)


def restore_resolver(token: Token[ServiceResolver | None]) -> None:
    _current_resolver.reset(token)
