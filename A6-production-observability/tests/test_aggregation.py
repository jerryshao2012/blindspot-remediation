from datetime import datetime, timedelta, timezone

from ai_engineering_observability.aggregation import (
    OperationalMetricsCalculator,
)
from ai_engineering_observability.models import (
    ExecutionOutcome,
    RuntimeObservation,
)


NOW = datetime.now(timezone.utc)


def observation(
    index: int,
    *,
    outcome: ExecutionOutcome,
    duration_ms: float,
) -> RuntimeObservation:
    return RuntimeObservation(
        observation_id=f"obs-{index}",
        timestamp=NOW + timedelta(seconds=index),
        deployment_id="deployment-1",
        service_name="mortgage-service",
        operation_name="process",
        outcome=outcome,
        duration_ms=duration_ms,
    )


def test_operational_metrics_are_calculated() -> None:
    observations = (
        observation(
            1,
            outcome=ExecutionOutcome.SUCCESS,
            duration_ms=100,
        ),
        observation(
            2,
            outcome=ExecutionOutcome.SUCCESS,
            duration_ms=200,
        ),
        observation(
            3,
            outcome=ExecutionOutcome.FAILURE,
            duration_ms=300,
        ),
    )

    window = OperationalMetricsCalculator().calculate(
        deployment_id="deployment-1",
        service_name="mortgage-service",
        observations=observations,
        window_start=NOW,
        window_end=NOW + timedelta(minutes=5),
    )

    assert window.observation_count == 3
    assert window.successful_executions == 2
    assert window.failed_executions == 1

    assert window.availability == 2 / 3
    assert window.error_rate == 1 / 3

    assert window.mean_latency_ms == 200
