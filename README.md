# pydico

`pydico` is a small dependency-injection container for Python 3.13+. It supports
constructor auto-wiring, transient, scoped and singleton lifetimes, keyed
registrations, prebuilt instances, custom factories, and explicit
decorator-based injection.

> The project is currently experimental. Its API may change while the design is
> being refined.

## Installation

```shell
uv pip install pydico
```

or:

```shell
pip install pydico
```

## Quick start

```python
from abc import ABC, abstractmethod

from pydico import Container


class ILogger(ABC):
    @abstractmethod
    def log(self, message: str) -> None:
        pass


class ConsoleLogger(ILogger):
    def log(self, message: str) -> None:
        print(message)


class ReportService:
    def __init__(self, logger: ILogger) -> None:
        self.logger = logger

    def create(self) -> None:
        self.logger.log("Report created")


container = Container()
container.register_singleton(ILogger, ConsoleLogger)

service = container.resolve(ReportService)
service.create()
```

`ReportService` does not need an explicit registration. Because it is a concrete
class, the container creates it as a transient and resolves its required
constructor dependencies recursively.

## Registrations

Each `Container` owns its registrations. Separate containers are fully isolated
from one another.

### Transient

A transient creates a new instance for every resolution:

```python
container.register_transient(ILogger, ConsoleLogger)

first = container.resolve(ILogger)
second = container.resolve(ILogger)

assert first is not second
```

A concrete class can be registered using its own type as the key:

```python
container.register_transient(ReportService)
```

### Singleton

A singleton is created lazily on its first resolution and then reused:

```python
container.register_singleton(ILogger, ConsoleLogger)

first = container.resolve(ILogger)
second = container.resolve(ILogger)

assert first is second
```

Concrete self-registration is also supported:

```python
container.register_singleton(ReportService)
```

Registrations apply only to their exact key. Registering `ILogger` does not also
register `ConsoleLogger`.

### Scoped

A scoped service is created once per scope. Repeated resolutions inside the same
scope return the same object, while another scope receives a different object:

```python
container.register_scoped(RequestContext)

with container.create_scope() as first_scope:
    first = first_scope.resolve(RequestContext)
    assert first_scope.resolve(RequestContext) is first

with container.create_scope() as second_scope:
    second = second_scope.resolve(RequestContext)

assert first is not second
```

Scoped services cannot be resolved directly from the root container. This also
prevents singletons from retaining scoped dependencies beyond the scope's
lifetime. Transient services resolved through a scope may depend on scoped
services and will receive that scope's cached instance.

Scopes are context managers and are closed automatically at the end of the
`with` block. A closed scope cannot resolve further dependencies.

### Existing instances

Use `register_instance` for configuration, mocks, or objects constructed by
another library:

```python
settings = AppSettings()
container.register_instance(AppSettings, settings)

assert container.resolve(AppSettings) is settings
```

The instance must match a class key. String keys may contain any object,
including `None`.

### String keys

String keys distinguish multiple services that share the same type:

```python
container.register_singleton("console-logger", ConsoleLogger)
logger = container.resolve("console-logger")
```

A later registration for the same key replaces the earlier registration.

### Factories

Factories are useful when construction needs runtime values or custom logic.
They receive a restricted `Resolver`, which can resolve dependencies without
changing the container's registrations:

```python
from pydico import Resolver


def create_report_service(resolver: Resolver) -> ReportService:
    logger = resolver.resolve(ILogger)
    return ReportService(logger)


container.register_factory(ReportService, create_report_service)
```

Factories are transient by default. Pass a lifetime to cache their result:

```python
from pydico import Lifetime

container.register_factory(
    ReportService,
    create_report_service,
    lifetime=Lifetime.SINGLETON,
)
```

`Lifetime.SCOPED` caches a factory result once per scope:

```python
container.register_factory(
    ReportService,
    create_report_service,
    lifetime=Lifetime.SCOPED,
)
```

For class keys, the factory result is checked at runtime against the registered
type. Factory dependencies participate in circular-dependency detection just
like constructor dependencies.

## Auto-wiring

When an unregistered concrete class is resolved, `pydico`:

1. inspects its `__init__` method;
2. reads the type hints of required parameters;
3. resolves those dependencies recursively;
4. calls the constructor with the resolved objects.

Required constructor parameters must have type hints. Parameters with default
values are left untouched, and built-in types such as `str` and `int` are not
auto-wired unless explicitly registered.

Circular dependency graphs raise `CircularDependencyError` with the detected
dependency chain.

## Function and method injection

`@inject(...)` binds a function to a specific resolver, which can be either a
container or a scope. Mark injectable parameters with `Depends()`:

```python
from pydico import Depends, inject


@inject(container)
def handle_report(
    report_id: int,
    logger: ILogger = Depends(),
) -> None:
    logger.log(f"Handling report {report_id}")


handle_report(42)
```

The dependency type comes from the parameter annotation. Passing an argument
explicitly overrides injection, which is useful for tests:

```python
handle_report(42, logger=fake_logger)
```

For a string-keyed registration, pass the key to `Depends`:

```python
container.register_transient("reports", ReportService)


@inject(container)
def run(service: ReportService = Depends("reports")) -> None:
    service.create()
```

The decorator can also be used on constructors:

```python
class Handler:
    @inject(container)
    def __init__(self, logger: ILogger = Depends()) -> None:
        self.logger = logger
```

Because the container is explicit, different functions can use different
dependency graphs without relying on global state.

For scoped dependencies, bind the decorator to the active scope:

```python
with container.create_scope() as scope:

    @inject(scope)
    def handle_request(context: RequestContext = Depends()) -> None:
        pass

    handle_request()
```

## Clearing a container

```python
container.clear()
```

`clear()` removes every registration and cached singleton from that container.
Calling `close()` on a scope releases its cached scoped instances.
