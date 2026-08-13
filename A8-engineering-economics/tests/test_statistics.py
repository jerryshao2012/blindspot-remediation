from ai_engineering_economics.statistics import (
    duration_distribution,
    proportion_metric,
    relative_reduction,
)


def test_small_perfect_sample_is_not_certainty() -> None:
    result = proportion_metric(
        numerator=10,
        denominator=10,
        confidence_level=0.95,
    )

    assert result.estimate == 1.0
    assert result.lower_bound is not None
    assert result.lower_bound < 1.0


def test_duration_distribution_preserves_tail() -> None:
    result = duration_distribution(
        [1.0, 1.0, 1.0, 10.0]
    )

    assert result.count == 4
    assert result.mean_hours == 3.25
    assert result.p95_hours is not None
    assert result.p95_hours > result.p50_hours


def test_relative_cost_reduction() -> None:
    result = relative_reduction(
        baseline=100.0,
        treatment=70.0,
    )

    assert result == 0.30
