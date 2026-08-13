"""
Statistical analysis for qualification campaigns.

The principal POC statistic is a binomial proportion with a Wilson score
confidence interval.

Why Wilson rather than:

    p ± 1.96 * sqrt(p(1-p)/n)

?

The simple Wald interval behaves poorly for small samples and proportions near
zero or one.

That is exactly where an engineering qualification process can otherwise become
overconfident.

Example:

    10 successes / 10 attempts

looks like:

    100%

but does NOT justify the statement:

    "True reliability is approximately 100%."

The confidence interval exposes that uncertainty.
"""

from __future__ import annotations

import math
from statistics import NormalDist

from .errors import StatisticalAnalysisError
from .models import ProportionEstimate


class StatisticalAnalyzer:
    """Deterministic statistical calculations used by Component 5."""

    def proportion(
        self,
        *,
        successes: int,
        trials: int,
        confidence_level: float = 0.95,
    ) -> ProportionEstimate:
        if trials < 0:
            raise StatisticalAnalysisError(
                "Number of trials cannot be negative."
            )

        if successes < 0 or successes > trials:
            raise StatisticalAnalysisError(
                "Successes must satisfy 0 <= successes <= trials."
            )

        if not 0.0 < confidence_level < 1.0:
            raise StatisticalAnalysisError(
                "Confidence level must be between zero and one."
            )

        if trials == 0:
            return ProportionEstimate(
                successes=0,
                trials=0,
                estimate=None,
                confidence_level=confidence_level,
                lower_bound=None,
                upper_bound=None,
            )

        p_hat = successes / trials

        alpha = 1.0 - confidence_level

        z = NormalDist().inv_cdf(1.0 - alpha / 2.0)

        z_squared = z * z

        denominator = 1.0 + z_squared / trials

        centre = (
            p_hat
            + z_squared / (2.0 * trials)
        ) / denominator

        half_width = (
            z
            * math.sqrt(
                (
                    p_hat * (1.0 - p_hat) / trials
                    + z_squared / (4.0 * trials * trials)
                )
            )
            / denominator
        )

        lower = max(0.0, centre - half_width)
        upper = min(1.0, centre + half_width)

        return ProportionEstimate(
            successes=successes,
            trials=trials,
            estimate=p_hat,
            confidence_level=confidence_level,
            lower_bound=lower,
            upper_bound=upper,
        )
