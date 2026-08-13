"""Typed failures for Component 8."""


class EngineeringEconomicsError(Exception):
    """Base class for expected Component 8 failures."""


class EconomicsValidationError(EngineeringEconomicsError):
    """An economics or delivery record violates its schema."""


class CostAllocationError(EngineeringEconomicsError):
    """A cost cannot be assigned according to the configured rules."""


class EconomicsAggregationError(EngineeringEconomicsError):
    """Engineering observations cannot be aggregated consistently."""


class EconomicsPolicyError(EngineeringEconomicsError):
    """The value-assessment policy is invalid or cannot be evaluated."""


class EconomicsStorageError(EngineeringEconomicsError):
    """Engineering economics evidence cannot be stored or retrieved."""
