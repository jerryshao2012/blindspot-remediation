"""
Deterministic release-policy evaluation.

No LLM participates in the final decision.

Decision precedence
-------------------
1. FAIL
2. HUMAN_REVIEW_REQUIRED
3. MORE_EVIDENCE_REQUIRED
4. PASS

A lower-priority condition cannot mask a higher-priority condition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ai_engineering_contracts import (
    CheckStatus,
    ControlResult,
    ControlSeverity,
    GateDecision,
)

from .errors import PolicyEvaluationError
from .models import (
    ComparisonOperator,
    MissingMetricAction,
    ReleasePolicy,
)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Internal deterministic policy output."""

    decision: GateDecision
    reasons: tuple[str, ...]
    unmet_obligations: tuple[str, ...]
    contradictions: tuple[str, ...]


class GatePolicyEngine:
    """Convert normalized authoritative evidence into a gate recommendation."""

    _PRECEDENCE = {
        GateDecision.PASS: 0,
        GateDecision.MORE_EVIDENCE_REQUIRED: 1,
        GateDecision.HUMAN_REVIEW_REQUIRED: 2,
        GateDecision.FAIL: 3,
    }

    def decide(
        self,
        *,
        controls: list[ControlResult],
        metrics: dict[str, float],
        policy: ReleasePolicy,
    ) -> PolicyDecision:
        candidate_decisions: list[tuple[GateDecision, str]] = []
        unmet_obligations: list[str] = []
        contradictions: list[str] = []
        for control in controls:
            failed = control.status in {
                CheckStatus.FAILED,
                CheckStatus.ERROR,
            }
            incomplete = control.status in {
                CheckStatus.SKIPPED,
                CheckStatus.NOT_APPLICABLE,
            }
            if (
                failed
                and control.severity == ControlSeverity.DOMINANT_FAILURE
                and policy.fail_on_dominant_failure
            ):
                candidate_decisions.append(
                    (
                        GateDecision.FAIL,
                        f"Dominant control {control.control_id!r} failed.",
                    )
                )
                continue
            if (
                failed
                and control.severity == ControlSeverity.MANDATORY
                and policy.fail_on_mandatory_control_failure
            ):
                candidate_decisions.append(
                    (
                        GateDecision.FAIL,
                        f"Mandatory control {control.control_id!r} failed.",
                    )
                )
                continue
            if (
                failed
                and control.severity == ControlSeverity.ADVISORY
                and policy.human_review_on_advisory_failure
            ):
                candidate_decisions.append(
                    (
                        GateDecision.HUMAN_REVIEW_REQUIRED,
                        f"Advisory control {control.control_id!r} failed.",
                    )
                )
            if (
                control.status == CheckStatus.WARNING
                and policy.human_review_on_warning
            ):
                candidate_decisions.append(
                    (
                        GateDecision.HUMAN_REVIEW_REQUIRED,
                        f"Control {control.control_id!r} produced a warning.",
                    )
                )
            if (
                incomplete
                and control.severity
                in {
                    ControlSeverity.MANDATORY,
                    ControlSeverity.DOMINANT_FAILURE,
                }
                and policy.more_evidence_on_skipped_mandatory_control
            ):
                message = (
                    f"Required control {control.control_id!r} did not produce "
                    "a conclusive result."
                )
                candidate_decisions.append(
                    (GateDecision.MORE_EVIDENCE_REQUIRED, message)
                )
                unmet_obligations.append(message)
            if control.status == CheckStatus.ERROR and control.reasons:
                contradictions.extend(
                    f"{control.control_id}: {reason}"
                    for reason in control.reasons
                    if "contradict" in reason.casefold()
                )
        for threshold in policy.metric_thresholds:
            actual = metrics.get(threshold.metric)
            if actual is None:
                decision = _missing_action_to_decision(
                    threshold.missing_metric_action
                )
                message = (
                    f"Metric {threshold.metric!r} required by threshold "
                    f"{threshold.threshold_id!r} is unavailable."
                )
                candidate_decisions.append((decision, message))
                unmet_obligations.append(message)
                continue
            if not math.isfinite(actual):
                raise PolicyEvaluationError(
                    f"Metric {threshold.metric!r} is not finite."
                )
            passed = _compare(
                actual=actual,
                operator=threshold.operator,
                expected=threshold.expected_value,
            )
            if not passed:
                message = (
                    f"Threshold {threshold.threshold_id!r} failed: "
                    f"{threshold.metric}={actual} does not satisfy "
                    f"{threshold.operator.value} "
                    f"{threshold.expected_value}. "
                    f"{threshold.description}"
                )
                candidate_decisions.append(
                    (threshold.failure_decision, message)
                )
                if (
                    threshold.failure_decision
                    == GateDecision.MORE_EVIDENCE_REQUIRED
                ):
                    unmet_obligations.append(message)
        if not candidate_decisions:
            return PolicyDecision(
                decision=GateDecision.PASS,
                reasons=(
                    "All configured deterministic controls and metric "
                    "thresholds passed.",
                ),
                unmet_obligations=(),
                contradictions=(),
            )
        final_decision = max(
            (item[0] for item in candidate_decisions),
            key=lambda decision: self._PRECEDENCE[decision],
        )
        relevant_reasons = tuple(
            reason
            for decision, reason in candidate_decisions
            if self._PRECEDENCE[decision]
            == self._PRECEDENCE[final_decision]
        )
        # GateResult does not permit unmet obligations or contradictions on PASS.
        # For FAIL or HUMAN_REVIEW, they remain useful explanatory evidence.
        return PolicyDecision(
            decision=final_decision,
            reasons=relevant_reasons,
            unmet_obligations=tuple(dict.fromkeys(unmet_obligations)),
            contradictions=tuple(dict.fromkeys(contradictions)),
        )


def _compare(
    *,
    actual: float,
    operator: ComparisonOperator,
    expected: float,
) -> bool:
    if operator == ComparisonOperator.GREATER_THAN:
        return actual > expected
    if operator == ComparisonOperator.GREATER_THAN_OR_EQUAL:
        return actual >= expected
    if operator == ComparisonOperator.LESS_THAN:
        return actual < expected
    if operator == ComparisonOperator.LESS_THAN_OR_EQUAL:
        return actual <= expected
    if operator == ComparisonOperator.EQUAL:
        return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    if operator == ComparisonOperator.NOT_EQUAL:
        return not math.isclose(
            actual,
            expected,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
    raise PolicyEvaluationError(
        f"Unsupported comparison operator {operator!r}."
    )


def _missing_action_to_decision(
    action: MissingMetricAction,
) -> GateDecision:
    if action == MissingMetricAction.FAIL:
        return GateDecision.FAIL
    if action == MissingMetricAction.HUMAN_REVIEW_REQUIRED:
        return GateDecision.HUMAN_REVIEW_REQUIRED
    if action == MissingMetricAction.MORE_EVIDENCE_REQUIRED:
        return GateDecision.MORE_EVIDENCE_REQUIRED
    raise PolicyEvaluationError(
        f"Unsupported missing-metric action {action!r}."
    )
