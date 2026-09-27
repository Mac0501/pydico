# pydico

`pydico` is a small experimental dependency-injection library for Python 3.13+.
The current design is intentionally compact: registrations are collected in a
`ServiceCollection`, and a read-only `ServiceProvider` resolves services from a
snapshot of those registrations.

The project is still being shaped. Breaking API changes are expected while the
core model is refined.

The implementation roadmap is maintained in [`ROADMAP.md`](ROADMAP.md).

## Installation

```shell
uv pip install pydico
```

or:

```shell
pip install pydico
```

## Quick Start

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


provider = (
    ServiceCollection()
    .add_singleton(Logger)
    .add_transient(ReportService)
    .build_service_provider()
)

service = provider.get_service(ReportService)
assert service is not None
service.create()
```

Constructor dependencies must be registered explicitly. `pydico` inspects the
constructor of the registered implementation type and resolves required
annotated parameters from the same provider.

## Registrations

`ServiceCollection` supports the following registrations:

```python
collection = ServiceCollection()

collection.add_transient(ReportService)
collection.add_scoped(DbContext)
collection.add_singleton(Logger)
collection.add_instance(Settings, Settings(environment="dev"))
```

You can also register an implementation type for a service type:

```python
collection.add_singleton(Logger, ConsoleLogger)
```

Or use a factory when construction needs custom logic:

```python
collection.add_singleton(
    ReportService,
    factory=lambda provider: ReportService(provider.get_service(Logger)),
)
```

For multiple registrations of the same service type, `get_service()` returns the
last matching registration and `get_services()` returns all matches in
registration order.

## Static Typing

Registration and resolution are typed for concrete classes, base classes, and
abstract base classes:

```python
from abc import ABC, abstractmethod
from typing import assert_type

from pydico import ServiceCollection


class Repository(ABC):
    @abstractmethod
    def save(self) -> None:
        ...


class SqlRepository(Repository):
    def save(self) -> None:
        ...


provider = (
    ServiceCollection()
    .add_scoped(Repository, SqlRepository)
    .build_service_provider()
)

assert_type(provider.get_service(Repository), Repository | None)
```

Factories may return the registered service type or a concrete subtype.
`ServiceDescriptor` is covariant, so a descriptor for a concrete implementation
can be used where a descriptor for its base service is expected. Runtime
validation remains active when static checking is bypassed.

Python type checkers can infer the common base `object` for two unrelated class
arguments in a direct registration call. pydico therefore keeps runtime
`issubclass()` and `isinstance()` validation as the authoritative safety net.
Structural `Protocol` service types are not part of the guaranteed typing
contract yet; use concrete classes or ABCs.

## Keys

Registrations can be separated with a hashable key:

```python
collection = (
    ServiceCollection()
    .add_singleton(Logger, ConsoleLogger, key="console")
    .add_singleton(Logger, FileLogger, key="file")
)

provider = collection.build_service_provider()
console_logger = provider.get_service(Logger, key="console")
```

Keys are part of the registration identity. A keyed registration is not returned
when resolving the same service type without that key.

Use `Annotated` with `InjectKey` to select a keyed registration during automatic
constructor or function injection:

```python
from typing import Annotated

from pydico import InjectKey, inject


class ReportService:
    def __init__(
        self,
        logger: Annotated[Logger, InjectKey("file")],
    ) -> None:
        self.logger = logger


@inject
def write_report(
    logger: Annotated[Logger, InjectKey("console")],
) -> None:
    ...
```

Exactly one `InjectKey` may appear on a parameter. Other `Annotated` metadata is
ignored so annotations can be shared with other libraries.

## Collection Injection

Automatic injection can resolve all registrations of a service into standard
collection annotations:

```python
from collections.abc import Iterable, Sequence
from typing import Annotated

from pydico import InjectKey


class Dispatcher:
    def __init__(
        self,
        handlers: list[Handler],
        keyed: Annotated[tuple[Handler, ...], InjectKey("commands")],
    ) -> None:
        self.handlers = handlers
        self.keyed = keyed
```

Supported forms are `list[T]`, `tuple[T, ...]`, `set[T]`, `frozenset[T]`,
`Sequence[T]`, and `Iterable[T]`. `Sequence` and `Iterable` are eagerly
materialized as tuples. An empty matching registration set produces an empty
collection rather than an error.

Lists and tuples preserve registration order and duplicates. Sets use normal
Python equality and hashing semantics, so they do not preserve order and may
combine equal services. A non-hashable service requested through `set` or
`frozenset` raises `CollectionMaterializationError`.

## Lifetimes

Transient services create a new object for each resolution:

```python
collection = ServiceCollection().add_transient(ReportService)
provider = collection.build_service_provider()

assert provider.get_service(ReportService) is not provider.get_service(ReportService)
```

Singleton services are created lazily once per provider and then reused:

```python
collection = ServiceCollection().add_singleton(Logger)
provider = collection.build_service_provider()

assert provider.get_service(Logger) is provider.get_service(Logger)
```

Prebuilt instances are always returned as-is.

Scoped services are created once per registration within each scope. Different
scopes have independent instances; singletons are shared with the root provider.

```python
class DbContext:
    pass

provider = ServiceCollection().add_scoped(DbContext).build_service_provider()
with provider.create_scope() as first:
    db = first.get_service(DbContext)
    assert db is first.get_service(DbContext)
    with provider.create_scope() as second:
        assert db is not second.get_service(DbContext)
```

Resolving a scoped service from the root raises `ScopeRequiredError`. This is
always enforced, without a validation option. Transient dependencies inherit the
current resolution context. Singletons are always constructed in the root
context, even when first requested from a scope. This root binding also applies
to ambient `@inject` calls made during singleton construction, so a singleton
cannot capture a scoped dependency.

Factories accept `ServiceResolver`, which can be imported directly from
`pydico`. Constructor injection and unkeyed `get_service()` provide these
built-in services:

| Requested type | Root resolution | Scope resolution |
| --- | --- | --- |
| `ServiceResolver` | Root provider | Current scope |
| `ServiceProvider` | Root provider | Root provider |
| `ServiceScope` | Not registered (`None`) | Current scope |

Use `ServiceResolver` for dependencies that need the current resolution context.
Built-in services are not added as descriptors: `get_services()` enumerates only
explicit registrations. Public types such as `ServiceScope` can be imported
directly from `pydico`.

Exiting the context manager calls `close()`, including when an exception occurs.
Closing is idempotent, clears the scope cache and rejects subsequent resolutions
with `ScopeClosedError`. Container-created scoped services implementing
`SupportsClose` are closed automatically in reverse creation order.

## Resource Lifecycle

`SupportsClose` is a runtime-checkable structural protocol:

```python
from pydico import SupportsClose


class Database:
    def close(self) -> None:
        ...


assert isinstance(Database(), SupportsClose)
```

Services do not need to inherit from a pydico base class. Ownership follows the
registration lifetime:

| Registration | Owner | Automatic close |
| --- | --- | --- |
| container-created scoped service | Scope | Yes |
| scoped factory result | Scope | Yes |
| container-created singleton | Provider | Yes |
| singleton factory result | Provider | Yes |
| transient service | Caller | No |
| `add_instance()` value | Caller | No |

Use the provider as a context manager when it owns singleton resources:

```python
services = ServiceCollection().add_singleton(HttpClient)

with services.build_service_provider() as provider:
    client = provider.get_service(HttpClient)

# The container-created HttpClient is closed here.
```

Scopes and providers close owned services in reverse creation order. Closing is
idempotent. If multiple service `close()` calls fail, pydico still attempts all
remaining services and raises one `DisposalError` containing the original
exceptions in its `errors` tuple. A closed provider rejects new resolution and
scope creation with `ProviderClosedError`.

Closing a provider or scope from inside one of its active resolutions raises
`CloseDuringResolutionError`. Reentrant provider closing from an owned service's
`close()` method is treated as part of the already running close operation.

## Function Injection

Entering a service scope automatically activates it for `@inject`. Decorated
functions therefore do not need to receive or locate a provider themselves.

```python
from pydico import inject

@inject
def create_report(db: DbContext):
    return db

with provider.create_scope() as scope:
    db = create_report()
    assert db is scope.get_service(DbContext)
```

`@inject()` is equivalent to `@inject`. Calling a decorated function without
an active scope raises `InjectionError`. Creating a scope object alone does not
activate it; activation begins when its `with` block is entered.

An explicitly bound `@inject(provider)` or `@inject(scope)` remains available
for specialized cases and takes precedence over the active scope. A root-bound
function still cannot resolve scoped services.

Only missing required parameters are injected. Explicit arguments (including
`None`) and defaults are preserved. Plain class annotations use unkeyed
registrations; `Annotated[T, InjectKey(key)]` selects a keyed registration.
The standard collection annotations documented above resolve all matching
registrations. Unions, nested collections, heterogeneous tuples, and other
generic aliases are not supported. `self`, `cls`, `*args` and `**kwargs` are
never injected. Use `@classmethod` outside `@inject`.
Unresolvable local forward references must be replaced with concrete annotations
or types available in the function's module.

Missing resolvers and invalid annotations raise `InjectionError`; a missing
single registration raises `ServiceNotRegisteredError`. Factory and function
errors propagate.
Normal and async functions are supported; generators are rejected. Async
injection happens when the coroutine executes, not when it is created.
Runtime signatures and metadata are preserved; static typing preserves the
return type but cannot express which arguments may be omitted for injection.

Nested scope blocks restore the outer scope even when the inner block raises an
exception. Resolver contexts are isolated between threads and async tasks. Child
async tasks inherit their creator's active scope and must finish before it
closes. New threads do not inherit the caller's scope; each worker should enter
its own scope.

## Thread Safety

`ServiceCollection` protects registration writes and provider snapshot creation
with a short lock. A provider therefore sees a stable tuple of descriptors, even
if the collection is modified later.

`ServiceProvider` protects singleton cache access with a provider-local
reentrant lock. Concurrent resolutions of the same singleton create exactly one
instance, and singleton factories may resolve other singleton services from the
same provider.

Transient services resolved from the root are not serialized and may be
constructed in parallel. Separate providers have separate singleton caches and
locks. Each scope uses its own reentrant lock to serialize resolutions and
closing, ensuring exactly one successful creation per scoped registration.
Different scopes can resolve concurrently. Closing waits for running resolutions;
factories must not wait for another thread to resolve through the same scope.

The provider does not make returned service objects thread-safe. If a service is
mutable and shared as a singleton, that service must protect its own state.

## Circular Dependencies

Resolution uses a thread-local stack. Cycles through constructors or factories
raise `CircularDependencyError` and include the detected descriptor chain:

```python
from pydico import CircularDependencyError


try:
    provider.get_service(ReportService)
except CircularDependencyError as error:
    print(error.chain)
```

The stack is local to each thread, so parallel resolutions of the same transient
registration do not look like false cycles.

## Build-Time Diagnostics

Pass `validate=True` when building a provider to inspect every statically
visible constructor graph before resolution begins:

```python
from pydico import ServiceProviderValidationError


try:
    provider = services.build_service_provider(validate=True)
except ServiceProviderValidationError as error:
    for issue in error.issues:
        print(" -> ".join(map(str, issue.path)))
        print(issue.error)
```

Validation reports missing registrations, annotation errors, keyed dependency
errors, and circular constructor graphs together. It never creates services,
executes factories, or fills provider caches. Factory bodies and standalone
`@inject` functions are not statically visible and remain runtime-validated.
Scope boundaries also remain runtime rules; build-time diagnostics do not add a
separate `ValidateScopes` mode.

## Error Handling

All errors raised by the dependency-injection system derive from `PydicoError`.
Invalid registrations derive from `RegistrationError`; failures while resolving
or injecting services derive from `ResolutionError`.

Common concrete errors include:

- `ConflictingRegistrationError` for multiple construction strategies;
- `ImplementationTypeMismatchError` and `InstanceTypeMismatchError` for
  incompatible registrations;
- `AbstractTypeRegistrationError` when an abstract type would be instantiated;
- `ScopeRequiredError` and `ScopeClosedError` for invalid scope usage;
- `ProviderClosedError` when a closed provider is used;
- `DisposalError` when owned services fail to close;
- `ServiceNotRegisteredError` when a required injected service is missing;
- `NoActiveScopeError` when `@inject` is called outside an active scope;
- `MissingTypeAnnotationError` and `UnsupportedTypeAnnotationError` for
  parameters that cannot be injected;
- `CircularDependencyError` for constructor or factory cycles;
- `CloseDuringResolutionError` when a provider or scope is closed from one of
  its active resolutions;
- `ServiceProviderValidationError` for aggregated optional build diagnostics.

The exceptions expose structured attributes such as `service_type`, `key`,
`target`, `parameter_name`, or `chain`. `get_service()` still returns
`None` when an optional lookup has no registration. Exceptions raised inside
user factories, constructors, and decorated function bodies propagate unchanged.

Constructor injection and `@inject` use the same strict annotation rules. Every
automatically injected parameter must name exactly one concrete registered type.
Missing annotations and unions (including `T | None`) are rejected. Supported
collection annotations resolve all matching services. Parameters with defaults
and explicitly supplied function arguments are left untouched, including their
annotations.

## Current Limits

This version intentionally keeps the surface small:

- no async disposal hooks yet;
- constructor auto-wiring only uses registered dependency types;
- factories receive the current `ServiceResolver`.

These limits are design space for the next iteration, not permanent constraints.

## Development Checks

The current behavior is protected by the test suite and static type checking:

```shell
uv run pytest -q
uv run pyright
```

Both commands must pass before a roadmap phase is considered complete.
