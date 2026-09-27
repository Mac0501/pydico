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

## Phase 3 - Resource Lifecycle

- Track container-owned scoped and singleton instances.
- Close them in reverse creation order.
- Add idempotent provider closing and provider context-manager support.
- Never automatically close transient or externally supplied instances.
- Define and test behavior for concurrent resolution and closing.

## Phase 4 - Registration Typing

- Model interface/ABC registrations with concrete implementations correctly.
- Tighten descriptor and factory generics and overloads.
- Add positive and negative Pyright contract cases.

## Phase 5 - Shared Injection Model

- Parse constructor and function dependencies through one internal request model.
- Share annotation validation, error reporting, and type-hint caching.
- Preserve the current resolver and lifetime semantics.

## Phase 6 - Keyed Injection

- Introduce an `InjectKey` metadata object.
- Resolve `Annotated[Service, InjectKey(key)]` in constructors and functions.
- Reject conflicting key metadata with a clear injection error.

## Phase 7 - Optional and Collection Injection

- Support `T | None` as an optional dependency.
- Support `tuple[T, ...]` through `get_services()`.
- Keep unsupported ambiguous unions explicit errors.
- Define combinations with keyed injection.

## Phase 8 - Optional Build-Time Diagnostics

- Validate constructability and statically visible dependency graphs without
  creating services.
- Report multiple configuration problems together.
- Keep runtime scope enforcement unchanged; no `ValidateScopes` switch is
  required for normal resolution.

## Phase 9 - Async Lifecycle

- Design async disposal separately from synchronous resolution.
- Add `aclose()` and async context management before considering async factories.
- Test task-local resolver context and concurrent async closing.

## Phase 10 - Package Readiness

- Complete user and API documentation, changelog, license, and examples.
- Add automated tests, Pyright, formatting, and package-build checks.
- Verify installation and usage from the built distribution.
