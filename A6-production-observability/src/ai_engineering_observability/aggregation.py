"""
Deterministic operational metric aggregation.

No LLM is used here.

If 1,000 production executions occurred, we should calculate latency,
availability, failure rates, and dependency behaviour from the observations
rather than ask an LLM to estimate whether the system appears healthy.
"""

from __future__ import annotations

import math
from datetime import datetime
from statistics import mean

from .errors import OperationalAggregationError
from .models import (
    ExecutionOutcome,
    OperationalWindow,
    ProcessOutcome,
    RuntimeObservation,
)


def percentile(
    values: list[float],
    percentile_value: float,
) -> float | None:
    """
    Calculate a percentile using linear interpolation.

    This implementation is intentionally explicit so junior engineers and data
    scientists can understand exactly how the reported percentile is produced.
    """

    if not values:
        return None

    if not 0.0 <= percentile_value <= 1.0:
        raise ValueError(
            "percentile_value must be between zero and one."
        )

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = percentile_value * (len(ordered) - 1)

    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return ordered[lower_index]

    fraction = position - lower_index

    return (
        ordered[lower_index]
        + fraction
        * (
            ordered[upper_index]
            - ordered[lower_index]
        )
    )


class OperationalMetricsCalculator:
    """Aggregate raw runtime observations into one operational window."""

    def calculate(
        self,
        *,
        deployment_id: str,
        service_name: str,
        observations: tuple[RuntimeObservation, ...],
        window_start: datetime,
        window_end: datetime,
    ) -> OperationalWindow:
        if window_end <= window_start:
            raise OperationalAggregationError(
                "window_end must be after window_start."
            )

        selected = [
            observation
            for observation in observations
            if (
                observation.deployment_id == deployment_id
                and observation.service_name == service_name
                and window_start
                <= observation.timestamp
                < window_end
            )
        ]

        total = len(selected)

        successes = sum(
            observation.outcome == ExecutionOutcome.SUCCESS
            for observation in selected
        )

        failures = sum(
            observation.outcome == ExecutionOutcome.FAILURE
            for observation in selected
        )

        timeouts = sum(
            observation.outcome == ExecutionOutcome.TIMEOUT
            for observation in selected
        )

        cancelled = sum(
            observation.outcome == ExecutionOutcome.CANCELLED
            for observation in selected
        )

        completed_processes = sum(
            observation.process_outcome == ProcessOutcome.COMPLETED
            for observation in selected
        )

        latencies = [
            observation.duration_ms
            for observation in selected
        ]

        dependency_calls = sum(
            observation.dependency_calls
            for observation in selected
        )

        dependency_failures = sum(
            observation.dependency_failures
            for observation in selected
        )

        retries = [
            observation.retry_count
            for observation in selected
        ]

        if total == 0:
            availability = None
            error_rate = None
            timeout_rate = None
            completion_rate = None
        else:
            availability = successes / total
            error_rate = failures / total
            timeout_rate = timeouts / total
            completion_rate = completed_processes / total

        dependency_failure_rate = (
            dependency_failures / dependency_calls
            if dependency_calls > 0
            else None
        )

        return OperationalWindow(
            deployment_id=deployment_id,
            service_name=service_name,
            window_start=window_start,
            window_end=window_end,
            observation_count=total,
            successful_executions=successes,
            failed_executions=failures,
            timeout_executions=timeouts,
            cancelled_executions=cancelled,
            completed_processes=completed_processes,
            availability=availability,
            error_rate=error_rate,
            timeout_rate=timeout_rate,
            dependency_failure_rate=dependency_failure_rate,
            process_completion_rate=completion_rate,
            mean_latency_ms=mean(latencies) if latencies else None,
            p50_latency_ms=percentile(latencies, 0.50),
            p95_latency_ms=percentile(latencies, 0.95),
            p99_latency_ms=percentile(latencies, 0.99),
            mean_retry_count=mean(retries) if retries else None,
            total_cpu_seconds=sum(
                observation.cpu_seconds
                for observation in selected
            ),
            maximum_memory_peak_mb=max(
                (
                    observation.memory_peak_mb
                    for observation in selected
                ),
                default=0.0,
            ),
        )
