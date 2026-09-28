from collections.abc import Iterable

from pydico.exceptions import AsyncDisposalRequiredError, DisposalError
from pydico.lifecycle import OwnedResource, SupportsAsyncClose, SupportsClose


def ensure_sync_disposable(instances: Iterable[OwnedResource]) -> None:
    async_only = tuple(
        instance
        for instance in instances
        if isinstance(instance, SupportsAsyncClose)
        and not isinstance(instance, SupportsClose)
    )
    if async_only:
        raise AsyncDisposalRequiredError(async_only)


def close_instances(instances: Iterable[OwnedResource]) -> None:
    instances = tuple(instances)
    ensure_sync_disposable(instances)
    errors: list[Exception] = []
    for instance in instances:
        try:
            if isinstance(instance, SupportsClose):
                instance.close()
        except Exception as error:
            errors.append(error)
    if errors:
        raise DisposalError(errors) from errors[0]


async def aclose_instances(instances: Iterable[OwnedResource]) -> None:
    errors: list[Exception] = []
    for instance in instances:
        try:
            if isinstance(instance, SupportsAsyncClose):
                await instance.aclose()
            else:
                instance.close()
        except Exception as error:
            errors.append(error)
    if errors:
        raise DisposalError(errors) from errors[0]
