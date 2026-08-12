from ai_engineering_evaluation.metrics import (
    CampaignMetricsCalculator,
)
from ai_engineering_evaluation.models import (
    CaseEvaluationResult,
    GateOutcome,
    OracleOutcome,
    QualificationPolicy,
    ReadinessStatus,
)
from ai_engineering_evaluation.readiness import (
    ReadinessEvaluator,
)
from ai_engineering_evaluation.statistics import (
    StatisticalAnalyzer,
)


def successful_case(index: int) -> CaseEvaluationResult:
    return CaseEvaluationResult(
        case_id=f"case-{index}",
        task_type="X1",
        difficulty="small",
        gate_outcome=GateOutcome.PASS,
        oracle_outcome=OracleOutcome.CORRECT,
    )


def policy(minimum_cases: int) -> QualificationPolicy:
    return QualificationPolicy(
        policy_version="test",
        minimum_gradable_cases=minimum_cases,
        minimum_task_success_lower_bound=0.80,
        minimum_safe_release_lower_bound=0.80,
        maximum_false_release_upper_bound=0.20,
        maximum_ungradable_fraction=0.05,
        maximum_pipeline_error_fraction=0.05,
    )


def test_small_sample_is_insufficient() -> None:
    results = tuple(
        successful_case(i)
        for i in range(10)
    )

    metrics = CampaignMetricsCalculator(
        StatisticalAnalyzer()
    ).calculate(
        results,
        confidence_level=0.95,
    )

    decision = ReadinessEvaluator().evaluate(
        metrics=metrics,
        policy=policy(minimum_cases=100),
    )

    assert decision.status == ReadinessStatus.INSUFFICIENT_EVIDENCE


def test_large_successful_campaign_can_qualify() -> None:
    results = tuple(
        successful_case(i)
        for i in range(500)
    )

    metrics = CampaignMetricsCalculator(
        StatisticalAnalyzer()
    ).calculate(
        results,
        confidence_level=0.95,
    )

    decision = ReadinessEvaluator().evaluate(
        metrics=metrics,
        policy=policy(minimum_cases=100),
    )

    assert decision.status == ReadinessStatus.QUALIFIED
