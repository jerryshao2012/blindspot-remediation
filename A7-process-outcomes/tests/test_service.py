from datetime import datetime, timedelta, timezone

from ai_engineering_outcomes.aggregation import (
    ProcessMetricsCalculator,
)
from ai_engineering_outcomes.attribution import (
    AttributionAssessor,
)
from ai_engineering_outcomes.correlation import (
    OutcomeCorrelationService,
)
from ai_engineering_outcomes.models import (
    ProcessEvent,
    ProcessEventType,
)
from ai_engineering_outcomes.service import (
    ProcessOutcomeService,
)
from ai_engineering_outcomes.storage import (
    OutcomeEvidenceRepository,
)


NOW = datetime.now(timezone.utc)


class InMemoryRepository(OutcomeEvidenceRepository):
    def __init__(self) -> None:
        self.events = []
        self.windows = []
        self.kpis = []
        self.attributions = []

    def write_process_event(self, event):
        self.events.append(event)

    def process_events_for_deployment(self, deployment_id):
        return tuple(
            event
            for event in self.events
            if event.deployment_id == deployment_id
        )

    def write_process_window(self, window):
        self.windows.append(window)

    def write_kpi_observation(self, observation):
        self.kpis.append(observation)

    def write_attribution_assessment(self, assessment):
        self.attributions.append(assessment)


def test_complete_process_outcome_flow() -> None:
    repository = InMemoryRepository()

    service = ProcessOutcomeService(
        repository=repository,
        correlation=OutcomeCorrelationService(),
        calculator=ProcessMetricsCalculator(),
        attribution=AttributionAssessor(),
    )

    process_event = ProcessEvent(
        event_id="event-1",
        process_instance_id="mortgage-1",
        process_name="mortgage-processing",
        event_type=ProcessEventType.COMPLETED,
        timestamp=NOW + timedelta(seconds=1),
        deployment_id="deployment-1",
        release_id="release-1",
        originating_run_id="run-1",
        duration_ms=1200,
    )

    service.record_process_event(
        expected_deployment_id="deployment-1",
        expected_release_id="release-1",
        expected_originating_run_id="run-1",
        event=process_event,
    )

    window = service.calculate_process_window(
        deployment_id="deployment-1",
        process_name="mortgage-processing",
        window_start=NOW,
        window_end=NOW + timedelta(minutes=5),
    )

    assert window.process_instances == 1

    assert window.completed_instances == 1

    assert window.completion_rate == 1.0
