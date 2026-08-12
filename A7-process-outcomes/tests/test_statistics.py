from ai_engineering_outcomes.statistics import (
    proportion_confidence_interval,
    safe_relative_difference,
)


def test_wilson_interval_is_valid() -> None:
    interval = proportion_confidence_interval(
        successes=95,
        total=100,
        confidence_level=0.95,
    )

    assert interval is not None

    assert 0.0 <= interval.lower <= 0.95
    assert 0.95 <= interval.upper <= 1.0


def test_no_observations_returns_no_interval() -> None:
    assert (
        proportion_confidence_interval(
            successes=0,
            total=0,
        )
        is None
    )


def test_relative_difference() -> None:
    result = safe_relative_difference(
        baseline=100.0,
        treatment=90.0,
    )

    assert result == -0.10


def test_zero_baseline_has_no_finite_relative_change() -> None:
    assert (
        safe_relative_difference(
            baseline=0.0,
            treatment=10.0,
        )
        is None
    )
