"""
Small, dependency-light statistical helpers.

Component 7 deliberately avoids asking an LLM to estimate uncertainty.

For the POC we implement transparent analytical confidence intervals that a
junior data scientist can inspect.

A mature implementation may eventually use scipy/statsmodels or a centrally
approved enterprise statistics package, but the formulas here remain useful
for understanding what is being calculated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist


@dataclass(frozen=True)
class ConfidenceInterval:
    lower: float
    upper: float
    confidence_level: float


def proportion_confidence_interval(
    *,
    successes: int,
    total: int,
    confidence_level: float = 0.95,
) -> ConfidenceInterval | None:
    """
    Wilson score interval for a binomial proportion.

    Wilson is preferred here over the naive Wald interval because the Wald
    interval behaves poorly for small samples and proportions close to zero
    or one.

    No interval is returned when total == 0 because there is no information.
    """

    if successes < 0:
        raise ValueError("successes cannot be negative.")

    if total < 0:
        raise ValueError("total cannot be negative.")

    if successes > total:
        raise ValueError(
            "successes cannot exceed total."
        )

    if not 0.0 < confidence_level < 1.0:
        raise ValueError(
            "confidence_level must be between zero and one."
        )

    if total == 0:
        return None

    alpha = 1.0 - confidence_level

    z = NormalDist().inv_cdf(
        1.0 - alpha / 2.0
    )

    proportion = successes / total

    denominator = 1.0 + (z * z / total)

    center = (
        proportion
        + z * z / (2.0 * total)
    ) / denominator

    half_width = (
        z
        * math.sqrt(
            (
                proportion
                * (1.0 - proportion)
                / total
            )
            + (
                z * z
                / (4.0 * total * total)
            )
        )
        / denominator
    )

    return ConfidenceInterval(
        lower=max(0.0, center - half_width),
        upper=min(1.0, center + half_width),
        confidence_level=confidence_level,
    )


def safe_relative_difference(
    *,
    baseline: float,
    treatment: float,
) -> float | None:
    """
    Calculate relative change.

    If baseline == 0 there is no finite percentage change with the usual
    definition, so None is returned instead of inventing a number.
    """

    if baseline == 0.0:
        return None

    return (
        treatment - baseline
    ) / abs(baseline)
