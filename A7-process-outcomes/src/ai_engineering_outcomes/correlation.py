"""
Outcome correlation.

Component 6 established:

    engineering run
        →
    release
        →
    deployment
        →
    runtime execution

Component 7 extends the spine:

    runtime execution
        →
    process instance
        →
    process outcome
        →
    KPI observation

Correlation is necessary for investigation.

Correlation alone is NOT sufficient for causal attribution.
"""

from __future__ import annotations

from .errors import OutcomeCorrelationError
from .models import ProcessEvent


class OutcomeCorrelationService:
    """Validate the stable identifiers carried by process events."""

    def validate_process_event(
        self,
        *,
        expected_deployment_id: str,
        expected_release_id: str,
        expected_originating_run_id: str,
        event: ProcessEvent,
    ) -> None:
        if event.deployment_id != expected_deployment_id:
            raise OutcomeCorrelationError(
                "Process event deployment_id does not match "
                "the expected deployment."
            )

        if event.release_id != expected_release_id:
            raise OutcomeCorrelationError(
                "Process event release_id does not match "
                "the expected release."
            )

        if (
            event.originating_run_id
            != expected_originating_run_id
        ):
            raise OutcomeCorrelationError(
                "Process event originating_run_id does not match "
                "the engineering run."
            )
