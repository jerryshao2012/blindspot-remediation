"""
Canonical orchestration boundary contracts.

Component 9 still owns:

    state transition implementation
    retry logic
    budget enforcement
    component invocation
    cancellation logic

The shared package owns the DATA exchanged with Components 4, 5, 8 and 12.
"""

from __future__ import annotations

from pydantic import (
    Field,
    model_validator,
)
from typing_extensions import (
    Annotated,
    Self,
)

from .base import (
    AwareDatetime,
    CONTRACT_SCHEMA_VERSION,
    ContractModel,
)
from .candidate import CandidateArtifact
from .enums import (
    FinalDisposition,
    RunState,
)
from .ids import (
    RunId,
)
from .references import (
    ArtifactReference,
    TaskSpecificationReference,
)
from .task import TaskRequest
from .usage import RunUsageLedger


TERMINAL_RUN_STATES = frozenset({
    RunState.RELEASED,
    RunState.RELEASE_APPROVAL_REQUIRED,
    RunState.HUMAN_REVIEW_REQUIRED,
    RunState.FAILED_VALIDATION,
    RunState.CHANGE_FAILED,
    RunState.GATE_FAILED,
    RunState.BUDGET_EXCEEDED,
    RunState.PIPELINE_ERROR,
    RunState.CANCELLED,
})


class StateTransition(ContractModel):
    from_state: RunState
    to_state: RunState

    timestamp: AwareDatetime

    reason: Annotated[
        str,
        Field(min_length=1, max_length=4096),
    ]

    evidence: ArtifactReference | None = None


class OrchestrationRun(ContractModel):
    schema_version: str = CONTRACT_SCHEMA_VERSION

    run_id: RunId

    task: TaskRequest

    # The exact specification is frozen BEFORE Component 2 is invoked.
    task_specification: TaskSpecificationReference

    state: RunState

    started_at: AwareDatetime
    updated_at: AwareDatetime

    usage: RunUsageLedger = Field(
        default_factory=RunUsageLedger
    )

    candidate: CandidateArtifact | None = None

    transitions: tuple[
        StateTransition,
        ...,
    ] = ()

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        if self.updated_at < self.started_at:
            raise ValueError(
                "OrchestrationRun.updated_at cannot precede started_at."
            )

        return self


class RunOutcome(ContractModel):
    """
    Terminal orchestration result consumed by Components 4, 5, 8 and 12.
    """

    schema_version: str = CONTRACT_SCHEMA_VERSION

    run_id: RunId

    task_id: str
    task_type: str

    task_specification: TaskSpecificationReference

    final_state: RunState
    disposition: FinalDisposition

    candidate_id: str | None

    started_at: AwareDatetime
    completed_at: AwareDatetime

    usage: RunUsageLedger

    evidence: tuple[
        ArtifactReference,
        ...,
    ]

    reason_codes: tuple[
        str,
        ...,
    ]

    @model_validator(mode="after")
    def validate_terminal_result(self) -> Self:
        if self.final_state not in TERMINAL_RUN_STATES:
            raise ValueError(
                "RunOutcome requires a terminal RunState."
            )

        if self.completed_at < self.started_at:
            raise ValueError(
                "RunOutcome.completed_at cannot precede started_at."
            )

        expected: dict[
            FinalDisposition,
            set[RunState],
        ] = {
            FinalDisposition.RELEASED: {
                RunState.RELEASED,
            },
            FinalDisposition.RELEASE_APPROVAL_REQUIRED: {
                RunState.RELEASE_APPROVAL_REQUIRED,
            },
            FinalDisposition.HUMAN_REVIEW_REQUIRED: {
                RunState.HUMAN_REVIEW_REQUIRED,
            },
            FinalDisposition.BUDGET_EXCEEDED: {
                RunState.BUDGET_EXCEEDED,
            },
            FinalDisposition.PIPELINE_ERROR: {
                RunState.PIPELINE_ERROR,
            },
            FinalDisposition.CANCELLED: {
                RunState.CANCELLED,
            },
            FinalDisposition.REJECTED: {
                RunState.FAILED_VALIDATION,
                RunState.CHANGE_FAILED,
                RunState.GATE_FAILED,
            },
        }

        if self.final_state not in expected[self.disposition]:
            raise ValueError(
                "RunOutcome final_state and disposition are inconsistent: "
                f"{self.final_state.value} / {self.disposition.value}."
            )

        return self

