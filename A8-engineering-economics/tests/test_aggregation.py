from datetime import datetime, timedelta, timezone

from ai_engineering_economics.aggregation import (
    EngineeringEconomicsCalculator,
)
from ai_engineering_economics.models import (
    DeliveryOutcome,
    GateDisposition,
    WorkItemEconomicsRecord,
    WorkItemStatus,
)


NOW = datetime.now(timezone.utc)


def record(
    identifier: str,
    *,
    safely_delivered: bool,
    human_review: bool,
    failed_change: bool = False,
) -> WorkItemEconomicsRecord:
    created = NOW

    delivery_outcome = (
        DeliveryOutcome.FAILED_CHANGE
        if failed_change
        else (
            DeliveryOutcome.SAFELY_DELIVERED
            if safely_delivered
            else DeliveryOutcome.NOT_DEPLOYED
        )
    )

    deployed_at = (
        created + timedelta(hours=2)
        if safely_delivered or failed_change
        else None
    )

    ai_cost = 5.0
    cloud_cost = 2.0
    human_cost = 10.0 if human_review else 2.0
    incident_cost = 30.0 if failed_change else 0.0

    return WorkItemEconomicsRecord(
        work_item_id=identifier,
        task_type="X1",
        team="poc",
        status=(
            WorkItemStatus.DEPLOYED
            if deployed_at is not None
            else WorkItemStatus.GATE_FAILED
        ),
        gate_disposition=(
            GateDisposition.HUMAN_REVIEW_REQUIRED
            if human_review
            else (
                GateDisposition.PASS
                if deployed_at is not None
                else GateDisposition.FAIL
            )
        ),
        delivery_outcome=delivery_outcome,
        created_at=created,
        automation_started_at=created + timedelta(minutes=5),
        candidate_produced_at=created + timedelta(minutes=20),
        gate_completed_at=created + timedelta(minutes=30),
        deployed_at=deployed_at,
        incident_resolved_at=(
            deployed_at + timedelta(hours=1)
            if failed_change and deployed_at is not None
            else None
        ),
        human_touch_count=1 if human_review else 0,
        human_effort_minutes=30.0 if human_review else 5.0,
        ai_input_tokens=1000,
        ai_output_tokens=200,
        ai_request_count=3,
        ai_cost=ai_cost,
        cloud_cost=cloud_cost,
        human_cost=human_cost,
        incident_cost=incident_cost,
        total_cost=(
            ai_cost
            + cloud_cost
            + human_cost
            + incident_cost
        ),
        human_review_required=human_review,
        rework_required=failed_change,
    )


def test_cost_per_safe_change_uses_safe_outcome_denominator() -> None:
    records = (
        record(
            "task-1",
            safely_delivered=True,
            human_review=False,
        ),
        record(
            "task-2",
            safely_delivered=True,
            human_review=True,
        ),
        record(
            "task-3",
            safely_delivered=False,
            human_review=False,
            failed_change=True,
        ),
    )

    report = EngineeringEconomicsCalculator().calculate(
        records=records,
        window_start=NOW - timedelta(minutes=1),
        window_end=NOW + timedelta(days=1),
        currency="CAD",
        confidence_level=0.95,
    )

    assert report.work_items == 3
    assert report.deployed_changes == 3
    assert report.safely_delivered_changes == 2
    assert report.failed_changes == 1

    assert report.cost_per_safely_delivered_change is not None
    assert report.cost_per_safely_delivered_change > 0

    assert report.change_failure_rate.estimate == 1 / 3
