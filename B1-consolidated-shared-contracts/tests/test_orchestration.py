from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ai_engineering_contracts import (
    ArtifactReference,
    FinalDisposition,
    ResourceBudget,
    RunOutcome,
    RunState,
    RunUsageLedger,
    TaskSpecificationReference,
)


NOW = datetime.now(timezone.utc)


def specification_reference() -> TaskSpecificationReference:
    return TaskSpecificationReference(
        task_type="X1",
        version="1.0.0",
        sha256="a" * 64,
    )


def evidence() -> ArtifactReference:
    return ArtifactReference(
        artifact_id="run-evidence",
        uri="evidence://run-evidence",
        sha256="b" * 64,
        media_type="application/json",
        created_at=NOW,
        producer_component="EvidenceService",
    )


def test_released_outcome_is_valid() -> None:
    result = RunOutcome(
        run_id="run-1",
        task_id="task-1",
        task_type="X1",
        task_specification=specification_reference(),
        final_state=RunState.RELEASED,
        disposition=FinalDisposition.RELEASED,
        candidate_id="candidate-1",
        started_at=NOW,
        completed_at=NOW,
        usage=RunUsageLedger(),
        evidence=(evidence(),),
        reason_codes=("GATE_PASS",),
    )

    assert result.disposition == FinalDisposition.RELEASED


def test_released_disposition_cannot_use_gate_failed_state() -> None:
    with pytest.raises(ValidationError):
        RunOutcome(
            run_id="run-1",
            task_id="task-1",
            task_type="X1",
            task_specification=specification_reference(),
            final_state=RunState.GATE_FAILED,
            disposition=FinalDisposition.RELEASED,
            candidate_id="candidate-1",
            started_at=NOW,
            completed_at=NOW,
            usage=RunUsageLedger(),
            evidence=(evidence(),),
            reason_codes=(),
        )


def test_release_approval_is_not_pipeline_error() -> None:
    """
    Regression test for the temporary Component 9 POC compromise.

    Gate PASS + organizational approval requirement is now represented
    explicitly instead of being mislabeled as a pipeline failure.
    """

    result = RunOutcome(
        run_id="run-1",
        task_id="task-1",
        task_type="X1",
        task_specification=specification_reference(),
        final_state=RunState.RELEASE_APPROVAL_REQUIRED,
        disposition=FinalDisposition.RELEASE_APPROVAL_REQUIRED,
        candidate_id="candidate-1",
        started_at=NOW,
        completed_at=NOW,
        usage=RunUsageLedger(),
        evidence=(evidence(),),
        reason_codes=("EXTERNAL_RELEASE_APPROVAL_REQUIRED",),
    )

    assert (
        result.final_state
        == RunState.RELEASE_APPROVAL_REQUIRED
    )

