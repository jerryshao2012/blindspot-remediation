from __future__ import annotations

from datetime import datetime, timezone

from ai_engineering_contracts import (
    CheckStatus,
    ControlResult,
    ControlSeverity,
    EvidenceStrategy,
    GateDecision,
)

from ai_engineering_release_gate.models import (
    ComparisonOperator,
    MetricThreshold,
    MissingMetricAction,
    ReleasePolicy,
)
from ai_engineering_release_gate.policy import GatePolicyEngine

NOW = datetime(2026, 8, 6, 18, 0, tzinfo=timezone.utc)


def control(
    *,
    control_id: str,
    status: CheckStatus,
    severity: ControlSeverity,
) -> ControlResult:
    return ControlResult(
        control_id=control_id,
        name=control_id,
        status=status,
        severity=severity,
        strategy=EvidenceStrategy.COMPILATION,
        deterministic_authority=True,
        summary="Test control.",
        started_at=NOW,
        completed_at=NOW,
        exit_code=None if False else None,
    )


def policy(
    thresholds: list[MetricThreshold] | None = None,
) -> ReleasePolicy:
    return ReleasePolicy(
        version="1.0.0",
        task_type="X1-test",
        metric_thresholds=thresholds or [],
    )


def test_mandatory_failure_produces_fail() -> None:
    result = GatePolicyEngine().decide(
        controls=[
            control(
                control_id="compile",
                status=CheckStatus.FAILED,
                severity=ControlSeverity.MANDATORY,
            )
        ],
        metrics={},
        policy=policy(),
    )
    assert result.decision == GateDecision.FAIL


def test_advisory_failure_produces_human_review() -> None:
    result = GatePolicyEngine().decide(
        controls=[
            control(
                control_id="coverage",
                status=CheckStatus.FAILED,
                severity=ControlSeverity.ADVISORY,
            )
        ],
        metrics={},
        policy=policy(),
    )
    assert result.decision == GateDecision.HUMAN_REVIEW_REQUIRED


def test_missing_required_metric_produces_more_evidence() -> None:
    threshold = MetricThreshold(
        threshold_id="coverage-required",
        metric="coverage.coverage_percent",
        operator=ComparisonOperator.GREATER_THAN_OR_EQUAL,
        expected_value=80,
        failure_decision=GateDecision.HUMAN_REVIEW_REQUIRED,
        missing_metric_action=MissingMetricAction.MORE_EVIDENCE_REQUIRED,
        description="Coverage must be measured.",
    )
    result = GatePolicyEngine().decide(
        controls=[],
        metrics={},
        policy=policy([threshold]),
    )
    assert result.decision == GateDecision.MORE_EVIDENCE_REQUIRED
    assert result.unmet_obligations


def test_passing_controls_and_metrics_produce_pass() -> None:
    threshold = MetricThreshold(
        threshold_id="coverage-required",
        metric="coverage.coverage_percent",
        operator=ComparisonOperator.GREATER_THAN_OR_EQUAL,
        expected_value=80,
        failure_decision=GateDecision.HUMAN_REVIEW_REQUIRED,
        missing_metric_action=MissingMetricAction.MORE_EVIDENCE_REQUIRED,
        description="Coverage must be at least 80 percent.",
    )
    result = GatePolicyEngine().decide(
        controls=[
            control(
                control_id="compile",
                status=CheckStatus.PASSED,
                severity=ControlSeverity.MANDATORY,
            )
        ],
        metrics={"coverage.coverage_percent": 95.0},
        policy=policy([threshold]),
    )
    assert result.decision == GateDecision.PASS
