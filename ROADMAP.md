# pydico Roadmap

The phases are intentionally ordered. Each phase must keep the existing tests
and Pyright checks green before the next phase begins.

## Phase 0 - Baseline (complete)

- [x] Run the complete test suite.
- [x] Run Pyright without errors or warnings.
- [x] Compare the README with the implemented behavior.
- [x] Preserve the existing TODO in this roadmap.
- [x] Cover the public behavior with success and failure tests.

Baseline contract:

- registrations are captured as an immutable provider snapshot;
- transient, scoped, singleton, and prebuilt-instance registrations work;
- root resolution rejects scoped services;
- scopes are isolated, synchronized, and reject access after closing;
- singleton creation and resolution-cycle tracking are thread-safe;
- constructor and function injection require registered concrete types;
- keyed and multiple registrations preserve registration identity and order;
- `ServiceResolver`, `ServiceProvider`, and `ServiceScope` follow the documented
  root/scope resolution rules.

Verification commands:

```shell
uv run pytest -q
uv run pyright
```

## Phase 1 - Public API (complete)

- [x] Export the supported collection, provider, scope, resolver, lifetime,
  descriptor, injection decorator, and exceptions from `pydico`.
- [x] Define `__all__` as the public compatibility boundary.
- [x] Update examples and add public-import contract tests.

## Phase 2 - Error Model (complete)

- [x] Introduce `PydicoError` as the common base exception.
- [x] Separate registration, resolution, injection, closed-resource, and missing
  service errors.
- [x] Attach service type, key, parameter, and resolution-chain context where
  useful.
- [x] Replace incidental built-in exceptions in public resolution paths.

## Phase 3 - Resource Lifecycle (complete)

- [x] Track container-owned scoped and singleton instances.
- [x] Close them in reverse creation order.
- [x] Add idempotent provider closing and provider context-manager support.
- [x] Never automatically close transient or externally supplied instances.
- [x] Define and test behavior for concurrent resolution and closing.

## Phase 4 - Registration Typing (complete)

- [x] Model class and ABC registrations with concrete implementations.
- [x] Tighten descriptor covariance, factory generics, and registration overloads.
- [x] Add positive and negative Pyright contract cases and document the
  common-base inference limitation for direct two-type calls.

## Phase 5 - Shared Injection Model (complete)

- [x] Parse constructor and function dependencies through one internal request model.
- [x] Share annotation validation, error reporting, and type-hint caching.
- [x] Preserve the current resolver and lifetime semantics.
- [x] Support required positional-only constructor dependencies.

## Phase 6 - Keyed Injection (complete)

- [x] Introduce an `InjectKey` metadata object.
- [x] Resolve `Annotated[Service, InjectKey(key)]` in constructors and functions.
- [x] Reject conflicting key metadata with a clear injection error.

## Phase 7 - Standard Collection Injection (complete)

- [x] Support `list[T]` and `tuple[T, ...]`.
- [x] Support `set[T]` and `frozenset[T]`.
- [x] Support `Sequence[T]` and `Iterable[T]` as eagerly resolved tuples.
- [x] Support keyed collections through `Annotated`.
- [x] Preserve registration order and lifetime semantics.
- [x] Return empty collections when no registrations exist.
- [x] Report collection materialization failures structurally.

## Phase 8 - Optional Build-Time Diagnostics (complete)

- [x] Validate constructability and statically visible dependency graphs without
  creating services.
- [x] Report multiple configuration problems together.
- [x] Keep runtime scope enforcement unchanged; no `ValidateScopes` switch is
  required for normal resolution.

## Phase 9 - Async Lifecycle

- Design async disposal separately from synchronous resolution.
- Add `aclose()` and async context management before considering async factories.
- Test task-local resolver context and concurrent async closing.

## Phase 10 - Package Readiness

- Complete user and API documentation, changelog, license, and examples.
- Add automated tests, Pyright, formatting, and package-build checks.
- Verify installation and usage from the built distribution.
