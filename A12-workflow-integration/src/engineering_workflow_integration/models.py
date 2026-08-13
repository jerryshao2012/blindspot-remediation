"""
Provider-neutral domain models for Component 12.

The important design rule is that provider-specific JSON stops at the adapter.

Component 9 should never need to inspect:

    System.WorkItemType

    resourceContainers

    Azure DevOps service-hook payload structure

    Jira webhook structure

or other provider-specific details.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class WorkflowModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class WorkflowProvider(StrEnum):
    AZURE_DEVOPS = "azure_devops"
    JIRA = "jira"
    OPERATOR = "operator"


class ExternalEventType(StrEnum):
    WORK_ITEM_CREATED = "work_item_created"
    WORK_ITEM_UPDATED = "work_item_updated"
    PULL_REQUEST_CREATED = "pull_request_created"
    PULL_REQUEST_UPDATED = "pull_request_updated"
    PULL_REQUEST_COMPLETED = "pull_request_completed"


class GateOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    MORE_EVIDENCE = "more_evidence"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class ExternalReference(WorkflowModel):
    """
    Stable reference to an object owned by an external engineering system.
    """

    provider: WorkflowProvider

    organization: Annotated[str, Field(min_length=1)]

    project: Annotated[str, Field(min_length=1)]

    resource_type: Annotated[str, Field(min_length=1)]

    resource_id: Annotated[str, Field(min_length=1)]

    web_url: str | None = None


class RepositoryReference(WorkflowModel):
    provider: WorkflowProvider

    organization: Annotated[str, Field(min_length=1)]

    project: Annotated[str, Field(min_length=1)]

    repository_id: Annotated[str, Field(min_length=1)]

    repository_name: Annotated[str, Field(min_length=1)]

    target_branch: Annotated[str, Field(min_length=1)]

    source_branch: str | None = None


class NormalizedWorkflowEvent(WorkflowModel):
    """
    Provider-neutral representation of an inbound workflow event.

    raw_payload is intentionally NOT included.

    Raw provider payloads belong in the ingress/audit boundary rather than
    being propagated throughout the platform.
    """

    event_id: Annotated[str, Field(min_length=1)]

    provider: WorkflowProvider

    event_type: ExternalEventType

    occurred_at: datetime

    subject: ExternalReference

    repository: RepositoryReference | None = None

    correlation_hint: str | None = None


class TaskRequest(WorkflowModel):
    """
    Internal request handed to Component 9.

    Component 12 may extract the requested task type from a controlled field,
    but Component 11 remains authoritative about whether that task type exists
    and is approved.
    """

    request_id: Annotated[str, Field(min_length=1)]

    task_type: Annotated[str, Field(min_length=1, max_length=128)]

    task_specification_version: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]

    title: Annotated[str, Field(min_length=1, max_length=512)]

    requested_change: Annotated[str, Field(min_length=1)]

    work_item: ExternalReference

    repository: RepositoryReference

    requested_by: str | None = None

    metadata: dict[str, str] = Field(default_factory=dict)


class EngineeringRunReference(WorkflowModel):
    run_id: Annotated[str, Field(min_length=1)]

    task_request_id: Annotated[str, Field(min_length=1)]

    task_type: Annotated[str, Field(min_length=1)]

    task_specification_sha256: Annotated[
        str,
        Field(pattern=r"^[0-9a-f]{64}$"),
    ]


class PullRequestReference(WorkflowModel):
    provider: WorkflowProvider

    organization: Annotated[str, Field(min_length=1)]

    project: Annotated[str, Field(min_length=1)]

    repository_id: Annotated[str, Field(min_length=1)]

    pull_request_id: Annotated[str, Field(min_length=1)]

    source_commit_sha: Annotated[
        str,
        Field(pattern=r"^[0-9a-fA-F]{7,64}$"),
    ]


class GatePublication(WorkflowModel):
    """
    Provider-neutral instruction to expose a Component 3 outcome externally.

    Component 12 translates this object into the provider's status vocabulary.
    """

    run: EngineeringRunReference

    pull_request: PullRequestReference

    outcome: GateOutcome

    summary: Annotated[str, Field(min_length=1, max_length=2048)]

    evidence_uri: str | None = None

    decision_sha256: Annotated[
        str,
        Field(pattern=r"^[0-9a-f]{64}$"),
    ]


class ExternalStatusState(StrEnum):
    """
    Provider-neutral subset sufficient for a blocking engineering status.
    """

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ERROR = "error"


class ExternalStatus(WorkflowModel):
    state: ExternalStatusState

    context_genre: Annotated[str, Field(min_length=1, max_length=128)]

    context_name: Annotated[str, Field(min_length=1, max_length=128)]

    description: Annotated[str, Field(min_length=1, max_length=2048)]

    target_url: str | None = None
