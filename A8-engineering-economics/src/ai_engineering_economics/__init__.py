"""
Component 8: Engineering Productivity & Automation Economics.

The package measures the delivery performance, human effort, resource
consumption, and unit economics of the engineering automation platform.

It deliberately distinguishes:

    generated change
    completed engineering task
    deployed change
    safely delivered change
    business outcome

The package does not treat them as equivalent units.
"""

from .aggregation import EngineeringEconomicsCalculator
from .allocation import CostAllocator
from .policy import ValueAssessmentService
from .service import EngineeringEconomicsService

__all__ = [
    "CostAllocator",
    "EngineeringEconomicsCalculator",
    "EngineeringEconomicsService",
    "ValueAssessmentService",
]

__version__ = "0.1.0"
