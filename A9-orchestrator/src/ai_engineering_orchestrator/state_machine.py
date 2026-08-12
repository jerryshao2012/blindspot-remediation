"""
Deterministic orchestration state machine.

This is intentionally boring.

That is desirable.

The workflow authority should be:

    explicit
    testable
    versionable
    auditable

rather than hidden inside an LLM conversation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .errors import InvalidStateTransitionError
from .models import (
    OrchestrationRun,
    RunState,
    StateTransition,
)


ALLOWED_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset({
        RunState.VALIDATING,
        RunState.CANCELLED,
    }),

    RunState.VALIDATING: frozenset({
        RunState.READY,
        RunState.FAILED_VALIDATION,
        RunState.CANCELLED,
    }),

    RunState.READY: frozenset({
        RunState.EXECUTING_CHANGE,
        RunState.CANCELLED,
    }),

    RunState.EXECUTING_CHANGE: frozenset({
        RunState.CANDIDATE_AVAILABLE,
        RunState.CHANGE_FAILED,
        RunState.BUDGET_EXCEEDED,
        RunState.PIPELINE_ERROR,
        RunState.CANCELLED,
    }),

    RunState.CANDIDATE_AVAILABLE: frozenset({
        RunState.GATING,
        RunState.CANCELLED,
    }),

    RunState.GATING: frozenset({
        RunState.READY_FOR_RELEASE,
        RunState.GATE_FAILED,
        RunState.MORE_EVIDENCE,
        RunState.HUMAN_REVIEW_REQUIRED,
        RunState.BUDGET_EXCEEDED,
        RunState.PIPELINE_ERROR,
        RunState.CANCELLED,
    }),

    RunState.MORE_EVIDENCE: frozenset({
        RunState.GATING,
        RunState.HUMAN_REVIEW_REQUIRED,
        RunState.GATE_FAILED,
        RunState.BUDGET_EXCEEDED,
        RunState.PIPELINE_ERROR,
        RunState.CANCELLED,
    }),

    RunState.READY_FOR_RELEASE: frozenset({
        RunState.RELEASED,
        RunState.PIPELINE_ERROR,
        RunState.CANCELLED,
    }),

    RunState.FAILED_VALIDATION: frozenset(),
    RunState.CHANGE_FAILED: frozenset(),
    RunState.GATE_FAILED: frozenset(),
    RunState.HUMAN_REVIEW_REQUIRED: frozenset(),
    RunState.RELEASED: frozenset(),
    RunState.BUDGET_EXCEEDED: frozenset(),
    RunState.PIPELINE_ERROR: frozenset(),
    RunState.CANCELLED: frozenset(),
}


TERMINAL_STATES = frozenset({
    RunState.FAILED_VALIDATION,
    RunState.CHANGE_FAILED,
    RunState.GATE_FAILED,
    RunState.HUMAN_REVIEW_REQUIRED,
    RunState.RELEASED,
    RunState.BUDGET_EXCEEDED,
    RunState.PIPELINE_ERROR,
    RunState.CANCELLED,
})


class OrchestrationStateMachine:
    """Authoritative workflow-transition implementation."""

    def transition(
        self,
        run: OrchestrationRun,
        *,
        to_state: RunState,
        reason: str,
        evidence_reference: str | None = None,
    ) -> OrchestrationRun:
        allowed = ALLOWED_TRANSITIONS[run.state]

        if to_state not in allowed:
            raise InvalidStateTransitionError(
                f"Transition {run.state.value!r} -> "
                f"{to_state.value!r} is not permitted."
            )

        now = datetime.now(timezone.utc)

        transition = StateTransition(
            from_state=run.state,
            to_state=to_state,
            timestamp=now,
            reason=reason,
            evidence_reference=evidence_reference,
        )

        return run.model_copy(
            update={
                "state": to_state,
                "updated_at": now,
                "transitions": (
                    *run.transitions,
                    transition,
                ),
            }
        )

    @staticmethod
    def is_terminal(state: RunState) -> bool:
        return state in TERMINAL_STATES
