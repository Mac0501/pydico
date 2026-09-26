# pydico

`pydico` is a small experimental dependency-injection library for Python 3.13+.
The current design is intentionally compact: registrations are collected in a
`ServiceCollection`, and a read-only `ServiceProvider` resolves services from a
snapshot of those registrations.

The project is still being shaped. Breaking API changes are expected while the
core model is refined.

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
from pydico.collection import ServiceCollection


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

Resolving a scoped service from the root raises `ScopedResolutionError`. This is
always enforced, without a validation option. Transient dependencies inherit the
current resolution context. Singletons are always constructed in the root
context, even when first requested from a scope, so a singleton cannot resolve
a scoped dependency through its constructor or supplied factory resolver.

Factories accept `ServiceResolver` (from `pydico.resolver`). Constructor injection
and unkeyed `get_service()` provide these built-in services:

| Requested type | Root resolution | Scope resolution |
| --- | --- | --- |
| `ServiceResolver` | Root provider | Current scope |
| `ServiceProvider` | Root provider | Root provider |
| `ServiceScope` | Not registered (`None`) | Current scope |

Use `ServiceResolver` for dependencies that need the current resolution context.
Built-in services are not added as descriptors: `get_services()` enumerates only
explicit registrations. Import `ServiceScope` from `pydico.scope`.

Exiting the context manager calls `close()`, including when an exception occurs.
Closing is idempotent, clears the scope cache and rejects subsequent resolutions
with `ScopeClosedError`. Existing references remain usable; service `close()` or
disposal hooks are not invoked automatically.

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
from pydico.exceptions import CircularDependencyError


try:
    provider.get_service(ReportService)
except CircularDependencyError as error:
    print(error.chain)
```

The stack is local to each thread, so parallel resolutions of the same transient
registration do not look like false cycles.

## Current Limits

This version intentionally keeps the surface small:

- no disposal or async disposal hooks yet;
- no decorator-based function injection yet;
- constructor auto-wiring only uses registered dependency types;
- factories receive the current `ServiceResolver`.

These limits are design space for the next iteration, not permanent constraints.
