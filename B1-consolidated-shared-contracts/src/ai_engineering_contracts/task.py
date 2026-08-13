"""
Canonical incoming engineering task contracts.

MAJOR CONSOLIDATION
-------------------

Component 9 and Component 12 previously had separate TaskRequest classes.

They are now one object.

Two identifiers are intentionally retained:

    request_id
        identifies this request/trigger.

    task_id
        identifies the underlying engineering task/work item.

For example, an Azure DevOps update may create a unique request while still
referring to Work Item 1234.
"""

from __future__ import annotations

from pydantic import Field
from typing_extensions import Annotated

from .base import (
    AwareDatetime,
    CONTRACT_SCHEMA_VERSION,
    ContractModel,
)
from .enums import TaskSourceKind
from .ids import (
    SpecificationVersion,
    TaskId,
    TaskRequestId,
)
from .references import (
    ExternalResourceReference,
    RepositoryReference,
)


class RequestedCapability(ContractModel):
    """
    Capability requested by the task source.

    This is NOT yet authoritative.

    Component 9 passes this request to Component 11, which returns the resolved
    and content-hashed TaskSpecification.
    """

    task_type: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    requested_version: SpecificationVersion


class TaskRequest(ContractModel):
    schema_version: str = CONTRACT_SCHEMA_VERSION

    request_id: TaskRequestId
    task_id: TaskId

    source_kind: TaskSourceKind

    capability: RequestedCapability

    title: Annotated[
        str,
        Field(min_length=1, max_length=512),
    ]

    requested_change: Annotated[
        str,
        Field(min_length=1),
    ]

    repository: RepositoryReference

    base_revision: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    created_at: AwareDatetime

    requested_by: str | None = None

    external_work_item: ExternalResourceReference | None = None

    metadata: dict[str, str] = Field(
        default_factory=dict
    )

