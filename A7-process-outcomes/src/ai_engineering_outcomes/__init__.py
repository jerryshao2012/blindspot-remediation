"""
Component 7: Process Outcome & Business Measurement Bridge.

This package connects production execution to process outcomes and KPI
observations without pretending that correlation automatically establishes
causation.

The package intentionally separates:

    technical operational health
    process performance
    business KPI measurement
    causal attribution

These concepts are related, but they are not interchangeable.
"""

from .aggregation import ProcessMetricsCalculator
from .attribution import AttributionAssessor
from .correlation import OutcomeCorrelationService
from .service import ProcessOutcomeService

__all__ = [
    "AttributionAssessor",
    "OutcomeCorrelationService",
    "ProcessMetricsCalculator",
    "ProcessOutcomeService",
]

__version__ = "0.1.0"
