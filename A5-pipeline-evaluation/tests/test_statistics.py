from ai_engineering_evaluation.statistics import StatisticalAnalyzer


def test_perfect_small_sample_is_not_treated_as_certainty() -> None:
    analyzer = StatisticalAnalyzer()

    result = analyzer.proportion(
        successes=10,
        trials=10,
        confidence_level=0.95,
    )

    assert result.estimate == 1.0
    assert result.lower_bound is not None
    assert result.lower_bound < 1.0


def test_large_perfect_sample_has_tighter_interval() -> None:
    analyzer = StatisticalAnalyzer()

    small = analyzer.proportion(
        successes=10,
        trials=10,
    )

    large = analyzer.proportion(
        successes=1000,
        trials=1000,
    )

    assert small.lower_bound is not None
    assert large.lower_bound is not None

    assert large.lower_bound > small.lower_bound


def test_zero_trials_returns_no_estimate() -> None:
    analyzer = StatisticalAnalyzer()

    result = analyzer.proportion(
        successes=0,
        trials=0,
    )

    assert result.estimate is None
    assert result.lower_bound is None
    assert result.upper_bound is None
