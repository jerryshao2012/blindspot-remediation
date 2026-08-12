from datetime import datetime, timezone

import pytest

from ai_engineering_orchestrator.errors import (
    InvalidStateTransitionError,
)
from ai_engineering_orchestrator.models import (
    OrchestrationRun,
    RunState,
    TaskRequest,
)
from ai_engineering_orchestrator.state_machine import (
    OrchestrationStateMachine,
)


NOW = datetime.now(timezone.utc)


def make_run() -> OrchestrationRun:
    task = TaskRequest(
        task_id="X1-001",
        task_type="X1",
        title="POC task",
        description="Apply the defined small engineering change.",
        repository_uri="https://example.invalid/engineering-poc",
        base_revision="abc123",
        requested_by="poc-operator",
        created_at=NOW,
    )

    return OrchestrationRun(
        run_id="run-001",
        task=task,
        task_definition_version="1.0.0",
        state=RunState.CREATED,
        started_at=NOW,
        updated_at=NOW,
    )


def test_valid_transition() -> None:
    machine = OrchestrationStateMachine()

    updated = machine.transition(
        make_run(),
        to_state=RunState.VALIDATING,
        reason="Beginning validation.",
    )

    assert updated.state == RunState.VALIDATING
    assert len(updated.transitions) == 1


def test_invalid_transition_is_rejected() -> None:
    machine = OrchestrationStateMachine()

    with pytest.raises(
        InvalidStateTransitionError
    ):
        machine.transition(
            make_run(),
            to_state=RunState.RELEASED,
            reason="This transition must never be possible.",
        )
