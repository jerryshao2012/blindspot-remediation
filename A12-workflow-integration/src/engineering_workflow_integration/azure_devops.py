"""
Azure DevOps adapter.

The adapter translates Azure DevOps representations into Component 12's
provider-neutral contracts.

Authentication is injected through an access-token provider.

Production should normally obtain tokens through enterprise-approved identity
mechanisms rather than storing long-lived credentials in source code.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from .errors import (
    ExternalAuthorizationError,
    ExternalResourceNotFoundError,
    ExternalSystemUnavailableError,
    InvalidExternalEventError,
    UnsupportedExternalEventError,
)
from .models import (
    ExternalEventType,
    ExternalReference,
    ExternalStatus,
    NormalizedWorkflowEvent,
    PullRequestReference,
    RepositoryReference,
    TaskRequest,
    WorkflowProvider,
)
from .ports import WorkflowProviderPort


AZURE_DEVOPS_API_VERSION = "7.1"


class AzureDevOpsWorkflowAdapter(WorkflowProviderPort):
    """
    Azure DevOps implementation of WorkflowProviderPort.

    Controlled work-item fields are configurable because organizations often
    use different custom-field names.

    We intentionally do not silently guess field names.
    """

    def __init__(
        self,
        *,
        organization: str,
        project: str,
        token_provider: Callable[[], str],
        task_type_field: str,
        task_version_field: str,
        repository_id_field: str,
        repository_name_field: str,
        target_branch_field: str,
        requested_change_field: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._organization = organization
        self._project = project
        self._token_provider = token_provider

        self._task_type_field = task_type_field
        self._task_version_field = task_version_field
        self._repository_id_field = repository_id_field
        self._repository_name_field = repository_name_field
        self._target_branch_field = target_branch_field
        self._requested_change_field = requested_change_field

        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0)
        )

    def normalize_event(
        self,
        payload: dict[str, Any],
    ) -> NormalizedWorkflowEvent:
        """
        Normalize a subset of Azure DevOps service-hook events.

        For the POC we deliberately support work-item creation/update only.

        Unsupported events fail explicitly rather than being partially
        interpreted.
        """

        event_id = payload.get("id")
        event_type = payload.get("eventType")
        created_date = payload.get("createdDate")
        resource = payload.get("resource")

        if not isinstance(event_id, str) or not event_id:
            raise InvalidExternalEventError(
                "Azure DevOps event does not contain a valid event id."
            )

        if not isinstance(resource, dict):
            raise InvalidExternalEventError(
                "Azure DevOps event does not contain a resource object."
            )

        event_mapping = {
            "workitem.created": ExternalEventType.WORK_ITEM_CREATED,
            "workitem.updated": ExternalEventType.WORK_ITEM_UPDATED,
        }

        normalized_type = event_mapping.get(event_type)

        if normalized_type is None:
            raise UnsupportedExternalEventError(
                f"Unsupported Azure DevOps event type: {event_type!r}"
            )

        work_item_id = resource.get("id")

        if work_item_id is None:
            # Update events can represent the work-item id differently.
            work_item_id = resource.get("workItemId")

        if work_item_id is None:
            raise InvalidExternalEventError(
                "Unable to determine Azure DevOps work-item id."
            )

        occurred_at = self._parse_datetime(created_date)

        subject = ExternalReference(
            provider=WorkflowProvider.AZURE_DEVOPS,
            organization=self._organization,
            project=self._project,
            resource_type="work_item",
            resource_id=str(work_item_id),
        )

        return NormalizedWorkflowEvent(
            event_id=event_id,
            provider=WorkflowProvider.AZURE_DEVOPS,
            event_type=normalized_type,
            occurred_at=occurred_at,
            subject=subject,
        )

    async def build_task_request(
        self,
        event: NormalizedWorkflowEvent,
    ) -> TaskRequest:
        """
        Retrieve the authoritative current work-item representation and
        translate controlled fields into a TaskRequest.

        We fetch the work item rather than trusting that every webhook payload
        contains a complete current representation.
        """

        work_item = await self._get_work_item(
            event.subject.resource_id
        )

        fields = work_item.get("fields")

        if not isinstance(fields, dict):
            raise InvalidExternalEventError(
                "Azure DevOps work item contains no valid fields object."
            )

        title = self._required_string(
            fields,
            "System.Title",
        )

        task_type = self._required_string(
            fields,
            self._task_type_field,
        )

        task_version = self._required_string(
            fields,
            self._task_version_field,
        )

        repository_id = self._required_string(
            fields,
            self._repository_id_field,
        )

        repository_name = self._required_string(
            fields,
            self._repository_name_field,
        )

        target_branch = self._required_string(
            fields,
            self._target_branch_field,
        )

        requested_change = self._required_string(
            fields,
            self._requested_change_field,
        )

        repository = RepositoryReference(
            provider=WorkflowProvider.AZURE_DEVOPS,
            organization=self._organization,
            project=self._project,
            repository_id=repository_id,
            repository_name=repository_name,
            target_branch=target_branch,
        )

        return TaskRequest(
            request_id=(
                f"azure-devops:"
                f"{self._organization}:"
                f"{self._project}:"
                f"{event.subject.resource_id}:"
                f"{event.event_id}"
            ),
            task_type=task_type,
            task_specification_version=task_version,
            title=title,
            requested_change=requested_change,
            work_item=event.subject,
            repository=repository,
            metadata={
                "source_event_id": event.event_id,
                "source_event_type": event.event_type.value,
            },
        )

    async def publish_status(
        self,
        *,
        pull_request: PullRequestReference,
        status: ExternalStatus,
    ) -> None:
        """
        Publish a status to an Azure DevOps pull request.

        Branch policy can separately require this status.

        This method publishes the result; it does not configure the branch
        policy itself.
        """

        repository_id = quote(
            pull_request.repository_id,
            safe="",
        )

        pull_request_id = quote(
            pull_request.pull_request_id,
            safe="",
        )

        url = (
            f"https://dev.azure.com/"
            f"{quote(self._organization, safe='')}/"
            f"{quote(self._project, safe='')}/"
            f"_apis/git/repositories/"
            f"{repository_id}/"
            f"pullRequests/"
            f"{pull_request_id}/statuses"
        )

        azure_state = {
            "pending": "pending",
            "succeeded": "succeeded",
            "failed": "failed",
            "error": "error",
        }[status.state.value]

        body: dict[str, Any] = {
            "state": azure_state,
            "description": status.description,
            "context": {
                "name": status.context_name,
                "genre": status.context_genre,
            },
        }

        if status.target_url is not None:
            body["targetUrl"] = status.target_url

        response = await self._request(
            "POST",
            url,
            json=body,
            params={
                "api-version": AZURE_DEVOPS_API_VERSION,
            },
        )

        # Reading the response body is unnecessary for our domain contract,
        # but raise_for_status semantics have already been handled in
        # _request().
        _ = response

    async def _get_work_item(
        self,
        work_item_id: str,
    ) -> dict[str, Any]:

        encoded_id = quote(work_item_id, safe="")

        url = (
            f"https://dev.azure.com/"
            f"{quote(self._organization, safe='')}/"
            f"{quote(self._project, safe='')}/"
            f"_apis/wit/workitems/{encoded_id}"
        )

        response = await self._request(
            "GET",
            url,
            params={
                "$expand": "relations",
                "api-version": AZURE_DEVOPS_API_VERSION,
            },
        )

        payload = response.json()

        if not isinstance(payload, dict):
            raise InvalidExternalEventError(
                "Azure DevOps work-item response was not a JSON object."
            )

        return payload

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Centralized HTTP failure translation.

        Retry policy should normally be applied outside this adapter or by
        infrastructure rather than hiding unbounded retries here.
        """

        token = self._token_provider()

        if not token:
            raise ExternalAuthorizationError(
                "Azure DevOps token provider returned no access token."
            )

        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/json"

        try:
            response = await self._client.request(
                method,
                url,
                headers=headers,
                **kwargs,
            )
        except httpx.TimeoutException as exc:
            raise ExternalSystemUnavailableError(
                "Azure DevOps request timed out."
            ) from exc
        except httpx.NetworkError as exc:
            raise ExternalSystemUnavailableError(
                "Azure DevOps network request failed."
            ) from exc

        if response.status_code in {401, 403}:
            raise ExternalAuthorizationError(
                "Azure DevOps rejected the integration identity."
            )

        if response.status_code == 404:
            raise ExternalResourceNotFoundError(
                f"Azure DevOps resource was not found: {url}"
            )

        if response.status_code == 429:
            raise ExternalSystemUnavailableError(
                "Azure DevOps rate limit was reached."
            )

        if 500 <= response.status_code <= 599:
            raise ExternalSystemUnavailableError(
                "Azure DevOps returned a server-side failure."
            )

        response.raise_for_status()

        return response

    @staticmethod
    def _required_string(
        fields: dict[str, Any],
        name: str,
    ) -> str:

        value = fields.get(name)

        if not isinstance(value, str) or not value.strip():
            raise InvalidExternalEventError(
                f"Required Azure DevOps field is missing or invalid: {name}"
            )

        return value.strip()

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime:

        if not isinstance(value, str):
            return datetime.now(timezone.utc)

        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise InvalidExternalEventError(
                f"Invalid Azure DevOps event timestamp: {value!r}"
            ) from exc

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed
