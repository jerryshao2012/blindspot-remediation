"""Typed failures for Component 9."""


class OrchestratorError(Exception):
    """Base class for expected orchestration failures."""


class TaskDefinitionError(OrchestratorError):
    """A task definition is missing, malformed, or inconsistent."""


class InvalidStateTransitionError(OrchestratorError):
    """The requested workflow transition is not permitted."""


class BudgetExceededError(OrchestratorError):
    """A configured execution budget has been exhausted."""


class ComponentInvocationError(OrchestratorError):
    """A downstream component failed unexpectedly."""


class EvidencePersistenceError(OrchestratorError):
    """Required orchestration evidence could not be persisted."""


class DuplicateRunError(OrchestratorError):
    """A run identifier already exists."""


class UnsupportedTaskTypeError(OrchestratorError):
    """No registered definition exists for the requested task type."""
