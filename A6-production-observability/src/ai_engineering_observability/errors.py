"""Typed failures for Component 6."""


class OperationalObservabilityError(Exception):
    """Base class for expected observability failures."""


class TelemetryValidationError(OperationalObservabilityError):
    """A telemetry observation violates the operational schema."""


class CorrelationError(OperationalObservabilityError):
    """Runtime telemetry cannot be safely correlated to a deployment."""


class OperationalAggregationError(OperationalObservabilityError):
    """Operational observations cannot be aggregated correctly."""


class OperationalPolicyError(OperationalObservabilityError):
    """Operational SLO policy is invalid or internally inconsistent."""


class OperationalStorageError(OperationalObservabilityError):
    """Operational evidence cannot be persisted or retrieved."""
