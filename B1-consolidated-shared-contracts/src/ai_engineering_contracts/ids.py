"""
Semantic identifier aliases.

WHY NOT USE PLAIN `str` EVERYWHERE?
-----------------------------------

At runtime these identifiers are strings, but giving them semantic names makes
method signatures much easier for junior developers to understand.

For example:

    def evaluate(run_id: RunId, candidate_id: CandidateId) -> ...

communicates much more than:

    def evaluate(run_id: str, candidate_id: str) -> ...

These aliases also provide consistent length validation.

We intentionally do NOT prescribe UUID format because external systems may use
their own durable identifiers.
"""

from typing_extensions import Annotated

from pydantic import Field


TaskId = Annotated[
    str,
    Field(min_length=1, max_length=256),
]

TaskRequestId = Annotated[
    str,
    Field(min_length=1, max_length=512),
]

RunId = Annotated[
    str,
    Field(min_length=1, max_length=256),
]

CandidateId = Annotated[
    str,
    Field(min_length=1, max_length=256),
]

EvidenceId = Annotated[
    str,
    Field(min_length=1, max_length=256),
]

ArtifactId = Annotated[
    str,
    Field(min_length=1, max_length=256),
]

DecisionId = Annotated[
    str,
    Field(min_length=1, max_length=256),
]

ReleaseId = Annotated[
    str,
    Field(min_length=1, max_length=256),
]

DeploymentId = Annotated[
    str,
    Field(min_length=1, max_length=256),
]

ProcessInstanceId = Annotated[
    str,
    Field(min_length=1, max_length=256),
]

TraceId = Annotated[
    str,
    Field(min_length=1, max_length=256),
]

SpecificationVersion = Annotated[
    str,
    Field(min_length=1, max_length=64),
]

Sha256Digest = Annotated[
    str,
    Field(pattern=r"^[0-9a-f]{64}$"),
]

ContainerImageDigest = Annotated[
    str,
    Field(pattern=r"^sha256:[0-9a-f]{64}$"),
]

