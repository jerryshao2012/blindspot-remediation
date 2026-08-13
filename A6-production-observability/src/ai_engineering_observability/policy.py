"""
Deterministic SLO evaluation.

This component does NOT ask:

    "Does an LLM think production looks healthy?"

Operational thresholds should be explicit, inspectable, versioned, and
reproducible.

AI may later assist humans in diagnosing a degradation.

AI should not be the authoritative mechanism deciding whether a numerical SLO
was violated.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    OperationalHealth,
    OperationalHealthDecision,
    OperationalPolicy,
    OperationalWindow,
)


class SLOEvaluator:
    """Evaluate operational observations against explicit policy."""

    def evaluate(
        self,
        *,
        window: OperationalWindow,
        policy: OperationalPolicy,
    ) -> OperationalHealthDecision:
        now = datetime.now(timezone.utc)

        if window.observation_count < policy.minimum_observations:
            return OperationalHealthDecision(
                deployment_id=window.deployment_id,
                status=OperationalHealth.INSUFFICIENT_DATA,
                policy_version=policy.policy_version,
                reasons=(
                    "Insufficient observations: "
                    f"{window.observation_count} < "
                    f"{policy.minimum_observations}.",
                ),
                evaluated_at=now,
            )

        critical: list[str] = []
        degraded: list[str] = []

        if window.error_rate is not None:
            if window.error_rate >= policy.critical_error_rate:
                critical.append(
                    "Error rate "
                    f"{window.error_rate:.4f} reached critical threshold "
                    f"{policy.critical_error_rate:.4f}."
                )
            elif window.error_rate > policy.maximum_error_rate:
                degraded.append(
                    "Error rate "
                    f"{window.error_rate:.4f} exceeded SLO "
                    f"{policy.maximum_error_rate:.4f}."
                )

        if window.p95_latency_ms is not None:
            if (
                window.p95_latency_ms
                >= policy.critical_p95_latency_ms
            ):
                critical.append(
                    "P95 latency "
                    f"{window.p95_latency_ms:.2f} ms reached critical "
                    f"threshold {policy.critical_p95_latency_ms:.2f} ms."
                )
            elif (
                window.p95_latency_ms
                > policy.maximum_p95_latency_ms
            ):
                degraded.append(
                    "P95 latency "
                    f"{window.p95_latency_ms:.2f} ms exceeded SLO "
                    f"{policy.maximum_p95_latency_ms:.2f} ms."
                )

        if (
            window.availability is not None
            and window.availability < policy.minimum_availability
        ):
            degraded.append(
                "Availability "
                f"{window.availability:.4f} fell below SLO "
                f"{policy.minimum_availability:.4f}."
            )

        if (
            window.timeout_rate is not None
            and window.timeout_rate > policy.maximum_timeout_rate
        ):
            degraded.append(
                "Timeout rate "
                f"{window.timeout_rate:.4f} exceeded SLO "
                f"{policy.maximum_timeout_rate:.4f}."
            )

        if (
            window.dependency_failure_rate is not None
            and window.dependency_failure_rate
            > policy.maximum_dependency_failure_rate
        ):
            degraded.append(
                "Dependency failure rate "
                f"{window.dependency_failure_rate:.4f} exceeded SLO "
                f"{policy.maximum_dependency_failure_rate:.4f}."
            )

        if critical:
            return OperationalHealthDecision(
                deployment_id=window.deployment_id,
                status=OperationalHealth.CRITICAL,
                policy_version=policy.policy_version,
                reasons=tuple(critical + degraded),
                evaluated_at=now,
            )

        if degraded:
            return OperationalHealthDecision(
                deployment_id=window.deployment_id,
                status=OperationalHealth.DEGRADED,
                policy_version=policy.policy_version,
                reasons=tuple(degraded),
                evaluated_at=now,
            )

        return OperationalHealthDecision(
            deployment_id=window.deployment_id,
            status=OperationalHealth.HEALTHY,
            policy_version=policy.policy_version,
            reasons=(
                "All configured operational SLO conditions were satisfied.",
            ),
            evaluated_at=now,
        )
