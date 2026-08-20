"""Private, demo-only campaign records and aggregate reporting."""

from __future__ import annotations

from math import sqrt
from statistics import NormalDist
from typing import Any

CONFIDENCE_LEVEL = 0.95
RUN_KINDS = ("trial", "re-gate", "control")
CLASSIFICATIONS = (
    "good_pass",
    "FALSE_RELEASE",
    "FALSE_BLOCK",
    "good_catch",
    "escalated",
    "oracle_error",
)


class CampaignError(RuntimeError):
    """An expected private-campaign validation or publication error."""


def wilson_interval(
    *, events: int, trials: int, confidence_level: float = CONFIDENCE_LEVEL
) -> dict[str, Any]:
    """Return a two-sided Wilson score interval for an event proportion."""

    if trials < 0:
        raise ValueError("trials cannot be negative")
    if events < 0 or events > trials:
        raise ValueError("events must be between zero and trials")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence level must be between zero and one")
    result: dict[str, Any] = {
        "numerator": events,
        "denominator": trials,
        "estimate": None,
        "lower_bound": None,
        "upper_bound": None,
        "confidence_level": confidence_level,
        "method": "wilson",
    }
    if trials == 0:
        return result

    proportion = events / trials
    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence_level) / 2.0)
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    center = (proportion + z_squared / (2.0 * trials)) / denominator
    margin = (
        z
        * sqrt(
            proportion * (1.0 - proportion) / trials
            + z_squared / (4.0 * trials * trials)
        )
        / denominator
    )
    result.update(
        estimate=proportion,
        lower_bound=max(0.0, center - margin),
        upper_bound=min(1.0, center + margin),
    )
    return result
