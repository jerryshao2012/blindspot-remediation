"""Transparent statistical and distribution helpers."""

from __future__ import annotations

import math
from statistics import NormalDist, mean

from .models import DurationDistribution, ProportionMetric


def proportion_metric(
    *,
    numerator: int,
    denominator: int,
    confidence_level: float,
) -> ProportionMetric:
    """
    Calculate a Wilson score confidence interval.

    A zero denominator produces no estimate rather than an invented zero rate.
    """

    if numerator < 0 or denominator < 0:
        raise ValueError("Counts must not be negative.")

    if numerator > denominator:
        raise ValueError("Numerator cannot exceed denominator.")

    if not 0.0 < confidence_level < 1.0:
        raise ValueError("Invalid confidence level.")

    if denominator == 0:
        return ProportionMetric(
            numerator=numerator,
            denominator=denominator,
            estimate=None,
            confidence_level=confidence_level,
            lower_bound=None,
            upper_bound=None,
        )

    estimate = numerator / denominator
    z = NormalDist().inv_cdf(
        1.0 - (1.0 - confidence_level) / 2.0
    )
    z_squared = z * z

    denominator_adjustment = 1.0 + z_squared / denominator

    centre = (
        estimate + z_squared / (2.0 * denominator)
    ) / denominator_adjustment

    half_width = (
        z
        * math.sqrt(
            estimate * (1.0 - estimate) / denominator
            + z_squared / (4.0 * denominator * denominator)
        )
        / denominator_adjustment
    )

    return ProportionMetric(
        numerator=numerator,
        denominator=denominator,
        estimate=estimate,
        confidence_level=confidence_level,
        lower_bound=max(0.0, centre - half_width),
        upper_bound=min(1.0, centre + half_width),
    )


def percentile(
    values: list[float],
    quantile: float,
) -> float | None:
    """Linear-interpolation percentile."""

    if not values:
        return None

    if not 0.0 <= quantile <= 1.0:
        raise ValueError("Quantile must be between zero and one.")

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = quantile * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower

    return ordered[lower] + fraction * (
        ordered[upper] - ordered[lower]
    )


def duration_distribution(
    durations_hours: list[float],
) -> DurationDistribution:
    """Summarize elapsed-time measurements without dropping tail latency."""

    if any(value < 0.0 for value in durations_hours):
        raise ValueError("Durations must not be negative.")

    return DurationDistribution(
        count=len(durations_hours),
        mean_hours=mean(durations_hours) if durations_hours else None,
        p50_hours=percentile(durations_hours, 0.50),
        p85_hours=percentile(durations_hours, 0.85),
        p95_hours=percentile(durations_hours, 0.95),
    )


def safe_divide(
    numerator: float,
    denominator: float,
) -> float | None:
    """Return None when no defensible denominator exists."""

    if denominator == 0:
        return None

    return numerator / denominator


def relative_reduction(
    *,
    baseline: float,
    treatment: float,
) -> float | None:
    """
    Calculate reduction relative to baseline.

    Positive means treatment is lower.

    A zero baseline has no finite conventional relative reduction.
    """

    if baseline == 0.0:
        return None

    return (baseline - treatment) / abs(baseline)
