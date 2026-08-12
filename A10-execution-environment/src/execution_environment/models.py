"""
Strict contracts for Component 10.

An execution request is deliberately different from an arbitrary shell session.

Every request specifies:

    identity
    trust role
    immutable input artifacts
    command
    resource limits
    network policy
    output policy

Every execution returns a receipt.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class SandboxRole(StrEnum):
    CHANGE_EXECUTION = "change_execution"
    RELEASE_GATE = "release_gate"
    BENCHMARK = "benchmark"


class ExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    COMMAND_FAILED = "command_failed"
    TIMED_OUT = "timed_out"
    POLICY_DENIED = "policy_denied"
    INFRASTRUCTURE_FAILED = "infrastructure_failed"


class NetworkMode(StrEnum):
    DENY_ALL = "deny_all"
    ALLOW_LIST = "allow_list"


class ArtifactReference(EnvironmentModel):
    """
    Immutable artifact supplied to a sandbox.

    The SHA-256 digest is mandatory.

    Component 10 never accepts an input whose integrity cannot be checked.
    """

    artifact_id: Annotated[str, Field(min_length=1, max_length=256)]

    uri: Annotated[str, Field(min_length=1)]

    sha256: Annotated[
        str,
        Field(pattern=r"^[0-9a-f]{64}$"),
    ]

    media_type: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]


class ResourceLimits(EnvironmentModel):
    """Hard execution ceilings."""

    wall_clock_seconds: Annotated[
        int,
        Field(ge=1, le=7200),
    ] = 900

    cpu_cores: Annotated[
        float,
        Field(gt=0, le=8),
    ] = 2.0

    memory_mb: Annotated[
        int,
        Field(ge=128, le=32768),
    ] = 4096

    output_bytes: Annotated[
        int,
        Field(ge=1024, le=100_000_000),
    ] = 10_000_000


class NetworkPolicy(EnvironmentModel):
    mode: NetworkMode = NetworkMode.DENY_ALL

    allowed_hosts: tuple[str, ...] = ()


class SandboxProfile(EnvironmentModel):
    """
    Approved execution profile.

    The runner image is pinned by digest.

    Tags such as ':latest' are intentionally insufficient for a reproducible
    environment.
    """

    profile_id: Annotated[str, Field(min_length=1, max_length=128)]

    role: SandboxRole

    runner_image: Annotated[str, Field(min_length=1)]

    runner_image_digest: Annotated[
        str,
        Field(pattern=r"^sha256:[0-9a-f]{64}$"),
    ]

    limits: ResourceLimits

    network: NetworkPolicy

    allowed_executables: tuple[str, ...]

    environment_variables: dict[str, str] = Field(
        default_factory=dict
    )

    allow_production_credentials: bool = False

    preserve_workspace_after_execution: bool = False


class ExecutionCommand(EnvironmentModel):
    """
    Structured command.

    Commands are represented as argument arrays rather than shell strings.

    This prevents the environment service itself from requiring shell parsing.
    """

    executable: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    arguments: tuple[str, ...] = ()

    working_directory: Annotated[
        str,
        Field(min_length=1),
    ] = "/workspace"

    environment: dict[str, str] = Field(
        default_factory=dict
    )


class ExecutionRequest(EnvironmentModel):
    request_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    run_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    component_name: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    role: SandboxRole

    profile_id: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    inputs: tuple[ArtifactReference, ...]

    command: ExecutionCommand

    created_at: datetime

    metadata: dict[str, str] = Field(
        default_factory=dict
    )


class ExecutionOutput(EnvironmentModel):
    """
    Artifact produced by an execution.

    Large binary content is not embedded in the receipt.
    """

    name: Annotated[str, Field(min_length=1)]

    artifact_reference: ArtifactReference


class ExecutionReceipt(EnvironmentModel):
    """
    Immutable evidence describing one sandbox execution.

    The receipt is important to both Component 3 and Component 4.
    """

    request_id: str
    run_id: str

    sandbox_id: str

    profile_id: str
    role: SandboxRole

    status: ExecutionStatus

    runner_image: str
    runner_image_digest: str

    started_at: datetime
    completed_at: datetime

    exit_code: int | None

    stdout_sha256: str
    stderr_sha256: str

    stdout_bytes: int
    stderr_bytes: int

    outputs: tuple[ExecutionOutput, ...]

    environment_fingerprint: str

    policy_fingerprint: str

    cleanup_completed: bool

    failure_reason: str | None = None


class RunnerResult(EnvironmentModel):
    """
    Result returned by the infrastructure-specific runner.

    This object is deliberately lower-level than ExecutionReceipt.
    """

    sandbox_id: str

    status: ExecutionStatus

    started_at: datetime
    completed_at: datetime

    exit_code: int | None

    stdout: bytes
    stderr: bytes

    outputs: tuple[ExecutionOutput, ...]

    cleanup_completed: bool

    failure_reason: str | None = None
