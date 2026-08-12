"""
Deterministic platform-readiness policy.

This is intentionally separate from statistical measurement.

The StatisticalAnalyzer says:

    "Here is what we observed and the uncertainty around it."

The ReadinessEvaluator says:

    "Given those measurements, does the platform satisfy our qualification
     policy?"

Those are different responsibilities.
"""

from __future__ import annotations

from .errors import ReadinessPolicyError
from .models import (
    CampaignMetrics,
    QualificationPolicy,
    ReadinessDecision,
    ReadinessStatus,
)


class ReadinessEvaluator:
    """Apply explicit deterministic qualification policy."""

    def evaluate(
        self,
        *,
        metrics: CampaignMetrics,
        policy: QualificationPolicy,
    ) -> ReadinessDecision:
        reasons: list[str] = []

        if metrics.gradable_cases < policy.minimum_gradable_cases:
            reasons.append(
                "Insufficient gradable benchmark cases: "
                f"{metrics.gradable_cases} < "
                f"{policy.minimum_gradable_cases}."
            )

            return ReadinessDecision(
                status=ReadinessStatus.INSUFFICIENT_EVIDENCE,
                reasons=tuple(reasons),
                policy_version=policy.policy_version,
            )

        required_estimates = {
            "task_success": metrics.task_success,
            "safe_release": metrics.safe_release,
            "false_release_rate": metrics.false_release_rate,
        }

        for name, estimate in required_estimates.items():
            if (
                estimate.lower_bound is None
                or estimate.upper_bound is None
            ):
                reasons.append(
                    f"{name} has insufficient observations."
                )

        if reasons:
            return ReadinessDecision(
                status=ReadinessStatus.INSUFFICIENT_EVIDENCE,
                reasons=tuple(reasons),
                policy_version=policy.policy_version,
            )

        task_lower = metrics.task_success.lower_bound
        safe_lower = metrics.safe_release.lower_bound
        false_release_upper = metrics.false_release_rate.upper_bound

        if task_lower is None or safe_lower is None or false_release_upper is None:
            raise ReadinessPolicyError(
                "Required confidence interval unexpectedly absent."
            )

        if task_lower < policy.minimum_task_success_lower_bound:
            reasons.append(
                "Task-success confidence lower bound "
                f"{task_lower:.4f} is below required "
                f"{policy.minimum_task_success_lower_bound:.4f}."
            )

        if safe_lower < policy.minimum_safe_release_lower_bound:
            reasons.append(
                "Safe-release confidence lower bound "
                f"{safe_lower:.4f} is below required "
                f"{policy.minimum_safe_release_lower_bound:.4f}."
            )

        if (
            false_release_upper
            > policy.maximum_false_release_upper_bound
        ):
            reasons.append(
                "False-release confidence upper bound "
                f"{false_release_upper:.4f} exceeds permitted "
                f"{policy.maximum_false_release_upper_bound:.4f}."
            )

        total = metrics.total_cases

        if total == 0:
            return ReadinessDecision(
                status=ReadinessStatus.INSUFFICIENT_EVIDENCE,
                reasons=("Campaign contains zero benchmark cases.",),
                policy_version=policy.policy_version,
            )

        ungradable_fraction = metrics.ungradable_cases / total
        pipeline_error_fraction = metrics.pipeline_errors / total

        if (
            ungradable_fraction
            > policy.maximum_ungradable_fraction
        ):
            reasons.append(
                "Ungradable fraction "
                f"{ungradable_fraction:.4f} exceeds permitted "
                f"{policy.maximum_ungradable_fraction:.4f}."
            )

        if (
            pipeline_error_fraction
            > policy.maximum_pipeline_error_fraction
        ):
            reasons.append(
                "Pipeline-error fraction "
                f"{pipeline_error_fraction:.4f} exceeds permitted "
                f"{policy.maximum_pipeline_error_fraction:.4f}."
            )

        if reasons:
            return ReadinessDecision(
                status=ReadinessStatus.NOT_QUALIFIED,
                reasons=tuple(reasons),
                policy_version=policy.policy_version,
            )

        return ReadinessDecision(
            status=ReadinessStatus.QUALIFIED,
            reasons=(
                "All configured statistical and operational "
                "qualification requirements were satisfied.",
            ),
            policy_version=policy.policy_version,
        )
