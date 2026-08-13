"""
Canonical references shared across component boundaries.

One recurring design principle is:

    LARGE CONTENT LIVES IN ARTIFACT STORAGE.
    CONTRACTS CARRY REFERENCES AND HASHES.

For example, a mutation report may be several megabytes.

GateDecision should point to the report rather than embedding the entire report
inside an orchestration database row.
"""

from __future__ import annotations

from pydantic import Field
from typing_extensions import Annotated

from .base import (
    AwareDatetime,
    ContractModel,
)
from .ids import (
    ArtifactId,
    CandidateId,
    DeploymentId,
    ReleaseId,
    RunId,
    Sha256Digest,
    SpecificationVersion,
    TaskId,
    TaskRequestId,
)


class ArtifactReference(ContractModel):
    """
    Immutable reference to a content-addressed artifact.

    `uri` is deliberately a string rather than HttpUrl because the platform may
    legitimately use custom schemes such as:

        artifact://...
        blob://...
        evidence://...

    Access control is an infrastructure responsibility. The URI should never
    contain embedded credentials.
    """

    artifact_id: ArtifactId

    uri: Annotated[
        str,
        Field(min_length=1),
    ]

    sha256: Sha256Digest

    media_type: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    created_at: AwareDatetime

    producer_component: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    metadata: dict[str, str] = Field(
        default_factory=dict
    )


class TaskSpecificationReference(ContractModel):
    """
    Exact identity of a capability specification.

    `version` is useful for humans.

    `sha256` is the real content identity.
    """

    task_type: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    version: SpecificationVersion

    sha256: Sha256Digest


class RepositoryReference(ContractModel):
    """
    Provider-neutral repository identity.

    Component 12 may construct this from Azure DevOps or Jira-linked metadata.

    No credential belongs in this object.
    """

    provider: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]

    organization: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    project: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    repository_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    repository_name: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    target_branch: Annotated[
        str,
        Field(min_length=1, max_length=512),
    ]


class ExternalResourceReference(ContractModel):
    """
    Reference to a work item, Jira issue, pull request or another external
    workflow object.
    """

    provider: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]

    organization: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    project: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    resource_type: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]

    resource_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    web_url: str | None = None


class PullRequestReference(ContractModel):
    """
    Exact pull-request candidate identity.

    `source_commit_sha` is important.

    A gate PASS applies to a specific candidate commit, not vaguely to a pull
    request that may later receive more commits.
    """

    provider: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]

    organization: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    project: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    repository_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    pull_request_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    source_commit_sha: Annotated[
        str,
        Field(pattern=r"^[0-9a-fA-F]{7,64}$"),
    ]


class ReleaseReference(ContractModel):
    release_id: ReleaseId

    run_id: RunId
    candidate_id: CandidateId

    created_at: AwareDatetime


class DeploymentReference(ContractModel):
    deployment_id: DeploymentId

    release_id: ReleaseId

    environment: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    deployed_at: AwareDatetime

