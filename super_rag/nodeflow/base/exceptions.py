


class nodeflowError(Exception):
    """Base exception for nodeflow engine"""

    pass


class CycleError(nodeflowError):
    """Raised when a cycle is detected in the nodeflow graph"""

    pass


class TypeMismatchError(nodeflowError):
    """Raised when input/output types don't match"""

    pass


class NodeNotFoundError(nodeflowError):
    """Raised when a node is not found"""

    pass


class ValidationError(nodeflowError):
    """Raised when input validation fails"""

    pass
