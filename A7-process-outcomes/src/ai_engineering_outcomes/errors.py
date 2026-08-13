"""Typed failures for Component 7."""


class ProcessOutcomeError(Exception):
    """Base class for expected Component 7 failures."""


class OutcomeValidationError(ProcessOutcomeError):
    """A process or KPI observation violates its schema."""


class OutcomeCorrelationError(ProcessOutcomeError):
    """Outcome evidence cannot be safely correlated."""


class OutcomeAggregationError(ProcessOutcomeError):
    """Process observations cannot be aggregated correctly."""


class AttributionError(ProcessOutcomeError):
    """Attribution evidence is invalid or inconsistent."""


class OutcomeStorageError(ProcessOutcomeError):
    """Outcome evidence cannot be persisted or retrieved."""
