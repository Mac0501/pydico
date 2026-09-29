# pydico

Dependency injection for Python 3.13+, with constructor injection, scoped
services, keyed registrations, collection injection, and synchronous or
asynchronous resource cleanup. There are no runtime dependencies.

The library is experimental. Its public API may change.

[Changelog](https://github.com/Mac0501/pydico/blob/main/CHANGELOG.md) ·
[Contributing](https://github.com/Mac0501/pydico/blob/main/CONTRIBUTING.md) ·
[MIT License](https://github.com/Mac0501/pydico/blob/main/LICENSE)

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Framework examples](#framework-examples)
- [Registering services](#registering-services)
- [Resolving services](#resolving-services)
- [Lifetimes and scopes](#lifetimes-and-scopes)
- [Function injection](#function-injection)
- [Annotation rules](#annotation-rules)
- [Keyed services](#keyed-services)
- [Collections](#collections)
- [Resource cleanup](#resource-cleanup)
- [Build-time validation](#build-time-validation)
- [Errors](#errors)
- [Concurrency](#concurrency)
- [Public API and typing](#public-api-and-typing)
- [Development](#development)

## Installation

Requires Python 3.13 or newer. Install the latest release from PyPI:

```shell
python -m pip install pydico
```

With uv:

```shell
uv add pydico
```

To install directly from a repository checkout:

```shell
python -m pip install .
```

The Python examples below are independent scripts unless identified as a
signature reference.

## Quick start

A service declares its dependencies as constructor parameters. Register those
types, build a provider, and ask it for the outermost service:

```python
from pydico import ServiceCollection


class Logger:
    def log(self, message: str) -> None:
        print(message)


class ReportService:
    def __init__(self, logger: Logger) -> None:
        self.logger = logger

    def create(self) -> None:
        self.logger.log("Report created")


service_collection = ServiceCollection()
service_collection.add_singleton(Logger)
service_collection.add_transient(ReportService)

with service_collection.build_service_provider(validate=True) as provider:
    report = provider.get_service(ReportService)
    assert report is not None
    report.create()
```

`ServiceCollection` describes how services are created. Building a
`ServiceProvider` takes a snapshot of those registrations; later changes to the
collection do not affect that provider. Services are created on demand, not when
the provider is built.

Constructor injection needs no decorator. Dependencies must be registered
explicitly; an unregistered class is not automatically constructed.

## Framework examples

The [`examples`](https://github.com/Mac0501/pydico/tree/main/examples)
directory contains medium-sized integrations split across multiple modules:

| Example | Scope boundary | Demonstrates |
| --- | --- | --- |
| [`fastapi_app`](https://github.com/Mac0501/pydico/tree/main/examples/fastapi_app) | One scope per HTTP request | FastAPI lifespan ownership and dependencies |
| [`discord_bot`](https://github.com/Mac0501/pydico/tree/main/examples/discord_bot) | One scope per command | discord.py bot ownership and command services |
| [`click_cli`](https://github.com/Mac0501/pydico/tree/main/examples/click_cli) | One scope per CLI command | Click application state and scoped repositories |
| [`apscheduler_app`](https://github.com/Mac0501/pydico/tree/main/examples/apscheduler_app) | One scope per scheduled run | Async jobs and asynchronous resource cleanup |

The framework remains the application host in every example. It owns startup,
shutdown, routing, commands, or scheduling; pydico only builds and resolves the
application services. Each example has its own README with installation and run
instructions.

## Registering services

Each lifetime method accepts either the service class itself, a concrete
implementation class, or a factory. Registration methods mutate the collection
and return it, so you may either call them step by step or chain them.

Signature reference (`T` is the requested service type):

| Method | Meaning |
| --- | --- |
| `add_transient(T, implementation_type=None, *, factory=None, key=None)` | Create on every resolution |
| `add_scoped(T, implementation_type=None, *, factory=None, key=None)` | Cache within each scope |
| `add_singleton(T, implementation_type=None, *, factory=None, key=None)` | Cache within each provider |
| `add_instance(T, instance, *, key=None)` | Return an existing caller-owned object |
| `build_service_provider(*, validate=False)` | Build an independent provider |

Do not specify an implementation and a factory together.

### Interfaces and implementations

Use a base class or an abstract base class as the service type. The
implementation must inherit from it and must not be abstract.

```python
from abc import ABC, abstractmethod

from pydico import ServiceCollection


class Repository(ABC):
    @abstractmethod
    def read(self) -> str:
        ...


class MemoryRepository(Repository):
    def read(self) -> str:
        return "stored value"


service_collection = ServiceCollection()
service_collection.add_scoped(Repository, MemoryRepository)

with service_collection.build_service_provider() as provider:
    with provider.create_scope() as scope:
        repository = scope.get_service(Repository)
        assert repository is not None
        assert repository.read() == "stored value"
        assert scope.get_service(MemoryRepository) is None
```

Lookup uses the registered service type, not an automatic search for subclasses.
Registering `Repository` does not also register `MemoryRepository`.

### Instances and factories

Use an instance for configuration or an object managed by your application.
Use a factory when construction requires values or custom logic.

```python
from dataclasses import dataclass

from pydico import ServiceCollection, ServiceResolver


@dataclass(frozen=True)
class Settings:
    prefix: str


class Greeter:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def greet(self) -> str:
        return f"{self.prefix}, world"


def create_greeter(resolver: ServiceResolver) -> Greeter:
    settings = resolver.get_service(Settings)
    assert settings is not None
    return Greeter(settings.prefix)


service_collection = ServiceCollection()
service_collection.add_instance(Settings, Settings(prefix="Hello"))
service_collection.add_transient(Greeter, factory=create_greeter)

with service_collection.build_service_provider() as provider:
    greeter = provider.get_service(Greeter)
    assert greeter is not None
    assert greeter.greet() == "Hello, world"
```

A factory receives one resolver; its parameters are not automatically injected.
It must synchronously return a valid service instance, never a coroutine or
`None`. Factory results are not runtime-checked against the service type, so
annotate and type-check your factories. Constructor and factory exceptions
propagate unchanged.

The factory runs in the service's lifetime context: singleton factories receive
the root provider, scoped factories receive their scope, and transient factories
receive the resolver through which they are being constructed.

## Resolving services

Providers and scopes both expose:

| Call | Result |
| --- | --- |
| `get_service(T, *, key=None)` | Last matching registration, or `None` if absent |
| `get_services(T, *, key=None)` | Tuple of all matching registrations in registration order; empty if absent |

A missing **direct lookup** returns `None`. A missing **required injected
dependency** raises `ServiceNotRegisteredError`. Errors constructing a
registered service still propagate from either lookup method.

Multiple registrations are retained. Singleton and scoped caches belong to
individual registrations, not just to the requested type; registering the same
class twice creates two independently cached registrations.

## Lifetimes and scopes

| Lifetime | Reuse | Typical use | Cleanup owner |
| --- | --- | --- | --- |
| Transient | New construction per lookup | Lightweight operations | Caller |
| Scoped | Once per registration per scope | Request or unit-of-work state | Scope |
| Singleton | Once per registration per provider | Shared application services | Provider |
| Instance | The supplied object | Configuration, external resources | Caller |

A factory can deliberately return an existing object; the container cannot make
that object new or isolate it across scopes.

Create a scope for each request, job, or unit of work:

```python
from pydico import ServiceCollection


class Session:
    pass


service_collection = ServiceCollection()
service_collection.add_scoped(Session)

with service_collection.build_service_provider() as provider:
    with provider.create_scope() as first:
        session = first.get_service(Session)
        assert session is not None
        assert first.get_service(Session) is session

        with provider.create_scope() as second:
            assert second.get_service(Session) is not session

        assert first.get_service(Session) is session
```

Scopes have independent caches, including when their context-manager blocks are
nested. They share their provider's singletons. Entering an inner scope restores
the outer injection context on exit.

A root lookup of a scoped service raises `ScopeRequiredError`. This also applies
when a root-resolved transient needs a scoped dependency. Resolve that transient
through a scope instead.

Singleton construction always uses the root context, even when the first lookup
comes from a scope. Its automatically resolved dependencies therefore cannot be
scoped. A transient captured by a singleton is retained by that singleton; its
transient registration does not shorten the lifetime of that reference.

Keep the provider alive until all scopes have finished. **Closing a provider
does not close its scopes.** Close each scope before closing the provider.

### Injecting the resolver itself

These unkeyed types are supplied automatically without registration:

| Requested type | Through the provider | Through a scope |
| --- | --- | --- |
| `ServiceResolver` | Root provider | Current scope |
| `ServiceProvider` | Root provider | Root provider |
| `ServiceScope` | No built-in instance | Current scope |

Use `ServiceResolver` when a service genuinely needs further lookups in its
current context. A `ServiceProvider` always refers to the root; it does not
become scope-aware when injected into a scoped service.

These built-ins are not descriptors and are not automatically included in
`get_services()`. Avoid registering replacements for their unkeyed types.

## Function injection

Use `@inject` or the equivalent `@inject()` to fill missing required function
arguments from the active scope:

```python
from pydico import ServiceCollection, inject


class Session:
    pass


@inject
def handle(session: Session, label: str = "default") -> Session:
    return session


service_collection = ServiceCollection()
service_collection.add_scoped(Session)

with service_collection.build_service_provider() as provider:
    with provider.create_scope() as scope:
        assert handle() is scope.get_service(Session)
        assert handle(label="custom") is scope.get_service(Session)

    explicit = Session()
    assert handle(explicit) is explicit
```

Only omitted required arguments are injected. Explicit values, including
`None`, win; parameters with defaults keep their defaults even if their type is
registered. If every required argument is supplied, no active scope is needed.

Calling a function that needs injection outside an active scope raises
`NoActiveScopeError`. Creating a scope without entering it does not activate
it. Entering a provider context also does not activate it for ambient injection.

For explicit binding, use `@inject(provider)` or `@inject(scope)`. The bound
resolver takes precedence over the ambient scope. A root-bound function cannot
resolve scoped dependencies.

Async functions are supported. Their arguments are resolved when the coroutine
executes, and resolution itself remains synchronous. Generator and async
generator functions are unsupported.

Instance methods work with `@inject`; place `@classmethod` outside `@inject`
for class methods. `self`, `cls`, `*args`, and `**kwargs` are never injected.

## Annotation rules

Constructor and function injection share the same rules for parameters that
actually require injection:

| Annotation | Behavior |
| --- | --- |
| A class or ABC, such as `Repository` | Resolve that exact registered service type |
| `Annotated[T, InjectKey(key)]` | Resolve a keyed service |
| A supported collection of `T` | Resolve all matching registrations |
| Missing annotation | `MissingTypeAnnotationError` |
| `Any`, `T \| None`, `Optional[T]`, or another union | `UnsupportedTypeAnnotationError` |
| Unsupported generic, such as `dict[str, T]` | `UnsupportedTypeAnnotationError` |

There is no optional-injection mode. To use an application-owned default,
declare a default value; the container then leaves that parameter alone.

String annotations and postponed annotations are resolved using the callable's
module and, for constructors, the class namespace. Locally defined types that
are no longer available in those namespaces cannot be resolved by name. Prefer
module-level service classes when using postponed annotations.

## Keyed services

Keys separate registrations of the same type. Keys must be hashable; `None`
means an unkeyed registration. There is no fallback between keyed and unkeyed
registrations.

```python
from typing import Annotated

from pydico import InjectKey, ServiceCollection, inject


class Channel:
    def __init__(self, name: str) -> None:
        self.name = name


@inject
def notify(channel: Annotated[Channel, InjectKey("email")]) -> str:
    return channel.name


service_collection = ServiceCollection()
service_collection.add_instance(Channel, Channel("email"), key="email")
service_collection.add_instance(Channel, Channel("sms"), key="sms")

with service_collection.build_service_provider() as provider:
    assert provider.get_service(Channel) is None
    channel = provider.get_service(Channel, key="sms")
    assert channel is not None and channel.name == "sms"
    with provider.create_scope():
        assert notify() == "email"
```

The same `Annotated` syntax works in constructors. One parameter may contain
at most one `InjectKey`; duplicate keys also raise `ConflictingInjectKeyError`.
Other `Annotated` metadata is ignored. `InjectKey(None)` is invalid.

## Collections

Collection injection uses the same registrations and lifetimes as
`get_services()`:

| Annotation | Injected value |
| --- | --- |
| `list[T]` | List |
| `tuple[T, ...]` | Tuple |
| `set[T]` | Set |
| `frozenset[T]` | Frozen set |
| `collections.abc.Sequence[T]` | Tuple |
| `collections.abc.Iterable[T]` | Tuple, eagerly resolved |

```python
from typing import Annotated

from pydico import InjectKey, ServiceCollection, inject


class Handler:
    pass


class AuditHandler(Handler):
    pass


class EmailHandler(Handler):
    pass


@inject
def handlers(
    items: Annotated[list[Handler], InjectKey("events")],
) -> list[Handler]:
    return items


service_collection = ServiceCollection()
service_collection.add_singleton(Handler, AuditHandler, key="events")
service_collection.add_singleton(Handler, EmailHandler, key="events")

with service_collection.build_service_provider() as provider:
    with provider.create_scope():
        assert [type(item) for item in handlers()] == [AuditHandler, EmailHandler]
```

Place `InjectKey` on the outer collection annotation, as above.
`list[Annotated[T, InjectKey(...)]]` is unsupported.

No matching registrations means an empty collection. Lists and tuples preserve
registration order and duplicates. Sets follow Python equality and hashing,
may merge equal objects, and provide no registration-order guarantee.
Unhashable results raise `CollectionMaterializationError`.

Nested collections, fixed-length tuples such as `tuple[T, T]`, and arbitrary
collection classes are not supported as multi-service annotations. Use the
parameterized forms above; a bare `list` is an ordinary service type lookup,
not a request for all services.

## Resource cleanup

Container-created scoped services and scoped factory results belong to their
scope. Container-created singletons and singleton factory results belong to
their provider. Only instantiated resources are tracked.

Transient instances and values registered with `add_instance()` remain
caller-owned and are never automatically closed. If a singleton retains a
disposable transient, your application or the singleton must manage its cleanup.

Resources participate by implementing either structural protocol:

- `SupportsClose`: `def close(self) -> None`
- `SupportsAsyncClose`: `async def aclose(self) -> None`

No inheritance or decorator is required. Merely implementing `__exit__` or
`__aexit__` is not sufficient; the container calls the close methods, and does
not enter service context managers.

### Choosing synchronous or asynchronous cleanup

| Resource methods | `with` / `close()` | `async with` / `await aclose()` |
| --- | --- | --- |
| Only `close()` | Calls `close()` | Calls `close()` |
| Only `aclose()` | Raises `AsyncDisposalRequiredError` | Awaits `aclose()` |
| Both | Calls `close()` | Awaits `aclose()` |
| Neither | No cleanup hook | No cleanup hook |

Async cleanup uses `asyncio`. This is a complete example:

```python
import asyncio

from pydico import ServiceCollection


class Connection:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        await asyncio.sleep(0)
        self.closed = True


async def main() -> None:
    service_collection = ServiceCollection()
    service_collection.add_scoped(Connection)

    async with service_collection.build_service_provider() as provider:
        async with provider.create_scope() as scope:
            connection = scope.get_service(Connection)
            assert connection is not None
            assert not connection.closed
        assert connection.closed


asyncio.run(main())
```

`get_service()` and `get_services()` remain synchronous, including inside
`async with`. Async factories and async initialization are not supported.
For externally initialized async resources, use `add_instance()` and retain
responsibility for their cleanup.

Use one event loop for the lifetime of resources that are tied to a loop.
In an already-running async application, await cleanup in that loop.

### Cleanup guarantees and boundaries

Each owner closes resources in reverse creation order, once per object identity
within that owner. Distinct owners do not coordinate ownership: do not return
the same disposable object from factories belonging to different scopes.

Repeated closing is idempotent. After cleanup, further resolution fails with
`ScopeClosedError` or `ProviderClosedError`. Context-manager exit closes the
owner even when the body raises an exception.

Before synchronous disposal starts, the owner checks for async-only resources.
If it finds any, it raises `AsyncDisposalRequiredError` without disposing
anything or clearing the cache. You can then finish with `await owner.aclose()`.
Such resources are never silently skipped.

Ordinary exceptions from cleanup hooks are collected in `DisposalError.errors`;
remaining resources are still attempted and the owner ends closed. A subsequent
close does not retry failed hooks. A cleanup error can become the exception
propagated from context-manager exit when the body also failed.

Concurrent `aclose()` calls coordinate so resources are not disposed twice.
Cancellation of a caller awaiting `aclose()` is deferred until its cleanup has
finished. This does not guarantee completion if the event loop is stopped or a
cleanup hook itself raises `CancelledError` or another `BaseException`.

Synchronous hooks called by `aclose()` run on the event-loop thread; keep them
short. Cleanup hooks should release their own resources rather than resolve
new services from their closing owner.

## Build-time validation

Use `build_service_provider(validate=True)` to check statically visible
constructor dependencies before use:

```python
from pydico import ServiceCollection, ServiceProviderValidationError


class Missing:
    pass


class Consumer:
    def __init__(self, dependency: Missing) -> None:
        self.dependency = dependency


try:
    service_collection = ServiceCollection()
    service_collection.add_transient(Consumer)
    service_collection.build_service_provider(validate=True)
except ServiceProviderValidationError as error:
    for issue in error.issues:
        print(" -> ".join(map(str, issue.path)))
        print(issue.error)
```

Validation reports missing registrations, invalid annotations, and constructor
cycles together. `issues` contains `ValidationIssue` objects with an `error`
and a `path` of `ServiceIdentifier` values (service type and key).

It does not construct services, execute factories, populate caches, inspect
standalone decorated functions, or validate scoped lifetime capture.
Scope rules still apply during resolution regardless of the validation option.

Runtime cycle detection also covers recursive factory lookups and raises
`CircularDependencyError`; its `chain` describes the cycle.

## Errors

Structured container errors derive from `PydicoError`. Registration failures
derive from `RegistrationError`; resolution failures derive from
`ResolutionError`, with injection failures under `InjectionError`.

| Error | Meaning / action |
| --- | --- |
| `ConflictingRegistrationError` | Choose one construction strategy |
| `ImplementationTypeMismatchError` | Implementation must inherit from service type |
| `InstanceTypeMismatchError` | Supplied instance must match service type |
| `AbstractTypeRegistrationError` | Provide a concrete implementation or factory |
| `ServiceNotRegisteredError` | Register the required type and matching key |
| `NoActiveScopeError` | Enter a scope or explicitly bind the decorator |
| `MissingTypeAnnotationError` | Annotate the required dependency |
| `UnsupportedTypeAnnotationError` | Use a supported, unambiguous annotation |
| `ConflictingInjectKeyError` | Use only one key annotation per parameter |
| `CollectionMaterializationError` | Check collection requirements, such as hashability |
| `ScopeRequiredError` | Resolve scoped dependencies through a scope |
| `ScopeClosedError` / `ProviderClosedError` | The owner is closing or closed |
| `CircularDependencyError` | Remove the dependency cycle shown in `chain` |
| `CloseDuringResolutionError` | Do not close an owner from its active resolution |
| `AsyncDisposalRequiredError` | Use async cleanup; `resources` identifies async-only objects |
| `DisposalError` | Inspect the original exceptions in `errors` |
| `ServiceProviderValidationError` | Inspect each build-time `issue` |

Errors expose relevant fields such as `service_type`, `key`, `target`, and
`parameter_name`. Unresolvable annotation names raise `InjectionError` with
the original exception as the cause.

Exceptions from user constructors, factories, and function bodies are not
wrapped. Invalid Python arguments and invalid metadata can raise ordinary
`TypeError` or `ValueError`; not every possible failure is a `PydicoError`.

## Concurrency

Registration writes and provider snapshots are synchronized. Singleton creation
is serialized per provider; resolutions within a scope are serialized per scope.
Root transient construction and work in separate scopes can run concurrently.

Container synchronization does not make service instances thread-safe.
Singletons must protect their own shared mutable state. Avoid factories that
wait for another thread to resolve through the same scope or create a singleton
through the same provider: the waiting factory may hold the lock it needs.

Injection context is local to the current context. Nested scopes restore the
previous resolver. Async child tasks inherit their creator's active scope;
finish those tasks before exiting it. Ordinary new threads need their own
scope; context-copying helpers can inherit a scope and therefore share it.

Enter and exit a scope in the same task/context. A scope cannot be entered twice
at the same time. For concurrent independent requests, create separate scopes.

Shutdown waits for active resolution operations, not for arbitrary application
code using objects returned earlier. Stop that work first, close scopes, then
close the provider. Await async shutdown before stopping the event loop.

## Public API and typing

Import supported symbols from `pydico`. The public exports are defined by
`pydico.__all__`; modules beginning with `_` are implementation details.

The main API consists of `ServiceCollection`, `ServiceProvider`,
`ServiceScope`, `ServiceResolver`, `inject`, `InjectKey`,
`SupportsClose`, `SupportsAsyncClose`, and the errors listed above.
`ServiceLifetime`, immutable `ServiceDescriptor[T]`, `ServiceIdentifier`,
and `ValidationIssue` are also public. Prefer `ServiceCollection` for normal
registration because it performs registration validation.

Lookups preserve service types: `get_service(T)` returns `T | None` and
`get_services(T)` returns `tuple[T, ...]`. Factory return types may be
subtypes. `ServiceDescriptor` is covariant.

Type checkers can infer a common base such as `object` for unrelated types in
a two-class registration call. Runtime registration checks still reject an
incompatible implementation. Structural `Protocol` service types are not a
guaranteed registration contract; use classes or ABCs.

The injection decorator preserves runtime metadata and signatures and the
static return type. Its static callable type does not precisely express which
arguments can be omitted for injection.

## Development

From a repository checkout:

```shell
uv sync
uv run pytest -q
uv run pyright
uv run black --check src tests examples
uv run isort --check-only src tests examples
uv build --no-sources
uv run twine check dist/*.whl dist/*.tar.gz
```

The tests cover registration, resolution, scopes, injection, typing, validation,
resource ownership, synchronous/asynchronous lifecycle behavior, and the
documented framework examples. See the
[contribution guide](https://github.com/Mac0501/pydico/blob/main/CONTRIBUTING.md)
before submitting a change.

## Releases

GitLab CI validates the code, derives versions from recognized Conventional
Commits, publishes packages to the GitLab Package Registry, and creates the
GitLab release. Non-conventional commits are allowed and ignored during version
calculation. Public PyPI publishing and GitHub mirroring are prepared in the
pipeline but currently disabled. Use subjects such as `feat(scope): add
cleanup` or `fix(injection): reject ambiguity` when a commit should trigger a
release.

Configure this masked CI/CD variable in GitLab:

- `RELEASE_TOKEN`: GitLab project token with `write_repository`.

`PYPI_TOKEN` and `GITHUB_TOKEN` are not required while their corresponding
pipeline jobs remain disabled.

To make successful pipelines mandatory, enable **Pipelines must succeed** under
**Settings > Merge requests > Merge checks**. Do not edit versions, changelog
release sections, or release tags manually.
