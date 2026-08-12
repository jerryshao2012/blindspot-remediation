"""
Component-local configuration and evidence models.

Cross-service records such as GateRequest, GateResult, ControlResult, and
ArtifactReference remain in ``ai_engineering_contracts``.

The release gate treats three concepts separately:

1. Evaluation specification:
   What controls should execute and what evidence should be collected?

2. Release policy:
   How should normalized evidence become PASS, FAIL, HUMAN_REVIEW_REQUIRED,
   or MORE_EVIDENCE_REQUIRED?

3. Runtime settings:
   Where and how should the gate run locally?

The separation is deliberate. Changing a command is not the same as changing a
release threshold, and both changes must be independently versioned.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Self

import yaml
from ai_engineering_contracts import (
    ArtifactKind,
    ArtifactReference,
    ControlSeverity,
    EvidenceStrategy,
    GateDecision,
    GateRequest,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .errors import ConfigurationError


class GateModel(BaseModel):
    """Strict and immutable base model for gate-local contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class ReportParser(StrEnum):
    """Supported deterministic evidence-report formats."""

    NONE = "none"
    JUNIT_XML = "junit_xml"
    COVERAGE_JSON = "coverage_json"
    JSON_METRICS = "json_metrics"


class ComparisonOperator(StrEnum):
    """Supported deterministic metric comparisons."""

    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    EQUAL = "eq"
    NOT_EQUAL = "ne"


class MissingMetricAction(StrEnum):
    """Policy response when a required metric is unavailable."""

    FAIL = "fail"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"


class ReportSpec(GateModel):
    """
    One report expected from a deterministic control.

    ``path`` is relative to the repository root.

    For JSON_METRICS, ``metric_paths`` maps normalized metric names to dotted
    JSON paths. Example:

        metric_paths:
          mutation_score: "metrics.mutation_score"
          survived_mutants: "metrics.survived"

    Dotted paths support dictionary keys and zero-based list indexes.
    """

    report_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        ),
    ]
    path: Annotated[str, Field(min_length=1, max_length=1_024)]
    parser: ReportParser
    required: bool = True
    artifact_kind: ArtifactKind = ArtifactKind.TEST_RESULTS
    media_type: Annotated[str, Field(min_length=3, max_length=255)]
    metric_paths: dict[
        Annotated[
            str,
            Field(
                min_length=1,
                max_length=128,
                pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
            ),
        ],
        Annotated[str, Field(min_length=1, max_length=1_024)],
    ] = Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def validate_report_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        path = Path(normalized)
        if path.is_absolute():
            raise ValueError("Report paths must be repository-relative.")
        if ".." in path.parts:
            raise ValueError(
                "Report paths must not contain parent-directory traversal."
            )
        return normalized

    @model_validator(mode="after")
    def validate_parser_configuration(self) -> Self:
        if self.parser == ReportParser.JSON_METRICS and not self.metric_paths:
            raise ValueError(
                "JSON_METRICS reports require at least one metric path."
            )
        if self.parser != ReportParser.JSON_METRICS and self.metric_paths:
            raise ValueError(
                "metric_paths are valid only with the JSON_METRICS parser."
            )
        return self


class DeterministicControlSpec(GateModel):
    """
    One authoritative deterministic assurance control.

    Commands are argument arrays and always execute with ``shell=False``.
    Consequently, shell syntax such as pipes, redirection, ``&&``, and ``;`` is
    unavailable.

    A control may produce zero or more reports. Command exit status remains an
    authoritative fact even when report parsing fails.
    """

    control_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        ),
    ]
    name: Annotated[str, Field(min_length=1, max_length=512)]
    description: Annotated[str, Field(min_length=1, max_length=4_000)]
    command: list[Annotated[str, Field(min_length=1, max_length=4_096)]] = Field(
        min_length=1,
        max_length=100,
    )
    timeout_seconds: Annotated[int, Field(gt=0, le=86_400)] = 600
    working_directory: Annotated[str, Field(min_length=1, max_length=1_024)] = "."
    environment: dict[
        Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")],
        Annotated[str, Field(max_length=4_096)],
    ] = Field(default_factory=dict)
    severity: ControlSeverity
    strategy: EvidenceStrategy
    expected_exit_codes: list[int] = Field(default_factory=lambda: [0])
    reports: list[ReportSpec] = Field(default_factory=list, max_length=100)
    continue_after_failure: bool = True

    @field_validator("command")
    @classmethod
    def reject_shell_control_tokens(cls, value: list[str]) -> list[str]:
        prohibited_standalone_tokens = {
            "|",
            "||",
            "&&",
            ";",
            ">",
            ">>",
            "<",
            "<<",
        }
        for argument in value:
            if argument in prohibited_standalone_tokens:
                raise ValueError(
                    f"Shell control token {argument!r} is not allowed."
                )
            if "\x00" in argument:
                raise ValueError("Command arguments must not contain NUL bytes.")
        return value

    @field_validator("working_directory")
    @classmethod
    def validate_working_directory(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        path = Path(normalized)
        if path.is_absolute():
            raise ValueError("working_directory must be repository-relative.")
        if ".." in path.parts:
            raise ValueError(
                "working_directory must not contain parent-directory traversal."
            )
        return normalized

    @field_validator("expected_exit_codes")
    @classmethod
    def validate_exit_codes(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("expected_exit_codes must not be empty.")
        if len(value) != len(set(value)):
            raise ValueError("expected_exit_codes must not contain duplicates.")
        return value


class RequirementContract(GateModel):
    """
    Deterministic requirement contract used by this initial gate.

    No LLM interprets free text in Component 3. Acceptance criteria are retained
    for traceability and future AI-assisted evidence generation, but deterministic
    controls must explicitly operationalize them.
    """

    version: Annotated[
        str,
        Field(
            pattern=(
                r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
            )
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
    title: Annotated[str, Field(min_length=1, max_length=512)]
    task_description: Annotated[str, Field(min_length=1, max_length=20_000)]
    acceptance_criteria: list[
        Annotated[str, Field(min_length=1, max_length=20_000)]
    ] = Field(min_length=1, max_length=1_000)
    permitted_paths: list[
        Annotated[str, Field(min_length=1, max_length=1_024)]
    ] = Field(min_length=1, max_length=10_000)
    prohibited_paths: list[
        Annotated[str, Field(min_length=1, max_length=1_024)]
    ] = Field(default_factory=list, max_length=10_000)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("acceptance_criteria")
    @classmethod
    def reject_duplicate_criteria(cls, value: list[str]) -> list[str]:
        normalized = [item.casefold() for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("acceptance_criteria must not contain duplicates.")
        return value


class EvaluationSpecification(GateModel):
    """Versioned specification of deterministic assurance controls."""

    version: Annotated[
        str,
        Field(
            pattern=(
                r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
            )
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
    controls: list[DeterministicControlSpec] = Field(
        min_length=1,
        max_length=1_000,
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("controls")
    @classmethod
    def reject_duplicate_control_ids(
        cls,
        value: list[DeterministicControlSpec],
    ) -> list[DeterministicControlSpec]:
        identifiers = [item.control_id for item in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("controls must not contain duplicate control IDs.")
        return value


class MetricThreshold(GateModel):
    """
    One release-policy threshold over normalized evidence.

    Metric names use this format:

        <control_id>.<metric_name>

    Examples:

        pytest.tests_failed
        coverage.coverage_percent
        security.high_findings
    """

    threshold_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        ),
    ]
    metric: Annotated[
        str,
        Field(
            min_length=3,
            max_length=256,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*\.[A-Za-z0-9._:-]+$",
        ),
    ]
    operator: ComparisonOperator
    expected_value: float
    failure_decision: GateDecision
    missing_metric_action: MissingMetricAction
    description: Annotated[str, Field(min_length=1, max_length=4_000)]

    @model_validator(mode="after")
    def validate_decisions(self) -> Self:
        if self.failure_decision == GateDecision.PASS:
            raise ValueError(
                "A failed metric threshold cannot produce PASS."
            )
        if self.failure_decision == GateDecision.MORE_EVIDENCE_REQUIRED:
            # A metric that exists and violates its threshold is normally adverse
            # evidence, not missing evidence. MORE_EVIDENCE_REQUIRED is still
            # allowed, but developers should use it only for sufficiency metrics.
            pass
        return self


class ReleasePolicy(GateModel):
    """
    Deterministic release-decision policy.

    Decision precedence is fixed and documented:

        FAIL
        > HUMAN_REVIEW_REQUIRED
        > MORE_EVIDENCE_REQUIRED
        > PASS

    The precedence cannot be overridden by YAML. This prevents a configuration
    error from allowing a lower-severity result to mask a dominant failure.
    """

    version: Annotated[
        str,
        Field(
            pattern=(
                r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
            )
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
    fail_on_mandatory_control_failure: bool = True
    fail_on_dominant_failure: bool = True
    human_review_on_advisory_failure: bool = True
    human_review_on_warning: bool = True
    more_evidence_on_skipped_mandatory_control: bool = True
    more_evidence_on_missing_required_report: bool = True
    metric_thresholds: list[MetricThreshold] = Field(
        default_factory=list,
        max_length=1_000,
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("metric_thresholds")
    @classmethod
    def reject_duplicate_threshold_ids(
        cls,
        value: list[MetricThreshold],
    ) -> list[MetricThreshold]:
        identifiers = [item.threshold_id for item in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(
                "metric_thresholds must not contain duplicate threshold IDs."
            )
        return value


class GateRuntimeSettings(GateModel):
    """Local runtime configuration for the deterministic gate."""

    artifact_root: Path
    git_executable: Annotated[str, Field(min_length=1, max_length=1_024)] = "git"
    maximum_captured_output_bytes: Annotated[
        int,
        Field(ge=1_024, le=50_000_000),
    ] = 1_000_000
    preserve_successful_workspace: bool = False
    preserve_failed_workspace: bool = False

    @field_validator("artifact_root")
    @classmethod
    def normalize_artifact_root(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @classmethod
    def from_yaml(cls, path: Path) -> "GateRuntimeSettings":
        return _load_yaml_model(path, cls)


class DeterministicGateExecutionRequest(GateModel):
    """
    Complete input to the deterministic release gate.

    ``candidate_patch`` is required because Component 2 does not push its local
    candidate commit. The patch must be the immutable patch artifact returned in
    ExecutionResult.

    Candidate-patch metadata must include:

        base_commit
        candidate_commit
        executor_version

    The service verifies the first two against GateRequest.
    """

    gate_request: GateRequest
    candidate_patch: ArtifactReference

    @model_validator(mode="after")
    def validate_candidate_patch(self) -> Self:
        if self.candidate_patch.kind != ArtifactKind.PATCH:
            raise ValueError(
                "candidate_patch must have ArtifactKind.PATCH."
            )
        if not self.candidate_patch.immutable:
            raise ValueError("candidate_patch must be immutable.")
        if self.candidate_patch.sha256 is None:
            raise ValueError("candidate_patch must include a SHA-256 digest.")
        recorded_base = self.candidate_patch.metadata.get("base_commit")
        recorded_candidate = self.candidate_patch.metadata.get("candidate_commit")
        if recorded_base is None:
            raise ValueError(
                "candidate_patch metadata must include base_commit."
            )
        if recorded_candidate is None:
            raise ValueError(
                "candidate_patch metadata must include candidate_commit."
            )
        if recorded_base.lower() != self.gate_request.base_commit.lower():
            raise ValueError(
                "candidate_patch base_commit metadata does not match GateRequest."
            )
        if recorded_candidate.lower() != self.gate_request.candidate_commit.lower():
            raise ValueError(
                "candidate_patch candidate_commit metadata does not match GateRequest."
            )
        return self


def _load_yaml_model(path: Path, model_type: type[GateModel]) -> Any:
    """Read and validate a strict YAML configuration model."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(
            f"Unable to read YAML document {path}: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"YAML document {path} is invalid: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise ConfigurationError(
            f"YAML document {path} must contain a mapping."
        )
    try:
        return model_type.model_validate(raw)
    except Exception as exc:
        raise ConfigurationError(
            f"YAML document {path} failed validation: {exc}"
        ) from exc


def load_requirement_contract(path: Path) -> RequirementContract:
    return _load_yaml_model(path, RequirementContract)


def load_evaluation_specification(path: Path) -> EvaluationSpecification:
    return _load_yaml_model(path, EvaluationSpecification)


def load_release_policy(path: Path) -> ReleasePolicy:
    return _load_yaml_model(path, ReleasePolicy)
