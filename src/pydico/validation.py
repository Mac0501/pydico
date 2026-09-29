"""Public result types for optional service-provider validation."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydico.exceptions import PydicoError
from pydico.identifiers import ServiceIdentifier


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One statically detectable problem in a registered dependency graph."""

    error: PydicoError
    path: tuple[ServiceIdentifier, ...]


class ServiceProviderValidationError(PydicoError):
    """One or more dependency graphs failed optional build-time validation."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        count = len(self.issues)
        details = "\n".join(
            f"{index}. {_format_path(issue.path)}\n   {issue.error}"
            for index, issue in enumerate(self.issues, start=1)
        )
        message = (
            f"Service provider validation failed with {count} issue"
            f"{'s' if count != 1 else ''}."
        )
        if details:
            message += f"\n\n{details}"
        super().__init__(message)


def _format_path(path: tuple[ServiceIdentifier, ...]) -> str:
    return " -> ".join(str(identifier) for identifier in path)
