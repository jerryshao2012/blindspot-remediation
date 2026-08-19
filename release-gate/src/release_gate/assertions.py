"""Pure RFC 6901 lookup and metric assertion evaluation."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeGuard

from release_gate.models import Assertion, AssertionOperator, Comparison, Scalar


class AssertionState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AssertionOutcome:
    state: AssertionState
    actual: Scalar
    reason_codes: tuple[str, ...]


def resolve_pointer(document: object, pointer: str) -> object:
    """Resolve a strict RFC 6901 JSON pointer."""

    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError("JSON pointer must be empty or begin with '/'")
    current = document
    for encoded in pointer[1:].split("/"):
        if re.search(r"~(?:[^01]|$)", encoded):
            raise ValueError("invalid JSON pointer escape")
        token = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise ValueError("JSON pointer member is missing")
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
                raise ValueError("JSON pointer array index is invalid")
            index = int(token)
            if index >= len(current):
                raise ValueError("JSON pointer array index is missing")
            current = current[index]
        else:
            raise ValueError("JSON pointer traverses a scalar")
    return current


def evaluate_assertion(
    assertion: Assertion,
    *,
    candidate: dict[str, object | None],
    baseline: dict[str, object | None] | None,
) -> AssertionOutcome:
    """Evaluate one assertion without tool-specific interpretation."""

    try:
        candidate_value = _metric(candidate, assertion)
        if assertion.comparison is Comparison.CANDIDATE:
            actual = candidate_value
        else:
            if baseline is None:
                raise ValueError("baseline is unavailable")
            baseline_value = _metric(baseline, assertion)
            if assertion.comparison is Comparison.BASELINE:
                actual = baseline_value
            else:
                actual = _subtract(candidate_value, baseline_value)
        scalar = _as_scalar(actual)
        passed = _compare(scalar, assertion.value, assertion.operator)
    except (KeyError, TypeError, ValueError, OverflowError):
        return AssertionOutcome(
            state=AssertionState.ERROR,
            actual=None,
            reason_codes=("ASSERTION_OPERAND_ERROR",),
        )
    return AssertionOutcome(
        state=AssertionState.PASS if passed else AssertionState.FAIL,
        actual=scalar,
        reason_codes=() if passed else ("ASSERTION_FAILED",),
    )


def _metric(values: dict[str, object | None], assertion: Assertion) -> object:
    report = values[assertion.report]
    if report is None:
        raise ValueError("report is unavailable")
    return resolve_pointer(report, assertion.metric)


def _subtract(candidate: object, baseline: object) -> float | int:
    if not _is_number(candidate) or not _is_number(baseline):
        raise TypeError("differential operands must be numeric")
    result = candidate - baseline
    if not math.isfinite(float(result)):
        raise ValueError("differential operand is non-finite")
    return result


def _as_scalar(value: object) -> Scalar:
    if value is None or isinstance(value, (str, bool)):
        return value
    if _is_number(value):
        if not math.isfinite(float(value)):
            raise ValueError("numeric operand is non-finite")
        return value
    raise TypeError("assertion operand is not scalar")


def _compare(actual: Scalar, expected: Scalar, operator: AssertionOperator) -> bool:
    actual_kind = _kind(actual)
    expected_kind = _kind(expected)
    if actual_kind != expected_kind:
        raise TypeError("assertion operands have incompatible types")
    if operator is AssertionOperator.EQ:
        return actual == expected
    if operator is AssertionOperator.NE:
        return actual != expected
    if actual_kind != "number":
        raise TypeError("ordered assertions require finite numbers")
    assert isinstance(actual, (int, float)) and not isinstance(actual, bool)
    assert isinstance(expected, (int, float)) and not isinstance(expected, bool)
    if operator is AssertionOperator.GT:
        return actual > expected
    if operator is AssertionOperator.GTE:
        return actual >= expected
    if operator is AssertionOperator.LT:
        return actual < expected
    if operator is AssertionOperator.LTE:
        return actual <= expected
    raise ValueError("unsupported assertion operator")


def _kind(value: Scalar) -> str:
    if _is_number(value):
        return "number"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    return "string"


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
