"""
Deterministic value assessment.

The service does not ask an LLM whether the automation appears economically
valuable.

It compares explicit measurements with an explicit, versioned policy and a
comparable baseline.
"""

from __future__ import annotations

from .models import (
    BaselineMetrics,
    EconomicsPolicy,
    EngineeringEconomicsReport,
    ValueAssessment,
    ValueStatus,
)
from .statistics import relative_reduction


class ValueAssessmentService:
    """Evaluate engineering automation value against a supplied baseline."""

    def evaluate(
        self,
        *,
        report: EngineeringEconomicsReport,
        baseline: BaselineMetrics,
        policy: EconomicsPolicy,
    ) -> ValueAssessment:
        reasons: list[str] = []

        if report.work_items < policy.minimum_work_items:
            reasons.append(
                "Insufficient work items: "
                f"{report.work_items} < {policy.minimum_work_items}."
            )

        if (
            report.safely_delivered_changes
            < policy.minimum_safely_delivered_changes
        ):
            reasons.append(
                "Insufficient safely delivered changes: "
                f"{report.safely_delivered_changes} < "
                f"{policy.minimum_safely_delivered_changes}."
            )

        if report.cost_per_safely_delivered_change is None:
            reasons.append(
                "Cost per safely delivered change cannot be calculated."
            )

        if report.mean_human_minutes_per_safe_change is None:
            reasons.append(
                "Human effort per safely delivered change cannot be calculated."
            )

        if report.intake_to_deployment.mean_hours is None:
            reasons.append(
                "Mean intake-to-deployment lead time cannot be calculated."
            )

        if reasons:
            return ValueAssessment(
                status=ValueStatus.INSUFFICIENT_EVIDENCE,
                policy_version=policy.policy_version,
                cost_difference_per_safe_change=None,
                cost_reduction_fraction=None,
                lead_time_difference_hours=None,
                lead_time_reduction_fraction=None,
                human_effort_difference_minutes=None,
                human_effort_reduction_fraction=None,
                reasons=tuple(reasons),
            )

        current_cost = report.cost_per_safely_delivered_change
        current_human = report.mean_human_minutes_per_safe_change
        current_lead = report.intake_to_deployment.mean_hours

        assert current_cost is not None
        assert current_human is not None
        assert current_lead is not None

        cost_reduction = relative_reduction(
            baseline=baseline.cost_per_safely_delivered_change,
            treatment=current_cost,
        )

        human_reduction = relative_reduction(
            baseline=baseline.mean_human_minutes_per_safe_change,
            treatment=current_human,
        )

        lead_reduction = relative_reduction(
            baseline=baseline.mean_lead_time_hours,
            treatment=current_lead,
        )

        cost_difference = (
            current_cost
            - baseline.cost_per_safely_delivered_change
        )

        human_difference = (
            current_human
            - baseline.mean_human_minutes_per_safe_change
        )

        lead_difference = (
            current_lead
            - baseline.mean_lead_time_hours
        )

        failures: list[str] = []

        if (
            cost_reduction is None
            or cost_reduction
            < policy.minimum_cost_reduction_fraction
        ):
            failures.append(
                "Required cost reduction was not demonstrated."
            )

        if (
            human_reduction is None
            or human_reduction
            < policy.minimum_human_effort_reduction_fraction
        ):
            failures.append(
                "Required human-effort reduction was not demonstrated."
            )

        change_failure = report.change_failure_rate.estimate

        if change_failure is None:
            failures.append(
                "Change-failure rate is unavailable."
            )
        elif change_failure > policy.maximum_change_failure_rate:
            failures.append(
                "Observed change-failure rate "
                f"{change_failure:.4f} exceeds permitted "
                f"{policy.maximum_change_failure_rate:.4f}."
            )

        review_rate = report.human_review_rate.estimate

        if review_rate is None:
            failures.append(
                "Human-review rate is unavailable."
            )
        elif review_rate > policy.maximum_human_review_rate:
            failures.append(
                "Observed human-review rate "
                f"{review_rate:.4f} exceeds permitted "
                f"{policy.maximum_human_review_rate:.4f}."
            )

        if failures:
            return ValueAssessment(
                status=ValueStatus.VALUE_NOT_DEMONSTRATED,
                policy_version=policy.policy_version,
                cost_difference_per_safe_change=cost_difference,
                cost_reduction_fraction=cost_reduction,
                lead_time_difference_hours=lead_difference,
                lead_time_reduction_fraction=lead_reduction,
                human_effort_difference_minutes=human_difference,
                human_effort_reduction_fraction=human_reduction,
                reasons=tuple(failures),
            )

        return ValueAssessment(
            status=ValueStatus.VALUE_DEMONSTRATED,
            policy_version=policy.policy_version,
            cost_difference_per_safe_change=cost_difference,
            cost_reduction_fraction=cost_reduction,
            lead_time_difference_hours=lead_difference,
            lead_time_reduction_fraction=lead_reduction,
            human_effort_difference_minutes=human_difference,
            human_effort_reduction_fraction=human_reduction,
            reasons=(
                "The configured minimum cost and human-effort reductions "
                "were demonstrated without violating the configured "
                "change-failure or human-review limits.",
            ),
        )
