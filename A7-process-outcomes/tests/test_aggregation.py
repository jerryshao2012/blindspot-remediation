from datetime import datetime, timedelta, timezone

from ai_engineering_outcomes.aggregation import (
    ProcessMetricsCalculator,
)
from ai_engineering_outcomes.models import (
    ProcessEvent,
    ProcessEventType,
)


NOW = datetime.now(timezone.utc)


def event(
    *,
    event_id: str,
    instance: str,
    event_type: ProcessEventType,
    seconds: int,
    duration_ms: float | None = None,
) -> ProcessEvent:
    return ProcessEvent(
        event_id=event_id,
        process_instance_id=instance,
        process_name="mortgage-processing",
        event_type=event_type,
        timestamp=NOW + timedelta(seconds=seconds),
        deployment_id="deployment-1",
        release_id="release-1",
        originating_run_id="run-1",
        duration_ms=duration_ms,
    )


def test_process_instances_are_not_double_counted() -> None:
    events = (
        event(
            event_id="1",
            instance="mortgage-1",
            event_type=ProcessEventType.STARTED,
            seconds=1,
        ),
        event(
            event_id="2",
            instance="mortgage-1",
            event_type=ProcessEventType.MANUAL_INTERVENTION,
            seconds=2,
        ),
        event(
            event_id="3",
            instance="mortgage-1",
            event_type=ProcessEventType.COMPLETED,
            seconds=3,
            duration_ms=1000,
        ),
        event(
            event_id="4",
            instance="mortgage-2",
            event_type=ProcessEventType.STARTED,
            seconds=4,
        ),
        event(
            event_id="5",
            instance="mortgage-2",
            event_type=ProcessEventType.COMPLETED,
            seconds=5,
            duration_ms=2000,
        ),
    )

    window = ProcessMetricsCalculator().calculate(
        deployment_id="deployment-1",
        process_name="mortgage-processing",
        events=events,
        window_start=NOW,
        window_end=NOW + timedelta(minutes=5),
    )

    assert window.process_instances == 2

    assert window.completed_instances == 2

    assert window.manual_intervention_instances == 1

    assert window.completion_rate == 1.0

    assert window.manual_intervention_rate == 0.5

    assert window.mean_completion_duration_ms == 1500
