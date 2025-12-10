from pydico.types import Key


class ContainerError(Exception):
    pass


class RegistrationError(ContainerError):
    def __init__(self, message: str):
        super().__init__(message)


class ImplementationMismatchError(RegistrationError):
    interface_type: type
    dependency_type: type

    def __init__(self, interface_type: type, dependency_type: type):
        self.interface_type = interface_type
        self.dependency_type = dependency_type
        message = (
            f"Implementation {dependency_type.__name__} must be a subclass "
            f"of interface {interface_type.__name__}."
        )
        super().__init__(message)


class AbstractDependencyError(RegistrationError):
    dependency_type: type

    def __init__(self, dependency_type: type):
        self.dependency_type = dependency_type
        message = (
            f"Cannot register abstract class {dependency_type.__name__} as a dependency. "
            f"An abstract class cannot be instantiated directly."
        )
        super().__init__(message)


class InstanceTypeError(RegistrationError):
    interface_type: type
    instance_object: object

    def __init__(self, interface_type: type, instance_object: object):
        self.interface_type = interface_type
        self.instance_object = instance_object
        dependency_type = type(self.instance_object)

        message = (
            f"Object {instance_object!r} is of type {dependency_type.__name__} "
            f"but is not an instance of the required type {interface_type.__name__}."
        )
        super().__init__(message)


class ResolutionError(ContainerError):
    def __init__(self, message: str):
        super().__init__(message)


class MissingTypeHintError(ResolutionError):
    dependency_type: type
    parameter_name: str

    def __init__(self, dependency_type: type, parameter_name: str):
        self.dependency_type = dependency_type
        self.parameter_name = parameter_name
        message = (
            f"Parameter '{parameter_name}' in {dependency_type.__name__}'s constructor "
            f"requires a type hint to be resolved by the container."
        )
        super().__init__(message)


class CircularDependencyError(ResolutionError):
    chain: list[type]

    def __init__(self, chain: list[type]):
        self.chain = chain

        type_names = [f"{t.__module__}.{t.__qualname__}" for t in chain]

        cycle = type_names
        first = type_names[0]
        if first in type_names[1:]:
            idx = type_names[1:].index(first) + 1
            cycle = type_names[: idx + 1]

        chain_str = " -> ".join(cycle)

        message = (
            "Circular dependency detected while resolving dependencies:\n"
            f"    {chain_str}\n"
            "The classes above depend on each other in a cycle. "
            "Check their __init__ signatures and dependency registrations."
        )

        super().__init__(message)


class UnregisteredDependencyError(ResolutionError):
    key: Key

    def __init__(self, key: Key):
        self.key = key

        if isinstance(key, str):
            key_repr = key
        else:
            key_repr = key.__name__

        message = f"Unregistered dependency for key {key_repr}."
        super().__init__(message)
