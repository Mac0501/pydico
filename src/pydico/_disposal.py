from collections.abc import Iterable

from pydico.exceptions import DisposalError
from pydico.lifecycle import SupportsClose


def close_instances(instances: Iterable[SupportsClose]) -> None:
    errors: list[Exception] = []
    for instance in instances:
        try:
            instance.close()
        except Exception as error:
            errors.append(error)
    if errors:
        raise DisposalError(errors) from errors[0]
