"""Typed failures for Component 10."""


class ExecutionEnvironmentError(Exception):
    """Base class for controlled environment failures."""


class SandboxPolicyError(ExecutionEnvironmentError):
    """Requested execution violates the selected sandbox policy."""


class SandboxProvisioningError(ExecutionEnvironmentError):
    """The execution environment could not be provisioned."""


class SandboxExecutionError(ExecutionEnvironmentError):
    """Infrastructure failed while executing the workload."""


class SandboxTimeoutError(ExecutionEnvironmentError):
    """The sandbox exceeded its wall-clock execution limit."""


class ArtifactIntegrityError(ExecutionEnvironmentError):
    """An artifact failed integrity validation."""


class OutputLimitExceededError(ExecutionEnvironmentError):
    """Sandbox output exceeded the configured evidence limit."""


class UnsupportedSandboxRoleError(ExecutionEnvironmentError):
    """No sandbox profile exists for the requested execution role."""
