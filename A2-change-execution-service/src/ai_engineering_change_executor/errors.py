"""
Domain-specific exceptions for ChangeExecutionService.

The service converts expected domain failures into a structured ExecutionResult.
Unexpected programming errors are also captured as a failed ExecutionResult,
but their exception type is retained in the execution trace.

No method in this component returns an unexplained ``None`` to signal failure.
"""

from __future__ import annotations


class ChangeExecutorError(Exception):
    """Base class for expected executor failures."""


class ConfigurationError(ChangeExecutorError):
    """Raised when executor configuration is invalid or incomplete."""


class ArtifactError(ChangeExecutorError):
    """Raised when an input or output artifact cannot be validated or stored."""


class ArtifactIntegrityError(ArtifactError):
    """Raised when retrieved artifact bytes do not match their recorded digest."""


class UnsupportedArtifactLocationError(ArtifactError):
    """
    Raised when the POC artifact loader receives an unsupported URI.

    The initial implementation intentionally reads local ``file://`` artifacts
    only. Azure Blob support will be added through a separate artifact-provider
    implementation rather than by embedding Azure logic in the executor.
    """


class CommandExecutionError(ChangeExecutorError):
    """Raised when a required external command cannot be executed."""


class CommandTimeoutError(CommandExecutionError):
    """Raised when a command exceeds its permitted runtime."""


class ExecutionBudgetExceeded(ChangeExecutorError):
    """Raised when the task's deterministic execution budget is exhausted."""


class RepositoryError(ChangeExecutorError):
    """Raised when repository preparation or Git processing fails."""


class PatchValidationError(RepositoryError):
    """Raised when the supplied patch is malformed or cannot be cleanly applied."""


class EmptyPatchError(PatchValidationError):
    """Raised when applying the patch produces no staged repository change."""


class ScopeViolationError(RepositoryError):
    """Raised when the candidate modifies a path outside the permitted scope."""


class WorkspaceMutationError(RepositoryError):
    """
    Raised when a local check modifies tracked source files.

    Checks may create ignored build outputs or temporary files, but they must not
    silently alter the candidate after it has been staged.
    """


class LocalCheckConfigurationError(ConfigurationError):
    """Raised when a configured local check is unsafe or malformed."""
