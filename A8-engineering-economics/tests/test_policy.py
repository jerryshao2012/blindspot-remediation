from datetime import datetime, timedelta, timezone

from ai_engineering_economics.aggregation import (
    EngineeringEconomicsCalculator,
)
from ai_engineering_economics.models import (
    BaselineMetrics,
    DeliveryOutcome,
    EconomicsPolicy,
    GateDisposition,
    ValueStatus,
    WorkItemEconomicsRecord,
    WorkItemStatus,
)
from ai_engineering_economics.policy import (
    ValueAssessmentService,
)


NOW = datetime.now(timezone.utc)


def automated_record(index: int) -> WorkItemEconomicsRecord:
    return WorkItemEconomicsRecord(
        work_item_id=f"task-{index}",
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
        human_touch_count=0,
        human_effort_minutes=10.0,
        ai_input_tokens=1000,
        ai_output_tokens=200,
        ai_request_count=3,
        ai_cost=5.0,
        cloud_cost=5.0,
        human_cost=10.0,
        incident_cost=0.0,
        total_cost=20.0,
    )


def test_value_can_be_demonstrated_against_comparable_baseline() -> None:
    records = tuple(
        automated_record(index)
        for index in range(100)
    )

    report = EngineeringEconomicsCalculator().calculate(
        records=records,
        window_start=NOW - timedelta(minutes=1),
        window_end=NOW + timedelta(days=1),
        currency="CAD",
        confidence_level=0.95,
    )

    baseline = BaselineMetrics(
        baseline_id="human-baseline",
        metric_version="1.0",
        task_type="X1",
        sample_size=100,
        cost_per_safely_delivered_change=100.0,
        mean_lead_time_hours=8.0,
        mean_human_minutes_per_safe_change=60.0,
        change_failure_rate=0.05,
    )

    policy = EconomicsPolicy(
        policy_version="test",
        minimum_work_items=50,
        minimum_safely_delivered_changes=50,
        minimum_cost_reduction_fraction=0.15,
        minimum_human_effort_reduction_fraction=0.25,
        maximum_change_failure_rate=0.10,
        maximum_human_review_rate=0.40,
    )

    assessment = ValueAssessmentService().evaluate(
        report=report,
        baseline=baseline,
        policy=policy,
    )

    assert assessment.status == ValueStatus.VALUE_DEMONSTRATED
