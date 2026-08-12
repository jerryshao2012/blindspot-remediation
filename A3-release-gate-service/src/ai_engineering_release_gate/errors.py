"""
Domain-specific errors for ReleaseGateService.

Expected gate failures normally become authoritative ControlResult records and a
structured GateResult. Errors that prevent the gate from constructing any
trustworthy evidence package are raised to the CLI and produce exit code 1.

No method intentionally returns ``None`` as an unexplained failure signal.
"""

from __future__ import annotations


class ReleaseGateError(Exception):
    """Base class for expected release-gate errors."""


class ConfigurationError(ReleaseGateError):
    """Raised when runtime, evaluation, or policy configuration is invalid."""


class ArtifactError(ReleaseGateError):
    """Raised when an artifact cannot be read, verified, parsed, or stored."""


class ArtifactIntegrityError(ArtifactError):
    """Raised when artifact content does not match its SHA-256 digest."""


class UnsupportedArtifactLocationError(ArtifactError):
    """Raised when the POC receives an unsupported artifact URI scheme."""


class CandidateIntegrityError(ReleaseGateError):
    """Raised when candidate patch provenance is inconsistent with GateRequest."""


class RepositoryError(ReleaseGateError):
    """Raised when the clean repository workspace cannot be prepared."""


class PatchValidationError(RepositoryError):
    """Raised when a candidate patch cannot be cleanly reconstructed."""


class ScopeViolationError(RepositoryError):
    """Raised when the candidate modifies an unauthorized repository path."""


class WorkspaceContaminationError(RepositoryError):
    """Raised when an assurance control modifies tracked candidate source."""


class CommandExecutionError(ReleaseGateError):
    """Raised when an assurance command cannot be started."""


class CommandTimeoutError(CommandExecutionError):
    """Raised when an assurance command exceeds its allowed runtime."""


class EvidenceBudgetExceeded(ReleaseGateError):
    """Raised when the deterministic gate consumes its execution budget."""


class EvidenceParsingError(ReleaseGateError):
    """Raised when a required evidence report cannot be parsed reliably."""


class PolicyEvaluationError(ReleaseGateError):
    """Raised when release policy cannot be evaluated deterministically."""
