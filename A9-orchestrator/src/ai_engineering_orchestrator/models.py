"""
Strict contracts for the orchestration control plane.

These contracts deliberately distinguish:

    task
    task definition
    orchestration run
    component invocation
    component result
    gate disposition
    run outcome

This prevents a Jira ticket, AI conversation, candidate patch, and released
change from becoming conflated into one mutable object.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from .errors import TaskDefinitionError


class OrchestratorModel(BaseModel):
    """Immutable strict base model."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class RunState(StrEnum):
    CREATED = "created"
    VALIDATING = "validating"
    READY = "ready"
    EXECUTING_CHANGE = "executing_change"
    CANDIDATE_AVAILABLE = "candidate_available"
    GATING = "gating"
    MORE_EVIDENCE = "more_evidence"
    READY_FOR_RELEASE = "ready_for_release"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    RELEASED = "released"

    FAILED_VALIDATION = "failed_validation"
    CHANGE_FAILED = "change_failed"
    GATE_FAILED = "gate_failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    PIPELINE_ERROR = "pipeline_error"
    CANCELLED = "cancelled"


class GateDisposition(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"


class FinalDisposition(StrEnum):
    RELEASED = "released"
    REJECTED = "rejected"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    BUDGET_EXCEEDED = "budget_exceeded"
    PIPELINE_ERROR = "pipeline_error"
    CANCELLED = "cancelled"


class TaskRequest(OrchestratorModel):
    """
    Normalized engineering work request.

    Jira-specific fields should be converted into this contract by an adapter.
    """

    task_id: Annotated[str, Field(min_length=1, max_length=256)]
    task_type: Annotated[str, Field(min_length=1, max_length=128)]

    title: Annotated[str, Field(min_length=1, max_length=512)]
    description: Annotated[str, Field(min_length=1)]

    repository_uri: Annotated[str, Field(min_length=1)]
    base_revision: Annotated[str, Field(min_length=1, max_length=256)]

    requested_by: Annotated[str, Field(min_length=1, max_length=256)]
    created_at: datetime

    metadata: dict[str, str] = Field(default_factory=dict)


class ResourceBudget(OrchestratorModel):
    """
    Hard ceilings for one orchestration run.

    Budgets are safety and economics controls.

    They are not predictions.
    """

    maximum_execution_attempts: Annotated[int, Field(ge=1)] = 2

    maximum_gate_attempts: Annotated[int, Field(ge=1)] = 3

    maximum_total_llm_input_tokens: Annotated[
        int,
        Field(ge=0),
    ] = 500_000

    maximum_total_llm_output_tokens: Annotated[
        int,
        Field(ge=0),
    ] = 100_000

    maximum_total_llm_requests: Annotated[
        int,
        Field(ge=0),
    ] = 200

    maximum_elapsed_seconds: Annotated[
        int,
        Field(ge=1),
    ] = 7_200


class TaskDefinition(OrchestratorModel):
    """
    Versioned definition of one supported task family.

    The task definition tells the control plane what is permitted.

    It does not contain model-generated runtime reasoning.
    """

    task_type: Annotated[str, Field(min_length=1, max_length=128)]

    definition_version: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]

    enabled: bool = True

    skill_reference: Annotated[
        str,
        Field(min_length=1),
    ]

    change_execution_profile: Annotated[
        str,
        Field(min_length=1),
    ]

    release_gate_profile: Annotated[
        str,
        Field(min_length=1),
    ]

    required_evidence_types: tuple[str, ...]

    allowed_repository_patterns: tuple[str, ...]

    budget: ResourceBudget

    maximum_more_evidence_cycles: Annotated[
        int,
        Field(ge=0),
    ] = 2

    automatic_release_allowed: bool = False

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        if not self.required_evidence_types:
            raise ValueError(
                "At least one required evidence type must be configured."
            )

        if not self.allowed_repository_patterns:
            raise ValueError(
                "At least one repository pattern must be configured."
            )

        return self

    @classmethod
    def from_yaml(cls, path: Path) -> "TaskDefinition":
        try:
            raw = yaml.safe_load(
                path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            raise TaskDefinitionError(
                f"Unable to read task definition {path}: {exc}"
            ) from exc

        try:
            return cls.model_validate(raw)
        except Exception as exc:
            raise TaskDefinitionError(
                f"Invalid task definition {path}: {exc}"
            ) from exc


class CandidatePatch(OrchestratorModel):
    """Reference to the immutable output of ChangeExecutionService."""

    candidate_id: Annotated[str, Field(min_length=1, max_length=256)]
    task_id: Annotated[str, Field(min_length=1, max_length=256)]
    run_id: Annotated[str, Field(min_length=1, max_length=256)]

    base_revision: Annotated[str, Field(min_length=1)]
    candidate_revision: Annotated[str, Field(min_length=1)]

    evidence_reference: Annotated[str, Field(min_length=1)]

    created_at: datetime


class ChangeExecutionResult(OrchestratorModel):
    """Normalized response from Component 2."""

    succeeded: bool

    candidate: CandidatePatch | None = None

    input_tokens: Annotated[int, Field(ge=0)] = 0
    output_tokens: Annotated[int, Field(ge=0)] = 0
    llm_requests: Annotated[int, Field(ge=0)] = 0

    failure_code: str | None = None
    failure_message: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.succeeded and self.candidate is None:
            raise ValueError(
                "Successful execution must provide a candidate."
            )

        if not self.succeeded and self.candidate is not None:
            raise ValueError(
                "Failed execution cannot provide a candidate."
            )

        return self


class ReleaseGateResult(OrchestratorModel):
    """Normalized response from Component 3."""

    disposition: GateDisposition

    evidence_reference: Annotated[str, Field(min_length=1)]

    input_tokens: Annotated[int, Field(ge=0)] = 0
    output_tokens: Annotated[int, Field(ge=0)] = 0
    llm_requests: Annotated[int, Field(ge=0)] = 0

    reason_codes: tuple[str, ...] = ()

    requested_evidence_types: tuple[str, ...] = ()


class UsageLedger(OrchestratorModel):
    """Cumulative AI-resource usage for one run."""

    input_tokens: Annotated[int, Field(ge=0)] = 0
    output_tokens: Annotated[int, Field(ge=0)] = 0
    llm_requests: Annotated[int, Field(ge=0)] = 0

    execution_attempts: Annotated[int, Field(ge=0)] = 0
    gate_attempts: Annotated[int, Field(ge=0)] = 0
    more_evidence_cycles: Annotated[int, Field(ge=0)] = 0


class StateTransition(OrchestratorModel):
    """Immutable state-transition evidence."""

    from_state: RunState
    to_state: RunState
    timestamp: datetime
    reason: Annotated[str, Field(min_length=1)]
    evidence_reference: str | None = None


class OrchestrationRun(OrchestratorModel):
    """
    Complete control-plane state for one engineering automation run.

    The run freezes the task-definition version used for execution.
    """

    run_id: Annotated[str, Field(min_length=1, max_length=256)]

    task: TaskRequest

    task_definition_version: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]

    state: RunState

    started_at: datetime
    updated_at: datetime

    usage: UsageLedger = Field(default_factory=UsageLedger)

    candidate: CandidatePatch | None = None

    transitions: tuple[StateTransition, ...] = ()


class RunOutcome(OrchestratorModel):
    """Terminal result emitted by Component 9."""

    run_id: str
    task_id: str
    task_type: str

    final_state: RunState
    disposition: FinalDisposition

    candidate_id: str | None

    started_at: datetime
    completed_at: datetime

    usage: UsageLedger

    evidence_references: tuple[str, ...]

    reason_codes: tuple[str, ...]
