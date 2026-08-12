"""
Statistical utilities for Component 5.

STATISTICAL PHILOSOPHY
----------------------

B5 deliberately avoids pretending that small samples are precise.

For binomial proportions we use the Wilson score interval rather than the
simple normal/Wald interval.

Reasons include:

    - the Wald interval performs poorly for small samples;
    - false-release rates may be near zero;
    - POC sample sizes may initially be modest.

This choice does NOT solve the larger evaluation problems:

    - benchmark representativeness;
    - dependence between repeated runs;
    - correlated benchmark cases;
    - benchmark contamination;
    - oracle quality.

A mathematically correct interval around a biased benchmark statistic remains
a biased answer.

The interval should therefore be interpreted as uncertainty conditional on
the observed benchmark sample and stated assumptions.
"""

from __future__ import annotations

from math import sqrt
from statistics import NormalDist

from .contracts import ProportionEstimate


def wilson_interval(
    *,
    successes: int,
    trials: int,
    confidence_level: float = 0.95,
) -> ProportionEstimate:
    """
    Calculate a two-sided Wilson score interval for a binomial proportion.

    Parameters
    ----------
    successes:
        Number of events of interest.

    trials:
        Number of eligible observations.

    confidence_level:
        Two-sided confidence level.

    Returns
    -------
    ProportionEstimate

    IMPORTANT
    ---------

    `trials == 0` does not produce an invented value of zero.

    Instead:

        estimate = None
        bounds   = None

    because a rate with no denominator is undefined.

    This is particularly important for:

        false_release_given_pass

    when a highly conservative system emits zero PASS decisions.
    """

    if trials < 0:
        raise ValueError(
            "trials cannot be negative."
        )

    if successes < 0:
        raise ValueError(
            "successes cannot be negative."
        )

    if successes > trials:
        raise ValueError(
            "successes cannot exceed trials."
        )

    if not 0.0 < confidence_level < 1.0:
        raise ValueError(
            "confidence_level must be strictly between 0 and 1."
        )

    if trials == 0:
        return ProportionEstimate(
            numerator=successes,
            denominator=trials,
            estimate=None,
            lower_bound=None,
            upper_bound=None,
            confidence_level=confidence_level,
            method="wilson",
        )

    p_hat = successes / trials

    alpha = 1.0 - confidence_level

    z = NormalDist().inv_cdf(
        1.0 - alpha / 2.0
    )

    z_squared = z * z

    denominator = (
        1.0
        + z_squared / trials
    )

    center = (
        p_hat
        + z_squared / (2.0 * trials)
    ) / denominator

    half_width = (
        z
        * sqrt(
            (
                p_hat * (1.0 - p_hat) / trials
                + z_squared / (4.0 * trials * trials)
            )
        )
        / denominator
    )

    lower = max(
        0.0,
        center - half_width,
    )

    upper = min(
        1.0,
        center + half_width,
    )

    return ProportionEstimate(
        numerator=successes,
        denominator=trials,
        estimate=p_hat,
        lower_bound=lower,
        upper_bound=upper,
        confidence_level=confidence_level,
        method="wilson",
    )

