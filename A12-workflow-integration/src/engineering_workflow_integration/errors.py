"""Typed failures for Component 12."""


class WorkflowIntegrationError(Exception):
    """Base exception for workflow-integration failures."""


class InvalidExternalEventError(WorkflowIntegrationError):
    """External event could not be safely normalized."""


class UnsupportedExternalEventError(WorkflowIntegrationError):
    """Event is valid but is not supported by this integration."""


class DuplicateExternalEventError(WorkflowIntegrationError):
    """Event has already been successfully accepted."""


class ExternalSystemUnavailableError(WorkflowIntegrationError):
    """External workflow provider is temporarily unavailable."""


class ExternalAuthorizationError(WorkflowIntegrationError):
    """Authentication or authorization against the provider failed."""


class ExternalResourceNotFoundError(WorkflowIntegrationError):
    """Referenced work item, repository or PR does not exist."""


class CorrelationError(WorkflowIntegrationError):
    """Internal and external workflow identities cannot be correlated."""


class StatusPublicationError(WorkflowIntegrationError):
    """An internal result could not be published externally."""
