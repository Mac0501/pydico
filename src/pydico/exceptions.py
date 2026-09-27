from collections.abc import Hashable, Sequence

from pydico.identifiers import ServiceIdentifier


def _name(value: object) -> str:
    return getattr(value, "__qualname__", repr(value))


class PydicoError(Exception):
    """Base class for errors raised by pydico itself."""


class RegistrationError(PydicoError):
    """A service registration is invalid."""


class ConflictingRegistrationError(RegistrationError):
    def __init__(self, service_type: type[object], strategies: Sequence[str]) -> None:
        self.service_type = service_type
        self.strategies = tuple(strategies)
        joined = ", ".join(self.strategies)
        super().__init__(
            f"{service_type.__qualname__} has multiple construction strategies: "
            f"{joined}. Only one strategy may be specified."
        )


class ImplementationTypeMismatchError(RegistrationError):
    def __init__(
        self,
        service_type: type[object],
        implementation_type: type[object],
    ) -> None:
        self.service_type = service_type
        self.implementation_type = implementation_type
        super().__init__(
            f"{implementation_type.__qualname__} cannot be registered as an "
            f"implementation of {service_type.__qualname__}."
        )


class AbstractTypeRegistrationError(RegistrationError):
    def __init__(
        self,
        service_type: type[object],
        implementation_type: type[object] | None = None,
    ) -> None:
        self.service_type = service_type
        self.implementation_type = implementation_type
        if implementation_type is None:
            message = (
                f"Abstract service {service_type.__qualname__} requires a concrete "
                "implementation, factory, or instance."
            )
        else:
            message = (
                f"Implementation {implementation_type.__qualname__} for service "
                f"{service_type.__qualname__} is abstract and cannot be instantiated."
            )
        super().__init__(message)


class InstanceTypeMismatchError(RegistrationError):
    def __init__(
        self,
        service_type: type[object],
        instance_type: type[object],
    ) -> None:
        self.service_type = service_type
        self.instance_type = instance_type
        super().__init__(
            f"Instance of {instance_type.__qualname__} cannot be registered for "
            f"service {service_type.__qualname__}."
        )


class ResolutionError(PydicoError):
    """A service could not be resolved by pydico."""


class ProviderClosedError(ResolutionError):
    def __init__(self) -> None:
        super().__init__(
            "The service provider is closed and can no longer resolve services."
        )


class ScopeClosedError(ResolutionError):
    def __init__(self) -> None:
        super().__init__(
            "The service scope is closed and can no longer resolve services."
        )


class ScopeRequiredError(ResolutionError):
    def __init__(
        self,
        service_type: type[object],
        key: Hashable | None = None,
    ) -> None:
        self.service_type = service_type
        self.key = key
        identifier = ServiceIdentifier(service_type, key)
        super().__init__(
            f"{identifier} has a scoped lifetime and requires an active service "
            "scope. Use provider.create_scope()."
        )


class CircularDependencyError(ResolutionError):
    def __init__(self, chain: Sequence[ServiceIdentifier]) -> None:
        self.chain = tuple(chain)
        chain_text = " -> ".join(str(identifier) for identifier in self.chain)
        super().__init__(f"Circular dependency detected: {chain_text}")


class ServiceNotRegisteredError(ResolutionError):
    def __init__(
        self,
        service_type: type[object],
        *,
        key: Hashable | None = None,
        target: object | None = None,
        parameter_name: str | None = None,
    ) -> None:
        self.service_type = service_type
        self.key = key
        self.target = target
        self.parameter_name = parameter_name
        identifier = ServiceIdentifier(service_type, key)
        message = f"No registration was found for {identifier}"
        if target is not None and parameter_name is not None:
            message += f" required by {_name(target)}.{parameter_name}"
        super().__init__(message + ".")


class InjectionError(ResolutionError):
    """Automatic constructor or function injection failed."""


class NoActiveScopeError(InjectionError):
    def __init__(self, target: object) -> None:
        self.target = target
        super().__init__(
            f"Cannot inject dependencies into {_name(target)} because no service "
            "scope is active. Use 'with provider.create_scope():' around the "
            "operation."
        )


class MissingTypeAnnotationError(InjectionError):
    def __init__(self, target: object, parameter_name: str) -> None:
        self.target = target
        self.parameter_name = parameter_name
        super().__init__(
            f"Parameter {parameter_name!r} of {_name(target)} requires a type "
            "annotation."
        )


class UnsupportedTypeAnnotationError(InjectionError):
    def __init__(
        self,
        target: object,
        parameter_name: str,
        annotation: object,
    ) -> None:
        self.target = target
        self.parameter_name = parameter_name
        self.annotation = annotation
        super().__init__(
            f"Parameter {parameter_name!r} of {_name(target)} uses unsupported "
            f"annotation {annotation!r}."
        )


class ConflictingInjectKeyError(InjectionError):
    def __init__(
        self,
        target: object,
        parameter_name: str,
        keys: Sequence[Hashable],
    ) -> None:
        self.target = target
        self.parameter_name = parameter_name
        self.keys = tuple(keys)
        super().__init__(
            f"Parameter {parameter_name!r} of {_name(target)} has multiple "
            f"InjectKey metadata values: {self.keys!r}. Exactly one is allowed."
        )


class DisposalError(PydicoError):
    def __init__(self, errors: Sequence[Exception]) -> None:
        self.errors = tuple(errors)
        count = len(self.errors)
        super().__init__(
            f"Failed to close {count} container-owned service"
            f"{'s' if count != 1 else ''}."
        )
