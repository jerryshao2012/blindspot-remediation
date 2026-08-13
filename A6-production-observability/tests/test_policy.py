from datetime import datetime, timedelta, timezone

from ai_engineering_observability.models import (
    OperationalHealth,
    OperationalPolicy,
    OperationalWindow,
)
from ai_engineering_observability.policy import SLOEvaluator


NOW = datetime.now(timezone.utc)


def policy() -> OperationalPolicy:
    return OperationalPolicy(
        policy_version="test",
        minimum_observations=100,
        minimum_availability=0.99,
        maximum_error_rate=0.01,
        critical_error_rate=0.05,
        maximum_timeout_rate=0.01,
        maximum_dependency_failure_rate=0.02,
        maximum_p95_latency_ms=1500,
        critical_p95_latency_ms=5000,
    )


def window(
    *,
    observations: int,
    availability: float,
    error_rate: float,
    p95: float,
) -> OperationalWindow:
    return OperationalWindow(
        deployment_id="deployment-1",
        service_name="mortgage-service",
        window_start=NOW,
        window_end=NOW + timedelta(minutes=5),
        observation_count=observations,
        successful_executions=observations,
        failed_executions=0,
        timeout_executions=0,
        cancelled_executions=0,
        completed_processes=observations,
        availability=availability,
        error_rate=error_rate,
        timeout_rate=0.0,
        dependency_failure_rate=0.0,
        process_completion_rate=1.0,
        mean_latency_ms=100,
        p50_latency_ms=100,
        p95_latency_ms=p95,
        p99_latency_ms=p95,
        mean_retry_count=0,
        total_cpu_seconds=10,
        maximum_memory_peak_mb=100,
    )


def test_healthy_window() -> None:
    decision = SLOEvaluator().evaluate(
        window=window(
            observations=1000,
            availability=0.999,
            error_rate=0.001,
            p95=500,
        ),
        policy=policy(),
    )

    assert decision.status == OperationalHealth.HEALTHY


def test_critical_error_rate() -> None:
    decision = SLOEvaluator().evaluate(
        window=window(
            observations=1000,
            availability=0.90,
            error_rate=0.10,
            p95=500,
        ),
        policy=policy(),
    )

    assert decision.status == OperationalHealth.CRITICAL


def test_small_sample_is_not_called_healthy() -> None:
    decision = SLOEvaluator().evaluate(
        window=window(
            observations=10,
            availability=1.0,
            error_rate=0.0,
            p95=100,
        ),
        policy=policy(),
    )

    assert decision.status == OperationalHealth.INSUFFICIENT_DATA
