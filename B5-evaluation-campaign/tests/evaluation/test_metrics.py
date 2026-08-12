"""
Tests for deterministic classification and metric semantics.
"""

from l1_automation.evaluation.campaign_runner import (
    classify_gate_against_oracle,
)

from l1_automation.evaluation.contracts import (
    DecisionClassification,
    GateOutcome,
    OracleAcceptability,
)


def test_pass_unacceptable_is_false_release() -> None:

    result = classify_gate_against_oracle(
        gate_outcome=GateOutcome.PASS,
        oracle_acceptability=(
            OracleAcceptability.UNACCEPTABLE
        ),
    )

    assert result == (
        DecisionClassification.FALSE_RELEASE
    )


def test_fail_acceptable_is_false_rejection() -> None:

    result = classify_gate_against_oracle(
        gate_outcome=GateOutcome.FAIL,
        oracle_acceptability=(
            OracleAcceptability.ACCEPTABLE
        ),
    )

    assert result == (
        DecisionClassification.FALSE_REJECTION
    )


def test_review_remains_review() -> None:
    """
    Review/abstention must not be hidden inside aggregate accuracy.
    """

    result = classify_gate_against_oracle(
        gate_outcome=(
            GateOutcome.HUMAN_REVIEW_REQUIRED
        ),
        oracle_acceptability=(
            OracleAcceptability.ACCEPTABLE
        ),
    )

    assert result == (
        DecisionClassification.REVIEW_REQUIRED
    )


def test_oracle_error_is_not_candidate_failure() -> None:

    result = classify_gate_against_oracle(
        gate_outcome=GateOutcome.PASS,
        oracle_acceptability=(
            OracleAcceptability.ORACLE_ERROR
        ),
    )

    assert result == (
        DecisionClassification.ORACLE_ERROR
    )

