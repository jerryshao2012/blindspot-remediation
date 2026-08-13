"""
Canonical candidate-change artifact.

MAJOR CONSOLIDATION
-------------------

Previous components used CandidatePatch.

The platform now uses CandidateArtifact.

Why "Artifact"?

Because the candidate is more than the textual patch.

It carries:

    candidate identity
    baseline revision
    candidate revision
    immutable patch artifact
    run identity
    task identity
    execution evidence
    creation timestamp

The actual code remains in version control/artifact storage.
"""

from __future__ import annotations

from pydantic import Field
from typing_extensions import Annotated

from .base import (
    AwareDatetime,
    CONTRACT_SCHEMA_VERSION,
    ContractModel,
)
from .ids import (
    CandidateId,
    RunId,
    TaskId,
)
from .references import ArtifactReference


class CandidateArtifact(ContractModel):
    schema_version: str = CONTRACT_SCHEMA_VERSION

    candidate_id: CandidateId

    run_id: RunId
    task_id: TaskId

    base_revision: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    candidate_revision: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    patch_artifact: ArtifactReference

    execution_evidence: tuple[
        ArtifactReference,
        ...,
    ] = ()

    change_rationale: Annotated[
        str | None,
        Field(max_length=10_000),
    ] = None

    created_at: AwareDatetime

