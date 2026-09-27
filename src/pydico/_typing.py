from collections.abc import Callable
from typing import TypeVar

from pydico.resolver import ServiceResolver

TService = TypeVar("TService")

ServiceFactory = Callable[[ServiceResolver], TService]
