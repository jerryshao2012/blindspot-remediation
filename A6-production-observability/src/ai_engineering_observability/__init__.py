"""
Component 6: Production Operational Observability.

This package measures what released software actually does in production.

It intentionally does NOT decide:

    whether a candidate should originally have been released
    whether a business KPI improved
    whether an observed business change was caused by the software change

Those concerns belong to other architectural layers.
"""

from .aggregation import OperationalMetricsCalculator
from .correlation import DeploymentCorrelationService
from .policy import SLOEvaluator
from .service import OperationalMetricsService
from .telemetry import OperationalTelemetryEmitter

__all__ = [
    "DeploymentCorrelationService",
    "OperationalMetricsCalculator",
    "OperationalMetricsService",
    "OperationalTelemetryEmitter",
    "SLOEvaluator",
]

__version__ = "0.1.0"
