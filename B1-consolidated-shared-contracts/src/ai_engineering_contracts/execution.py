"""
Shared boundary contracts for Component 10.

Only contracts exchanged BETWEEN components live here.

Component 10's low-level:

    SandboxProfile
    RunnerResult
    AzureContainerAppsJobRunner

remain private to Component 10.

This prevents Component 1 from becoming coupled to one execution technology.
"""

from __future__ import annotations

from pydantic import Field
from typing_extensions import Annotated

from .base import (
    AwareDatetime,
    CONTRACT_SCHEMA_VERSION,
    ContractModel,
)
from .enums import (
    ExecutionStatus,
    SandboxRole,
)
from .ids import (
    RunId,
    Sha256Digest,
)
from .references import ArtifactReference


class ExecutionCommand(ContractModel):
    """
    Structured command rather than a shell string.

    This avoids making shell parsing part of the shared contract.

    Component 10 remains responsible for enforcing the executable allow-list.
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


class ExecutionRequest(ContractModel):
    schema_version: str = CONTRACT_SCHEMA_VERSION

    request_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    run_id: RunId

    component_name: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    role: SandboxRole

    profile_id: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    inputs: tuple[
        ArtifactReference,
        ...,
    ]

    command: ExecutionCommand

    created_at: AwareDatetime

    metadata: dict[str, str] = Field(
        default_factory=dict
    )


class ExecutionOutput(ContractModel):
    name: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    artifact: ArtifactReference


class ExecutionReceipt(ContractModel):
    """
    Evidence returned by Component 10.

    It proves the execution event and environment identity.

    It does NOT prove that the software was semantically correct.
    """

    schema_version: str = CONTRACT_SCHEMA_VERSION

    request_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    run_id: RunId

    sandbox_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    profile_id: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    role: SandboxRole

    status: ExecutionStatus

    runner_image: Annotated[
        str,
        Field(min_length=1),
    ]

    runner_image_digest: Annotated[
        str,
        Field(pattern=r"^sha256:[0-9a-f]{64}$"),
    ]

    started_at: AwareDatetime
    completed_at: AwareDatetime

    exit_code: int | None

    stdout_sha256: Sha256Digest
    stderr_sha256: Sha256Digest

    stdout_bytes: Annotated[
        int,
        Field(ge=0),
    ]

    stderr_bytes: Annotated[
        int,
        Field(ge=0),
    ]

    outputs: tuple[
        ExecutionOutput,
        ...,
    ]

    environment_fingerprint: Sha256Digest
    policy_fingerprint: Sha256Digest

    cleanup_completed: bool

    failure_reason: str | None = None

