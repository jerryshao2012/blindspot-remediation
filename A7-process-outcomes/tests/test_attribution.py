from datetime import datetime, timedelta, timezone

from ai_engineering_outcomes.attribution import (
    AttributionAssessor,
)
from ai_engineering_outcomes.models import (
    AttributionStrength,
    KPIObservation,
    KPIType,
)


NOW = datetime.now(timezone.utc)


def kpi(
    *,
    identifier: str,
    value: float,
    start_offset_days: int,
) -> KPIObservation:
    start = NOW + timedelta(
        days=start_offset_days
    )

    return KPIObservation(
        observation_id=identifier,
        metric_name="manual-touch-rate",
        metric_version="1.0",
        metric_type=KPIType.RATE,
        value=value,
        unit="proportion",
        window_start=start,
        window_end=start + timedelta(days=1),
        sample_size=1000,
        process_name="mortgage-processing",
    )


def test_before_after_is_not_called_strong_causal_evidence() -> None:
    baseline = kpi(
        identifier="baseline",
        value=0.30,
        start_offset_days=-10,
    )

    treatment = kpi(
        identifier="treatment",
        value=0.20,
        start_offset_days=1,
    )

    assessment = AttributionAssessor().assess_before_after(
        deployment_id="deployment-1",
        baseline=baseline,
        treatment=treatment,
    )

    assert assessment.strength == AttributionStrength.WEAK

    assert assessment.absolute_difference == -0.10

    assert assessment.relative_difference is not None
