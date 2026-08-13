from datetime import datetime, timezone

import pytest

from ai_engineering_outcomes.correlation import (
    OutcomeCorrelationService,
)
from ai_engineering_outcomes.errors import (
    OutcomeCorrelationError,
)
from ai_engineering_outcomes.models import (
    ProcessEvent,
    ProcessEventType,
)


NOW = datetime.now(timezone.utc)


def process_event(
    deployment_id: str = "deployment-1",
) -> ProcessEvent:
    return ProcessEvent(
        event_id="event-1",
        process_instance_id="process-1",
        process_name="mortgage-processing",
        event_type=ProcessEventType.COMPLETED,
        timestamp=NOW,
        deployment_id=deployment_id,
        release_id="release-1",
        originating_run_id="run-1",
        duration_ms=1000,
    )


def test_correct_correlation() -> None:
    OutcomeCorrelationService().validate_process_event(
        expected_deployment_id="deployment-1",
        expected_release_id="release-1",
        expected_originating_run_id="run-1",
        event=process_event(),
    )


def test_wrong_deployment_is_rejected() -> None:
    with pytest.raises(
        OutcomeCorrelationError
    ):
        OutcomeCorrelationService().validate_process_event(
            expected_deployment_id="deployment-1",
            expected_release_id="release-1",
            expected_originating_run_id="run-1",
            event=process_event(
                deployment_id="deployment-2"
            ),
        )
