"""
Evidence-manifest models.

The manifest records provenance rather than merely collecting filenames.

A useful manifest must answer:

* Which run?
* Which task type?
* Which repository?
* Which base and candidate?
* Which executor?
* Which gate?
* Which policy?
* Which evidence specification?
* Which decision?
* Which artifacts?
* Which metrics?
* Which token/tool budgets were consumed?
* When did the run occur?
* What manifest format created this record?

The models are immutable and reject unknown fields so that accidental schema
drift fails visibly.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Self

import yaml
from ai_engineering_contracts import ArtifactKind, GateDecision
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .errors import EvidenceConfigurationError


class EvidenceModel(BaseModel):
    """Strict immutable base model."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class RunPhase(StrEnum):
    """Platform phase that produced an artifact."""

    TASK_INPUT = "task_input"
    CHANGE_EXECUTION = "change_execution"
    RELEASE_GATE = "release_gate"
    PIPELINE_EVALUATION = "pipeline_evaluation"
    OPERATIONAL = "operational"
    BUSINESS = "business"
    OTHER = "other"


class ArtifactManifestEntry(EvidenceModel):
    """
    One immutable object referenced by a run manifest.

    ``object_key`` is backend-independent logical storage identity.

    For the local backend it looks like:

        objects/sha256/ab/abcdef...

    A future Azure backend can map the same logical key into Blob Storage.
    """

    artifact_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$",
        ),
    ]
    kind: ArtifactKind
    phase: RunPhase

    sha256: Annotated[
        str,
        Field(pattern=r"^[a-f0-9]{64}$"),
    ]
    size_bytes: Annotated[int, Field(ge=0)]
    media_type: Annotated[str, Field(min_length=3, max_length=255)]

    object_key: Annotated[str, Field(min_length=1, max_length=2_048)]

    source_uri: Annotated[str | None, Field(max_length=4_096)] = None

    producer_component: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]
    producer_version: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    metadata: dict[str, str] = Field(default_factory=dict)


class ComponentExecutionRecord(EvidenceModel):
    """Version and timing information for one participating component."""

    component_name: Annotated[str, Field(min_length=1, max_length=256)]
    component_version: Annotated[str, Field(min_length=1, max_length=128)]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: Annotated[str, Field(min_length=1, max_length=128)]

    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError(
                "Component completion time precedes its start time."
            )

        return self


class ResourceConsumption(EvidenceModel):
    """
    Resource consumption associated with a run.

    Token accounting is explicit because later AI-assisted release gating and
    pipeline evaluation may consume substantial LLM resources.

    Component 4 itself uses zero LLM tokens.
    """

    llm_calls: Annotated[int, Field(ge=0)] = 0
    input_tokens: Annotated[int, Field(ge=0)] = 0
    output_tokens: Annotated[int, Field(ge=0)] = 0
    estimated_cost: Annotated[float, Field(ge=0)] = 0.0

    deterministic_tool_calls: Annotated[int, Field(ge=0)] = 0

    generated_tests: Annotated[int, Field(ge=0)] = 0
    qualified_generated_tests: Annotated[int, Field(ge=0)] = 0
    mutants_generated: Annotated[int, Field(ge=0)] = 0
    meaningful_mutants_survived: Annotated[int, Field(ge=0)] = 0


class RunManifestCore(EvidenceModel):
    """
    Manifest payload whose canonical digest defines the manifest identity.

    The digest itself is deliberately not part of this structure because a
    document cannot directly hash itself without defining a special exclusion
    rule.
    """

    manifest_format_version: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ] = "1.0.0"

    run_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        ),
    ]

    task_type: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        ),
    ]

    task_package_version: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    repository_url: Annotated[str, Field(min_length=1, max_length=4_096)]

    base_commit: Annotated[
        str,
        Field(pattern=r"^[0-9a-fA-F]{40}$"),
    ]

    candidate_commit: Annotated[
        str,
        Field(pattern=r"^[0-9a-fA-F]{40}$"),
    ]

    candidate_tree: Annotated[
        str | None,
        Field(pattern=r"^[0-9a-fA-F]{40}$"),
    ] = None

    gate_decision: GateDecision

    gate_version: Annotated[str, Field(min_length=1, max_length=128)]
    policy_version: Annotated[str, Field(min_length=1, max_length=128)]

    requirement_contract_version: Annotated[
        str | None,
        Field(max_length=128),
    ] = None

    evaluation_specification_version: Annotated[
        str | None,
        Field(max_length=128),
    ] = None

    components: list[ComponentExecutionRecord] = Field(
        min_length=1,
        max_length=100,
    )

    artifacts: list[ArtifactManifestEntry] = Field(
        min_length=1,
        max_length=100_000,
    )

    evidence_metrics: dict[str, float] = Field(default_factory=dict)

    decision_reasons: list[
        Annotated[str, Field(min_length=1, max_length=10_000)]
    ] = Field(default_factory=list, max_length=10_000)

    unmet_obligations: list[
        Annotated[str, Field(min_length=1, max_length=10_000)]
    ] = Field(default_factory=list, max_length=10_000)

    contradictions: list[
        Annotated[str, Field(min_length=1, max_length=10_000)]
    ] = Field(default_factory=list, max_length=10_000)

    resource_consumption: ResourceConsumption = Field(
        default_factory=ResourceConsumption
    )

    started_at: datetime
    completed_at: datetime

    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("base_commit", "candidate_commit", "candidate_tree")
    @classmethod
    def normalize_git_identifiers(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None

    @field_validator("artifacts")
    @classmethod
    def validate_artifact_uniqueness(
        cls,
        value: list[ArtifactManifestEntry],
    ) -> list[ArtifactManifestEntry]:
        artifact_ids = [item.artifact_id for item in value]

        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError(
                "Run manifest contains duplicate artifact IDs."
            )

        return value

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError(
                "Run completion time precedes run start time."
            )

        return self


class RunManifest(EvidenceModel):
    """
    Published immutable run manifest.

    ``manifest_sha256`` is calculated from canonical serialization of ``core``.

    This allows independent verification without circular self-hashing.
    """

    core: RunManifestCore

    manifest_sha256: Annotated[
        str,
        Field(pattern=r"^[a-f0-9]{64}$"),
    ]

    published_at: datetime

    storage_format: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ] = "canonical-json-sha256"


class ManifestVerificationResult(EvidenceModel):
    """Complete result of independent manifest verification."""

    run_id: str
    valid: bool

    manifest_digest_valid: bool
    all_artifacts_present: bool
    all_artifact_digests_valid: bool

    verified_artifact_count: Annotated[int, Field(ge=0)]
    missing_artifacts: list[str] = Field(default_factory=list)
    corrupted_artifacts: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class EvidenceStorageSettings(EvidenceModel):
    """Runtime settings for the local POC evidence backend."""

    root: Path

    verify_after_write: bool = True

    @field_validator("root")
    @classmethod
    def normalize_root(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @classmethod
    def from_yaml(cls, path: Path) -> "EvidenceStorageSettings":
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise EvidenceConfigurationError(
                f"Unable to read evidence configuration {path}: {exc}"
            ) from exc
        except yaml.YAMLError as exc:
            raise EvidenceConfigurationError(
                f"Invalid evidence configuration YAML {path}: {exc}"
            ) from exc

        if not isinstance(raw, dict):
            raise EvidenceConfigurationError(
                "Evidence configuration must contain a mapping."
            )

        try:
            return cls.model_validate(raw)
        except Exception as exc:
            raise EvidenceConfigurationError(
                f"Evidence configuration failed validation: {exc}"
            ) from exc
