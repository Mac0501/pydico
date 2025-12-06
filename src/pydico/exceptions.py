class ContainerError(Exception):
    pass


class RegistrationError(ContainerError):
    def __init__(self, interface_type: type, dependency_type: type, message: str):
        self.interface_type = interface_type
        self.dependency_type = dependency_type
        super().__init__(message)


class ImplementationMismatchError(RegistrationError):
    def __init__(self, interface_type: type, dependency_type: type):
        message = (
            f"Implementation {dependency_type.__name__} must be a subclass "
            f"of interface {interface_type.__name__}."
        )
        super().__init__(interface_type, dependency_type, message)


class AbstractDependencyError(RegistrationError):
    def __init__(self, interface_type: type, dependency_type: type):
        message = (
            f"Cannot register abstract class {dependency_type.__name__} as a dependency. "
            f"An abstract class cannot be instantiated directly."
        )
        super().__init__(interface_type, dependency_type, message)


class InstanceTypeError(RegistrationError):
    def __init__(self, interface_type: type, instance_object: object):
        self.instance_object = instance_object
        dependency_type = type(instance_object)

        message = (
            f"Object {instance_object!r} is of type {dependency_type.__name__} "
            f"but is not an instance of the required type {interface_type.__name__}."
        )
        super().__init__(interface_type, dependency_type, message)


class ResolutionError(ContainerError):
    def __init__(
        self,
        requesting_type: type,
        dependency_name: str | None = None,
        message: str | None = None,
    ):
        self.requesting_type = requesting_type
        self.dependency_name = dependency_name

        if message is None:
            message = (
                f"Error resolving dependencies for class: {requesting_type.__name__}"
            )
            if dependency_name:
                message += f" (affected parameter: '{dependency_name}')"

        super().__init__(message)


class MissingTypeHintError(ResolutionError):
    def __init__(self, requesting_type: type, dependency_name: str):
        message = (
            f"Parameter '{dependency_name}' in {requesting_type.__name__}'s constructor "
            f"requires a type hint to be resolved by the container."
        )
        super().__init__(requesting_type, dependency_name, message)


class CircularDependencyError(ResolutionError):
    def __init__(self, requesting_type: type, dependency_name: str):
        message = (
            f"Circular dependency detected while resolving '{dependency_name}' "
            f"for class {requesting_type.__name__}. Check the dependency chain."
        )
        super().__init__(requesting_type, dependency_name, message)


class UnregisteredDependencyError(ResolutionError):
    def __init__(
        self, requesting_type: type, dependency_name: str, requested_type: type
    ):
        self.requested_type = requested_type
        message = (
            f"Unregistered dependency (Type: {requested_type.__name__}) "
            f"requested by class {requesting_type.__name__} for parameter '{dependency_name}'."
        )
        super().__init__(requesting_type, dependency_name, message)


class InstantiationError(ResolutionError):
    def __init__(self, implementation_type: type, original_exception: Exception):
        self.original_exception = original_exception

        message = (
            f"Failed to instantiate class {implementation_type.__name__}. "
            f"The constructor raised an unexpected error: "
            f"{original_exception.__class__.__name__}: {original_exception}"
        )
        # Note: InstantiationError reports the implementation_type as the 'requesting_type'
        # in the ResolutionError base class, which is logical here.
        super().__init__(implementation_type, None, message)
