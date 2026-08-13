"""
Component 9: Engineering Automation Orchestrator & Task Control Plane.

The orchestrator coordinates the AI engineering pipeline.

It intentionally contains no LLM client.

That is an architectural control, not an implementation omission.

The orchestrator determines workflow from:

    task definition
    orchestration policy
    component results
    resource budgets
    deterministic state transitions

AI-capable components remain behind explicit ports.
"""

from .service import EngineeringAutomationOrchestrator
from .state_machine import OrchestrationStateMachine

__all__ = [
    "EngineeringAutomationOrchestrator",
    "OrchestrationStateMachine",
]

__version__ = "0.1.0"
