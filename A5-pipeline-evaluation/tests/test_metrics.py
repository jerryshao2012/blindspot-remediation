from ai_engineering_evaluation.metrics import (
    CampaignMetricsCalculator,
)
from ai_engineering_evaluation.models import (
    CaseEvaluationResult,
    GateOutcome,
    OracleOutcome,
)
from ai_engineering_evaluation.statistics import (
    StatisticalAnalyzer,
)


def case(
    case_id: str,
    gate: GateOutcome,
    oracle: OracleOutcome,
) -> CaseEvaluationResult:
    return CaseEvaluationResult(
        case_id=case_id,
        task_type="X1",
        difficulty="small",
        gate_outcome=gate,
        oracle_outcome=oracle,
    )


def test_false_release_is_detected() -> None:
    results = (
        case(
            "1",
            GateOutcome.PASS,
            OracleOutcome.CORRECT,
        ),
        case(
            "2",
            GateOutcome.PASS,
            OracleOutcome.INCORRECT,
        ),
        case(
            "3",
            GateOutcome.FAIL,
            OracleOutcome.INCORRECT,
        ),
    )

    calculator = CampaignMetricsCalculator(
        StatisticalAnalyzer()
    )

    metrics = calculator.calculate(
        results,
        confidence_level=0.95,
    )

    assert metrics.gradable_cases == 3
    assert metrics.correct_cases == 1
    assert metrics.incorrect_cases == 2

    assert metrics.false_releases == 1

    assert metrics.released_cases == 2

    assert metrics.false_release_rate.estimate == 0.5


def test_false_rejection_is_detected() -> None:
    results = (
        case(
            "1",
            GateOutcome.FAIL,
            OracleOutcome.CORRECT,
        ),
        case(
            "2",
            GateOutcome.PASS,
            OracleOutcome.CORRECT,
        ),
    )

    metrics = CampaignMetricsCalculator(
        StatisticalAnalyzer()
    ).calculate(
        results,
        confidence_level=0.95,
    )

    assert metrics.false_rejections == 1
    assert metrics.false_rejection_rate.estimate == 0.5
