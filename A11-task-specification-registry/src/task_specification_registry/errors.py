"""Typed failures for Component 11."""


class TaskSpecificationError(Exception):
    """Base class for registry failures."""


class SpecificationNotFoundError(TaskSpecificationError):
    """Requested task specification does not exist."""


class SpecificationValidationError(TaskSpecificationError):
    """Specification violates structural or semantic requirements."""


class SpecificationIntegrityError(TaskSpecificationError):
    """Stored specification does not match its expected content digest."""


class SpecificationNotApprovedError(TaskSpecificationError):
    """Specification exists but is not approved for execution."""


class DuplicateSpecificationError(TaskSpecificationError):
    """An immutable specification identity already exists."""


class CapabilityNotQualifiedError(TaskSpecificationError):
    """Task capability has not reached the required qualification state."""


class IncompatibleSpecificationError(TaskSpecificationError):
    """Referenced component contracts are mutually incompatible."""
