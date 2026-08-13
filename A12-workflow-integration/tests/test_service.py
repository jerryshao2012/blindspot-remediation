from typing import Any

import pytest

from engineering_workflow_integration.correlation import (
    InMemoryCorrelationStore,
)
from engineering_workflow_integration.errors import (
    DuplicateExternalEventError,
)
from engineering_workflow_integration.idempotency import (
    InMemoryIdempotencyStore,
)
from engineering_workflow_integration.models import (
    EngineeringRunReference,
    ExternalEventType,
    ExternalReference,
    ExternalStatus,
    NormalizedWorkflowEvent,
    RepositoryReference,
    TaskRequest,
    WorkflowProvider,
)
from engineering_workflow_integration.ports import (
    OrchestratorPort,
    WorkflowProviderPort,
)
from engineering_workflow_integration.service import (
    EngineeringWorkflowIntegrationService,
)


class FakeProvider(WorkflowProviderPort):

    def __init__(self) -> None:
        self.published_statuses: list[ExternalStatus] = []

    def normalize_event(
        self,
        payload: dict[str, Any],
    ) -> NormalizedWorkflowEvent:

        from datetime import datetime, timezone

        return NormalizedWorkflowEvent(
            event_id=str(payload["id"]),
            provider=WorkflowProvider.AZURE_DEVOPS,
            event_type=ExternalEventType.WORK_ITEM_UPDATED,
            occurred_at=datetime.now(timezone.utc),
            subject=ExternalReference(
                provider=WorkflowProvider.AZURE_DEVOPS,
                organization="org",
                project="project",
                resource_type="work_item",
                resource_id="100",
            ),
        )

    async def build_task_request(
        self,
        event: NormalizedWorkflowEvent,
    ) -> TaskRequest:

        return TaskRequest(
            request_id=f"request-{event.event_id}",
            task_type="X1",
            task_specification_version="1.0.0",
            title="POC change",
            requested_change="Perform the bounded X1 change.",
            work_item=event.subject,
            repository=RepositoryReference(
                provider=WorkflowProvider.AZURE_DEVOPS,
                organization="org",
                project="project",
                repository_id="repo",
                repository_name="example",
                target_branch="main",
            ),
        )

    async def publish_status(
        self,
        *,
        pull_request: Any,
        status: ExternalStatus,
    ) -> None:
        self.published_statuses.append(status)


class FakeOrchestrator(OrchestratorPort):

    def __init__(self) -> None:
        self.submission_count = 0

    async def submit_task(
        self,
        request: TaskRequest,
    ) -> EngineeringRunReference:

        self.submission_count += 1

        return EngineeringRunReference(
            run_id=f"run-{self.submission_count}",
            task_request_id=request.request_id,
            task_type=request.task_type,
            task_specification_sha256="a" * 64,
        )


@pytest.mark.asyncio
async def test_event_creates_one_run() -> None:

    provider = FakeProvider()
    orchestrator = FakeOrchestrator()

    service = EngineeringWorkflowIntegrationService(
        provider=provider,
        orchestrator=orchestrator,
        idempotency_store=InMemoryIdempotencyStore(),
        correlation_store=InMemoryCorrelationStore(),
    )

    run = await service.accept_external_event(
        {"id": "event-001"}
    )

    assert run.run_id == "run-1"
    assert orchestrator.submission_count == 1


@pytest.mark.asyncio
async def test_duplicate_event_does_not_create_second_run() -> None:

    provider = FakeProvider()
    orchestrator = FakeOrchestrator()

    service = EngineeringWorkflowIntegrationService(
        provider=provider,
        orchestrator=orchestrator,
        idempotency_store=InMemoryIdempotencyStore(),
        correlation_store=InMemoryCorrelationStore(),
    )

    await service.accept_external_event(
        {"id": "event-001"}
    )

    with pytest.raises(DuplicateExternalEventError):
        await service.accept_external_event(
            {"id": "event-001"}
        )

    assert orchestrator.submission_count == 1
