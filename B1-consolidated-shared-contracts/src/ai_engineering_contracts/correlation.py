"""
Canonical end-to-end correlation spine.

This model exists because our architecture now crosses many distinct domains:

    engineering workflow
    AI engineering run
    candidate artifact
    release
    deployment
    runtime trace
    business process

Not every identifier exists at every lifecycle stage.

Fields therefore become populated progressively.

The object should not be interpreted as a causal graph.

It is a correlation spine.
"""

from __future__ import annotations

from .base import (
    CONTRACT_SCHEMA_VERSION,
    ContractModel,
)
from .ids import (
    CandidateId,
    DeploymentId,
    ProcessInstanceId,
    ReleaseId,
    RunId,
    TaskId,
    TaskRequestId,
    TraceId,
)
from .references import (
    PullRequestReference,
    TaskSpecificationReference,
)


class CorrelationContext(ContractModel):
    schema_version: str = CONTRACT_SCHEMA_VERSION

    task_request_id: TaskRequestId
    task_id: TaskId

    task_specification: TaskSpecificationReference

    run_id: RunId

    candidate_id: CandidateId | None = None

    pull_request: PullRequestReference | None = None

    release_id: ReleaseId | None = None

    deployment_id: DeploymentId | None = None

    trace_id: TraceId | None = None

    process_instance_id: ProcessInstanceId | None = None

