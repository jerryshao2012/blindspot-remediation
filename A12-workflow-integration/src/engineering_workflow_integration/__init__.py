"""
Component 12 — Engineering Workflow Integration Service.

This package isolates external engineering workflow products from the
internal automation architecture.

The rest of the platform should deal in our domain contracts rather than
Azure DevOps or Jira payloads.
"""

from .service import EngineeringWorkflowIntegrationService

__all__ = ["EngineeringWorkflowIntegrationService"]

__version__ = "0.1.0"
