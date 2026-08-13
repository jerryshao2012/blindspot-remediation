from datetime import datetime, timedelta, timezone

from ai_engineering_economics.aggregation import (
    EngineeringEconomicsCalculator,
)
from ai_engineering_economics.models import (
    DeliveryOutcome,
    EconomicsPolicy,
    EconomicsSettings,
    GateDisposition,
    WorkItemEconomicsRecord,
    WorkItemStatus,
)
from ai_engineering_economics.policy import (
    ValueAssessmentService,
)
from ai_engineering_economics.service import (
    EngineeringEconomicsService,
)
from ai_engineering_economics.storage import (
    EngineeringEconomicsRepository,
)


NOW = datetime.now(timezone.utc)


class InMemoryRepository(EngineeringEconomicsRepository):
    def __init__(self, records):
        self.records = tuple(records)
        self.reports = []
        self.assessments = []

    def write_work_event(self, event):
        return None

    def write_human_effort(self, effort):
        return None

    def write_ai_usage(self, usage):
        return None

    def write_cost(self, cost):
        return None

    def normalized_records(self, *, window_start, window_end):
        return tuple(
            item
            for item in self.records
            if window_start <= item.created_at < window_end
        )

    def write_report(self, report):
        self.reports.append(report)

    def write_value_assessment(self, assessment):
        self.assessments.append(assessment)


def test_service_creates_and_stores_report() -> None:
    record = WorkItemEconomicsRecord(
        work_item_id="task-1",
        task_type="X1",
        team="poc",
        status=WorkItemStatus.DEPLOYED,
        gate_disposition=GateDisposition.PASS,
        delivery_outcome=DeliveryOutcome.SAFELY_DELIVERED,
        created_at=NOW,
        automation_started_at=NOW + timedelta(minutes=1),
        candidate_produced_at=NOW + timedelta(minutes=10),
        gate_completed_at=NOW + timedelta(minutes=15),
        deployed_at=NOW + timedelta(hours=1),
        human_effort_minutes=5.0,
        ai_input_tokens=1000,
        ai_output_tokens=100,
        ai_request_count=2,
        ai_cost=2.0,
        cloud_cost=1.0,
        human_cost=2.0,
        incident_cost=0.0,
        total_cost=5.0,
    )

    repository = InMemoryRepository([record])

    service = EngineeringEconomicsService(
        repository=repository,
        calculator=EngineeringEconomicsCalculator(),
        assessor=ValueAssessmentService(),
    )

    settings = EconomicsSettings(
        currency="CAD",
        policy=EconomicsPolicy(
            policy_version="test",
            minimum_work_items=1,
            minimum_safely_delivered_changes=1,
            minimum_cost_reduction_fraction=0.0,
            minimum_human_effort_reduction_fraction=0.0,
            maximum_change_failure_rate=0.10,
            maximum_human_review_rate=0.50,
        ),
    )

    report = service.create_report(
        window_start=NOW - timedelta(minutes=1),
        window_end=NOW + timedelta(days=1),
        settings=settings,
    )

    assert report.work_items == 1
    assert report.safely_delivered_changes == 1
    assert repository.reports == [report]
