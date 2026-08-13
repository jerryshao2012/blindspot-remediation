"""
Engineering-flow and unit-economics aggregation.

The calculator operates on normalized WorkItemEconomicsRecord values.

Source-specific parsing belongs in adapters. The authoritative calculations
remain independent from Jira, Azure DevOps, Azure Cost Management, or any model
provider.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from .errors import EconomicsAggregationError
from .models import (
    DeliveryOutcome,
    EngineeringEconomicsReport,
    GateDisposition,
    WorkItemEconomicsRecord,
    WorkItemStatus,
)
from .statistics import (
    duration_distribution,
    proportion_metric,
    safe_divide,
)


def elapsed_hours(
    start: datetime | None,
    end: datetime | None,
) -> float | None:
    if start is None or end is None:
        return None

    if end < start:
        raise EconomicsAggregationError(
            "Milestone end precedes start."
        )

    return (end - start).total_seconds() / 3600.0


class EngineeringEconomicsCalculator:
    """Calculate one engineering-productivity and unit-economics report."""

    def calculate(
        self,
        *,
        records: tuple[WorkItemEconomicsRecord, ...],
        window_start: datetime,
        window_end: datetime,
        currency: str,
        confidence_level: float,
        report_id: str | None = None,
    ) -> EngineeringEconomicsReport:
        if window_end <= window_start:
            raise EconomicsAggregationError(
                "window_end must be after window_start."
            )

        selected = tuple(
            record
            for record in records
            if window_start <= record.created_at < window_end
        )

        currencies = {currency}

        if len(currencies) != 1:
            raise EconomicsAggregationError(
                "A report must use one normalized currency."
            )

        total = len(selected)

        deployed = [
            item
            for item in selected
            if item.deployed_at is not None
        ]

        safely_delivered = [
            item
            for item in selected
            if (
                item.delivery_outcome
                == DeliveryOutcome.SAFELY_DELIVERED
            )
        ]

        failed_changes = [
            item
            for item in selected
            if (
                item.delivery_outcome
                == DeliveryOutcome.FAILED_CHANGE
            )
        ]

        human_review = [
            item
            for item in selected
            if (
                item.human_review_required
                or item.gate_disposition
                == GateDisposition.HUMAN_REVIEW_REQUIRED
            )
        ]

        autonomous = [
            item
            for item in safely_delivered
            if not item.human_review_required
        ]

        reworked = [
            item
            for item in selected
            if item.rework_required
        ]

        pipeline_errors = [
            item
            for item in selected
            if item.status == WorkItemStatus.PIPELINE_ERROR
        ]

        automation_completed = [
            item
            for item in selected
            if item.candidate_produced_at is not None
        ]

        lead_times = [
            value
            for item in deployed
            if (
                value := elapsed_hours(
                    item.created_at,
                    item.deployed_at,
                )
            )
            is not None
        ]

        automation_cycle_times = [
            value
            for item in selected
            if (
                value := elapsed_hours(
                    item.automation_started_at,
                    item.candidate_produced_at,
                )
            )
            is not None
        ]

        gate_cycle_times = [
            value
            for item in selected
            if (
                value := elapsed_hours(
                    item.candidate_produced_at,
                    item.gate_completed_at,
                )
            )
            is not None
        ]

        recovery_times = [
            value
            for item in failed_changes
            if (
                value := elapsed_hours(
                    item.deployed_at,
                    item.incident_resolved_at,
                )
            )
            is not None
        ]

        observation_days = (
            window_end - window_start
        ).total_seconds() / 86_400.0

        deployment_frequency = safe_divide(
            len(deployed),
            observation_days,
        )

        total_human_minutes = sum(
            item.human_effort_minutes
            for item in selected
        )

        total_human_hours = total_human_minutes / 60.0

        total_input_tokens = sum(
            item.ai_input_tokens
            for item in selected
        )

        total_output_tokens = sum(
            item.ai_output_tokens
            for item in selected
        )

        total_ai_requests = sum(
            item.ai_request_count
            for item in selected
        )

        total_ai_cost = sum(
            item.ai_cost
            for item in selected
        )

        total_cloud_cost = sum(
            item.cloud_cost
            for item in selected
        )

        total_human_cost = sum(
            item.human_cost
            for item in selected
        )

        total_incident_cost = sum(
            item.incident_cost
            for item in selected
        )

        total_cost = sum(
            item.total_cost
            for item in selected
        )

        safe_count = len(safely_delivered)

        return EngineeringEconomicsReport(
            report_id=report_id or f"economics-{uuid4()}",
            window_start=window_start,
            window_end=window_end,
            currency=currency,
            work_items=total,
            deployed_changes=len(deployed),
            safely_delivered_changes=safe_count,
            failed_changes=len(failed_changes),
            autonomous_changes=len(autonomous),
            human_review_changes=len(human_review),
            reworked_changes=len(reworked),
            pipeline_error_items=len(pipeline_errors),
            automation_completion_rate=proportion_metric(
                numerator=len(automation_completed),
                denominator=total,
                confidence_level=confidence_level,
            ),
            autonomous_delivery_rate=proportion_metric(
                numerator=len(autonomous),
                denominator=total,
                confidence_level=confidence_level,
            ),
            human_review_rate=proportion_metric(
                numerator=len(human_review),
                denominator=total,
                confidence_level=confidence_level,
            ),
            rework_rate=proportion_metric(
                numerator=len(reworked),
                denominator=len(deployed),
                confidence_level=confidence_level,
            ),
            change_failure_rate=proportion_metric(
                numerator=len(failed_changes),
                denominator=len(deployed),
                confidence_level=confidence_level,
            ),
            intake_to_deployment=duration_distribution(
                lead_times
            ),
            automation_cycle_time=duration_distribution(
                automation_cycle_times
            ),
            gate_cycle_time=duration_distribution(
                gate_cycle_times
            ),
            failed_deployment_recovery_time=(
                duration_distribution(recovery_times)
            ),
            deployment_frequency_per_day=deployment_frequency,
            total_human_hours=total_human_hours,
            mean_human_minutes_per_item=safe_divide(
                total_human_minutes,
                total,
            ),
            mean_human_minutes_per_safe_change=safe_divide(
                total_human_minutes,
                safe_count,
            ),
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_ai_requests=total_ai_requests,
            total_ai_cost=total_ai_cost,
            total_cloud_cost=total_cloud_cost,
            total_human_cost=total_human_cost,
            total_incident_cost=total_incident_cost,
            total_cost=total_cost,
            cost_per_attempted_item=safe_divide(
                total_cost,
                total,
            ),
            cost_per_deployed_change=safe_divide(
                total_cost,
                len(deployed),
            ),
            cost_per_safely_delivered_change=safe_divide(
                total_cost,
                safe_count,
            ),
            tokens_per_safely_delivered_change=safe_divide(
                total_input_tokens + total_output_tokens,
                safe_count,
            ),
        )
