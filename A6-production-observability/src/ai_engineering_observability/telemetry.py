"""
OpenTelemetry emission.

OpenTelemetry is used as the telemetry abstraction.

Azure Monitor can receive this telemetry through the Azure Monitor
OpenTelemetry distribution/export path.

The domain objects remain independent of Azure Monitor.
"""

from __future__ import annotations

from opentelemetry import metrics, trace

from .models import RuntimeObservation


class OperationalTelemetryEmitter:
    """
    Emit runtime observations into OpenTelemetry.

    IMPORTANT CARDINALITY RULE

    Metrics should not use:

        observation_id
        trace_id
        customer ID
        request body
        source code

    as metric dimensions.

    High-cardinality identifiers belong in traces/logs/evidence stores, not
    metric labels.
    """

    def __init__(
        self,
        instrumentation_name: str = "ai_engineering.production",
    ) -> None:
        self._tracer = trace.get_tracer(instrumentation_name)

        meter = metrics.get_meter(instrumentation_name)

        self._execution_counter = meter.create_counter(
            "ai_engineering.production.executions",
            unit="{execution}",
            description="Number of observed production executions.",
        )

        self._failure_counter = meter.create_counter(
            "ai_engineering.production.failures",
            unit="{execution}",
            description="Number of failed production executions.",
        )

        self._duration = meter.create_histogram(
            "ai_engineering.production.duration",
            unit="ms",
            description="Production execution duration.",
        )

        self._dependency_failures = meter.create_counter(
            "ai_engineering.production.dependency_failures",
            unit="{failure}",
            description="Observed dependency failures.",
        )

    def emit(
        self,
        observation: RuntimeObservation,
    ) -> None:
        attributes = {
            "service.name": observation.service_name,
            "deployment.id": observation.deployment_id,
            "operation.name": observation.operation_name,
            "execution.outcome": observation.outcome.value,
        }

        self._execution_counter.add(
            1,
            attributes=attributes,
        )

        if observation.outcome.value == "failure":
            self._failure_counter.add(
                1,
                attributes=attributes,
            )

        self._duration.record(
            observation.duration_ms,
            attributes=attributes,
        )

        if observation.dependency_failures:
            self._dependency_failures.add(
                observation.dependency_failures,
                attributes=attributes,
            )

        with self._tracer.start_as_current_span(
            "production.execution"
        ) as span:
            span.set_attribute(
                "deployment.id",
                observation.deployment_id,
            )
            span.set_attribute(
                "operation.name",
                observation.operation_name,
            )
            span.set_attribute(
                "execution.outcome",
                observation.outcome.value,
            )
            span.set_attribute(
                "execution.duration_ms",
                observation.duration_ms,
            )
            span.set_attribute(
                "dependency.calls",
                observation.dependency_calls,
            )
            span.set_attribute(
                "dependency.failures",
                observation.dependency_failures,
            )
            span.set_attribute(
                "execution.retry_count",
                observation.retry_count,
            )
