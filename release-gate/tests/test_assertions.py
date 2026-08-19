from __future__ import annotations

import math

import pytest

from release_gate.assertions import (
    AssertionState,
    evaluate_assertion,
    resolve_pointer,
)
from release_gate.models import Assertion, AssertionOperator, Comparison


def assertion(
    *,
    metric: str = "/value",
    comparison: Comparison = Comparison.CANDIDATE,
    operator: AssertionOperator = AssertionOperator.EQ,
    value: object = 3,
) -> Assertion:
    return Assertion.model_validate(
        {
            "report": "metrics",
            "metric": metric,
            "comparison": comparison,
            "operator": operator,
            "value": value,
        }
    )


@pytest.mark.parametrize(
    ("pointer", "expected"),
    [
        ("", {"": {"a/b": {"~key": 4}}}),
        ("/", {"a/b": {"~key": 4}}),
        ("//a~1b/~0key", 4),
    ],
)
def test_resolves_rfc6901_pointer(pointer: str, expected: object) -> None:
    document = {"": {"a/b": {"~key": 4}}}
    assert resolve_pointer(document, pointer) == expected


@pytest.mark.parametrize("pointer", ["value", "/bad~2escape", "/dangling~"])
def test_rejects_invalid_or_missing_pointer(pointer: str) -> None:
    with pytest.raises(ValueError):
        resolve_pointer({"value": 1}, pointer)


@pytest.mark.parametrize(
    ("operator", "expected", "state"),
    [
        (AssertionOperator.EQ, 3, AssertionState.PASS),
        (AssertionOperator.NE, 4, AssertionState.PASS),
        (AssertionOperator.GT, 2, AssertionState.PASS),
        (AssertionOperator.GTE, 3, AssertionState.PASS),
        (AssertionOperator.LT, 4, AssertionState.PASS),
        (AssertionOperator.LTE, 3, AssertionState.PASS),
        (AssertionOperator.GT, 4, AssertionState.FAIL),
    ],
)
def test_all_assertion_operators(
    operator: AssertionOperator, expected: int, state: AssertionState
) -> None:
    outcome = evaluate_assertion(
        assertion(operator=operator, value=expected),
        candidate={"metrics": {"value": 3}},
        baseline=None,
    )
    assert outcome.state is state
    assert outcome.reason_codes == (
        () if state is AssertionState.PASS else ("ASSERTION_FAILED",)
    )


def test_candidate_baseline_and_delta_comparisons() -> None:
    candidate = {"metrics": {"value": 5}}
    baseline = {"metrics": {"value": 3}}

    absolute = evaluate_assertion(
        assertion(comparison=Comparison.BASELINE, value=3),
        candidate=candidate,
        baseline=baseline,
    )
    delta = evaluate_assertion(
        assertion(comparison=Comparison.CANDIDATE_MINUS_BASELINE, value=2),
        candidate=candidate,
        baseline=baseline,
    )

    assert absolute.actual == 3
    assert absolute.state is AssertionState.PASS
    assert delta.actual == 2
    assert delta.state is AssertionState.PASS


@pytest.mark.parametrize(
    ("candidate", "baseline"),
    [
        ({}, None),
        ({"metrics": {}}, None),
        ({"metrics": {"value": "text"}}, {"metrics": {"value": 1}}),
        ({"metrics": {"value": math.inf}}, None),
    ],
)
def test_missing_or_incompatible_operands_are_errors(
    candidate: dict[str, object], baseline: dict[str, object] | None
) -> None:
    comparison = (
        Comparison.CANDIDATE_MINUS_BASELINE
        if baseline is not None
        else Comparison.CANDIDATE
    )
    outcome = evaluate_assertion(
        assertion(comparison=comparison, operator=AssertionOperator.GT, value=0),
        candidate=candidate,
        baseline=baseline,
    )
    assert outcome.state is AssertionState.ERROR
    assert outcome.reason_codes == ("ASSERTION_OPERAND_ERROR",)


def test_optional_missing_report_referenced_by_assertion_is_error() -> None:
    outcome = evaluate_assertion(
        assertion(),
        candidate={"metrics": None},
        baseline=None,
    )
    assert outcome.state is AssertionState.ERROR
