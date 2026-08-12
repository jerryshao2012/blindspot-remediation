"""
Primary Component 12 service.

This class coordinates provider normalization, idempotency, orchestration
submission, correlation and outbound status publication.

It contains no LLM calls.
"""

from __future__ import annotations

from typing import Any

from .errors import DuplicateExternalEventError, CorrelationError
from .models import (
    EngineeringRunReference,
    GatePublication,
    PullRequestReference,
)
from .ports import (
    CorrelationStorePort,
    IdempotencyStorePort,
    OrchestratorPort,
    WorkflowProviderPort,
)
from .status_mapping import map_gate_publication


class EngineeringWorkflowIntegrationService:

    def __init__(
        self,
        *,
        provider: WorkflowProviderPort,
        orchestrator: OrchestratorPort,
        idempotency_store: IdempotencyStorePort,
        correlation_store: CorrelationStorePort,
    ) -> None:
        self._provider = provider
        self._orchestrator = orchestrator
        self._idempotency_store = idempotency_store
        self._correlation_store = correlation_store

    async def accept_external_event(
        self,
        payload: dict[str, Any],
    ) -> EngineeringRunReference:
        """
        Convert an external workflow event into exactly one automation run.

        Processing sequence:

            normalize
                ↓
            duplicate check
                ↓
            build TaskRequest
                ↓
            submit to Component 9
                ↓
            persist correlation
                ↓
            mark external event processed

        Important production note:

        The final three operations cross persistence/service boundaries.

        Production should use a durable message architecture and/or outbox
        pattern so that a crash between these operations cannot produce an
        ambiguous state.

        The POC keeps this flow explicit rather than pretending a distributed
        transaction exists.
        """

        event = self._provider.normalize_event(payload)

        provider_name = event.provider.value

        if self._idempotency_store.has_processed(
            provider=provider_name,
            event_id=event.event_id,
        ):
            raise DuplicateExternalEventError(
                f"External event already processed: {event.event_id}"
            )

        request = await self._provider.build_task_request(
            event
        )

        run = await self._orchestrator.submit_task(
            request
        )

        self._correlation_store.bind_run(
            run=run,
            request=request,
        )

        self._idempotency_store.mark_processed(
            provider=provider_name,
            event_id=event.event_id,
        )

        return run

    def bind_pull_request(
        self,
        *,
        run_id: str,
        pull_request: PullRequestReference,
    ) -> None:
        """
        Associate a candidate PR with an existing automation run.

        Component 2 or Component 9 can call this once a PR exists.
        """

        self._correlation_store.bind_pull_request(
            run_id=run_id,
            pull_request=pull_request,
        )

    async def publish_gate_decision(
        self,
        publication: GatePublication,
    ) -> None:
        """
        Translate Component 3's gate decision into an external workflow
        status.

        The PR contained in the publication is checked against our correlation
        record before publication.
        """

        expected_pr = self._correlation_store.get_pull_request(
            run_id=publication.run.run_id
        )

        if expected_pr is None:
            raise CorrelationError(
                "No pull request is bound to engineering run "
                f"{publication.run.run_id!r}."
            )

        if expected_pr != publication.pull_request:
            raise CorrelationError(
                "Gate publication references a pull request different "
                "from the pull request bound to this engineering run."
            )

        status = map_gate_publication(publication)

        await self._provider.publish_status(
            pull_request=publication.pull_request,
            status=status,
        )
