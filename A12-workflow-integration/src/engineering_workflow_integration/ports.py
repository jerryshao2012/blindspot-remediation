"""
Ports used by Component 12.

Provider APIs and platform services are intentionally represented as
interfaces.

This allows:

    real Azure DevOps in production

    deterministic fakes in unit tests

    Jira later

without rewriting EngineeringWorkflowIntegrationService.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import (
    EngineeringRunReference,
    ExternalStatus,
    GatePublication,
    NormalizedWorkflowEvent,
    PullRequestReference,
    TaskRequest,
)


class WorkflowProviderPort(ABC):

    @abstractmethod
    def normalize_event(
        self,
        payload: dict[str, Any],
    ) -> NormalizedWorkflowEvent:
        raise NotImplementedError(
            "WorkflowProviderPort.normalize_event must be implemented."
        )

    @abstractmethod
    async def build_task_request(
        self,
        event: NormalizedWorkflowEvent,
    ) -> TaskRequest:
        raise NotImplementedError(
            "WorkflowProviderPort.build_task_request must be implemented."
        )

    @abstractmethod
    async def publish_status(
        self,
        *,
        pull_request: PullRequestReference,
        status: ExternalStatus,
    ) -> None:
        raise NotImplementedError(
            "WorkflowProviderPort.publish_status must be implemented."
        )


class OrchestratorPort(ABC):
    """
    Minimal Component 9 boundary needed by Component 12.

    The full Orchestrator can expose many more operations internally.
    Component 12 should depend only on what it needs.
    """

    @abstractmethod
    async def submit_task(
        self,
        request: TaskRequest,
    ) -> EngineeringRunReference:
        raise NotImplementedError(
            "OrchestratorPort.submit_task must be implemented."
        )


class IdempotencyStorePort(ABC):

    @abstractmethod
    def has_processed(
        self,
        *,
        provider: str,
        event_id: str,
    ) -> bool:
        raise NotImplementedError(
            "IdempotencyStorePort.has_processed must be implemented."
        )

    @abstractmethod
    def mark_processed(
        self,
        *,
        provider: str,
        event_id: str,
    ) -> None:
        raise NotImplementedError(
            "IdempotencyStorePort.mark_processed must be implemented."
        )


class CorrelationStorePort(ABC):

    @abstractmethod
    def bind_run(
        self,
        *,
        run: EngineeringRunReference,
        request: TaskRequest,
    ) -> None:
        raise NotImplementedError(
            "CorrelationStorePort.bind_run must be implemented."
        )

    @abstractmethod
    def bind_pull_request(
        self,
        *,
        run_id: str,
        pull_request: PullRequestReference,
    ) -> None:
        raise NotImplementedError(
            "CorrelationStorePort.bind_pull_request must be implemented."
        )

    @abstractmethod
    def get_pull_request(
        self,
        *,
        run_id: str,
    ) -> PullRequestReference | None:
        raise NotImplementedError(
            "CorrelationStorePort.get_pull_request must be implemented."
        )
