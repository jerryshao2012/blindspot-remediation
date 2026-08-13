"""
Deterministic process-outcome aggregation.

The central unit is the process instance rather than the raw event.

This matters because one mortgage workflow might emit:

    STARTED
    MANUAL_INTERVENTION
    COMPLETED

Those are three events but one process instance.

Rates must therefore normally use process instances as their denominator,
not event count.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from statistics import mean

from .errors import OutcomeAggregationError
from .models import (
    ProcessEvent,
    ProcessEventType,
    ProcessWindow,
)


def percentile(
    values: list[float],
    quantile: float,
) -> float | None:
    if not values:
        return None

    if not 0.0 <= quantile <= 1.0:
        raise ValueError(
            "quantile must be between zero and one."
        )

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = quantile * (len(ordered) - 1)

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower

    return (
        ordered[lower]
        + fraction
        * (
            ordered[upper]
            - ordered[lower]
        )
    )


class ProcessMetricsCalculator:
    """Aggregate process events into deployment-level process metrics."""

    def calculate(
        self,
        *,
        deployment_id: str,
        process_name: str,
        events: tuple[ProcessEvent, ...],
        window_start: datetime,
        window_end: datetime,
    ) -> ProcessWindow:
        if window_end <= window_start:
            raise OutcomeAggregationError(
                "window_end must be after window_start."
            )

        selected = [
            event
            for event in events
            if (
                event.deployment_id == deployment_id
                and event.process_name == process_name
                and window_start
                <= event.timestamp
                < window_end
            )
        ]

        by_instance: dict[
            str,
            list[ProcessEvent],
        ] = defaultdict(list)

        for event in selected:
            by_instance[event.process_instance_id].append(
                event
            )

        total_instances = len(by_instance)

        completed = 0
        failed = 0
        abandoned = 0
        manual = 0
        rework = 0

        completion_durations: list[float] = []

        for instance_events in by_instance.values():
            event_types = {
                event.event_type
                for event in instance_events
            }

            if ProcessEventType.COMPLETED in event_types:
                completed += 1

            if ProcessEventType.FAILED in event_types:
                failed += 1

            if ProcessEventType.ABANDONED in event_types:
                abandoned += 1

            if (
                ProcessEventType.MANUAL_INTERVENTION
                in event_types
            ):
                manual += 1

            if (
                ProcessEventType.REWORK_REQUIRED
                in event_types
            ):
                rework += 1

            completion_events = [
                event
                for event in instance_events
                if (
                    event.event_type
                    == ProcessEventType.COMPLETED
                    and event.duration_ms is not None
                )
            ]

            if completion_events:
                # There should normally be one terminal completion event.
                # If instrumentation emits duplicates, taking the earliest
                # completion avoids counting one process multiple times.
                earliest_completion = min(
                    completion_events,
                    key=lambda event: event.timestamp,
                )

                completion_durations.append(
                    earliest_completion.duration_ms
                )

        def rate(count: int) -> float | None:
            if total_instances == 0:
                return None

            return count / total_instances

        return ProcessWindow(
            deployment_id=deployment_id,
            process_name=process_name,
            window_start=window_start,
            window_end=window_end,
            process_instances=total_instances,
            completed_instances=completed,
            failed_instances=failed,
            abandoned_instances=abandoned,
            manual_intervention_instances=manual,
            rework_instances=rework,
            completion_rate=rate(completed),
            failure_rate=rate(failed),
            abandonment_rate=rate(abandoned),
            manual_intervention_rate=rate(manual),
            rework_rate=rate(rework),
            mean_completion_duration_ms=(
                mean(completion_durations)
                if completion_durations
                else None
            ),
            p50_completion_duration_ms=percentile(
                completion_durations,
                0.50,
            ),
            p95_completion_duration_ms=percentile(
                completion_durations,
                0.95,
            ),
        )
