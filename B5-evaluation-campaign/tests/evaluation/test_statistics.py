"""
Tests for statistical utilities.

The purpose is to verify calculation semantics, especially at small sample
sizes and zero denominators.
"""

import pytest

from l1_automation.evaluation.statistics import (
    wilson_interval,
)


def test_wilson_zero_events_is_not_zero_uncertainty() -> None:
    """
    Zero observed failures in a small sample must not become:

        true failure probability = 0

    The point estimate is zero, but the upper confidence bound remains
    positive.
    """

    result = wilson_interval(
        successes=0,
        trials=10,
        confidence_level=0.95,
    )

    assert result.estimate == 0.0
    assert result.lower_bound == pytest.approx(0.0)
    assert result.upper_bound is not None
    assert result.upper_bound > 0.0


def test_zero_denominator_is_undefined() -> None:
    """
    Example:

        the gate emitted zero PASS decisions.

    Then:

        false releases / PASS decisions

    has no valid denominator.

    Returning zero would misleadingly imply perfect performance.
    """

    result = wilson_interval(
        successes=0,
        trials=0,
        confidence_level=0.95,
    )

    assert result.estimate is None
    assert result.lower_bound is None
    assert result.upper_bound is None


def test_successes_cannot_exceed_trials() -> None:
    with pytest.raises(
        ValueError,
        match="cannot exceed",
    ):
        wilson_interval(
            successes=2,
            trials=1,
        )

