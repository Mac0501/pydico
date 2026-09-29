# Contributing to pydico

Thank you for helping improve pydico. The library is still experimental, so
changes to its public API are possible, but they must remain deliberate,
documented, and covered by tests.

## Before starting

Open or check an issue at <https://github.com/Mac0501/pydico/issues> before
starting a large change. This avoids duplicate work and gives maintainers a
place to agree on the intended behavior.

Never commit credentials, access tokens, private URLs, or generated package
artifacts.

## Development setup

Requires Python 3.13 or newer and [uv](https://docs.astral.sh/uv/).

```shell
git clone https://github.com/Mac0501/pydico.git
cd pydico
uv sync --frozen
```

## Required checks

Run the same checks locally that are expected in continuous integration:

```shell
uv run black --check src tests examples
uv run isort --check-only src tests examples
uv run pyright
uv run pytest -q
uv build --no-sources
uv run twine check dist/*.whl dist/*.tar.gz
```

Use `uv run black src tests examples` and
`uv run isort src tests examples` to apply formatting fixes.

## Submitting a change

- Keep each change focused and include tests for observable behavior.
- Use a Conventional Commit subject such as `feat(scope): add async cleanup` or
  `fix(injection): reject an ambiguous annotation` when a change should affect
  the next release version. Other commit formats are allowed, but release
  automation ignores them.
- Update the README when public behavior or usage changes.
- Preserve type safety and the zero-runtime-dependency design unless a change
  explicitly revises those project goals.
- Do not edit the project version or generated release sections in the
  changelog. GitLab CI derives them from the commit history.

By contributing, you agree that your contribution is licensed under the MIT
License used by this repository.

Versioning and publishing are automated by GitLab CI. Normal contributions
must not edit versions, generated changelog sections, or release tags.
