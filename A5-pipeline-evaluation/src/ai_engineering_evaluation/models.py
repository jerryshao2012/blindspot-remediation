"""
Data models for benchmark and campaign qualification.

The models are intentionally strict.

Benchmark evaluation is only meaningful when we know exactly:

    what case ran,
    what version ran,
    what task type it represents,
    what oracle defines correctness,
    what gate decision occurred,
    and what evidence supports the observation.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .errors import BenchmarkValidationError


class EvaluationModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class OracleType(StrEnum):
    """
    Deterministic grading mechanisms supported by the POC.

    COMMAND
        Run an executable grading command in an isolated benchmark
        environment.

    FILE_SHA256
        Verify that one or more expected files have exact known hashes.

    COMPOSITE
        Require both command and file-hash conditions.
    """

    COMMAND = "command"
    FILE_SHA256 = "file_sha256"
    COMPOSITE = "composite"


class ExpectedFile(EvaluationModel):
    relative_path: Annotated[
        str,
        Field(min_length=1, max_length=2_048),
    ]

    sha256: Annotated[
        str,
        Field(pattern=r"^[a-f0-9]{64}$"),
    ]

    @field_validator("relative_path")
    @classmethod
    def prohibit_absolute_paths(cls, value: str) -> str:
        path = Path(value)

        if path.is_absolute() or ".." in path.parts:
            raise ValueError(
                "Expected oracle file paths must remain inside the workspace."
            )

        return value


class HiddenOracle(EvaluationModel):
    """
    Ground truth withheld from the online automation.

    The oracle itself is deterministic.

    AI may be used during benchmark creation, but a generated benchmark does
    not become trusted ground truth merely because an LLM produced it.
    """

    oracle_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    oracle_version: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    oracle_type: OracleType

    command: list[
        Annotated[str, Field(min_length=1, max_length=4_096)]
    ] = Field(default_factory=list)

    expected_exit_code: int = 0

    expected_files: list[ExpectedFile] = Field(default_factory=list)

    timeout_seconds: Annotated[
        int,
        Field(ge=1, le=7_200),
    ] = 900

    @model_validator(mode="after")
    def validate_oracle(self) -> Self:
        if self.oracle_type in {OracleType.COMMAND, OracleType.COMPOSITE}:
            if not self.command:
                raise ValueError(
                    "Command-based oracle requires a command."
                )

        if self.oracle_type in {
            OracleType.FILE_SHA256,
            OracleType.COMPOSITE,
        }:
            if not self.expected_files:
                raise ValueError(
                    "File-based oracle requires expected files."
                )

        return self


class BenchmarkCase(EvaluationModel):
    """
    One independently gradable engineering problem.

    ``task_payload_uri`` contains information visible to the online pipeline.

    ``oracle_uri`` is deliberately separate and must never be passed to the
    online pipeline.
    """

    case_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$",
        ),
    ]

    task_type: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    difficulty: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    task_payload_uri: Annotated[
        str,
        Field(min_length=1, max_length=4_096),
    ]

    starting_repository_uri: Annotated[
        str,
        Field(min_length=1, max_length=4_096),
    ]

    starting_commit: Annotated[
        str,
        Field(pattern=r"^[0-9a-fA-F]{40}$"),
    ]

    oracle_uri: Annotated[
        str,
        Field(min_length=1, max_length=4_096),
    ]

    oracle_sha256: Annotated[
        str,
        Field(pattern=r"^[a-f0-9]{64}$"),
    ]

    tags: tuple[str, ...] = ()

    @field_validator("starting_commit")
    @classmethod
    def normalize_commit(cls, value: str) -> str:
        return value.lower()


class ValidatedGoldenBenchmark(EvaluationModel):
    benchmark_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    benchmark_version: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    created_at: datetime

    cases: tuple[BenchmarkCase, ...]

    validated: bool

    validation_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_cases(self) -> Self:
        if not self.cases:
            raise ValueError("Benchmark must contain at least one case.")

        ids = [case.case_id for case in self.cases]

        if len(ids) != len(set(ids)):
            raise ValueError("Benchmark contains duplicate case IDs.")

        if not self.validated:
            raise ValueError(
                "Only explicitly validated benchmarks may be executed."
            )

        return self


class GateOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"
    PIPELINE_ERROR = "pipeline_error"


class OracleOutcome(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNGRADABLE = "ungradable"


class CaseEvaluationResult(EvaluationModel):
    case_id: str
    task_type: str
    difficulty: str

    gate_outcome: GateOutcome
    oracle_outcome: OracleOutcome

    run_id: str | None = None
    manifest_sha256: str | None = None

    execution_seconds: Annotated[float, Field(ge=0.0)] = 0.0

    llm_calls: Annotated[int, Field(ge=0)] = 0
    input_tokens: Annotated[int, Field(ge=0)] = 0
    output_tokens: Annotated[int, Field(ge=0)] = 0
    estimated_cost: Annotated[float, Field(ge=0)] = 0.0

    failure_category: str | None = None
    grading_notes: tuple[str, ...] = ()


class ProportionEstimate(EvaluationModel):
    successes: Annotated[int, Field(ge=0)]
    trials: Annotated[int, Field(ge=0)]

    estimate: Annotated[float | None, Field(ge=0.0, le=1.0)]

    confidence_level: Annotated[
        float,
        Field(gt=0.0, lt=1.0),
    ]

    lower_bound: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    upper_bound: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]


class CampaignMetrics(EvaluationModel):
    total_cases: Annotated[int, Field(ge=0)]
    gradable_cases: Annotated[int, Field(ge=0)]

    correct_cases: Annotated[int, Field(ge=0)]
    incorrect_cases: Annotated[int, Field(ge=0)]
    ungradable_cases: Annotated[int, Field(ge=0)]

    released_cases: Annotated[int, Field(ge=0)]
    rejected_cases: Annotated[int, Field(ge=0)]
    review_cases: Annotated[int, Field(ge=0)]
    more_evidence_cases: Annotated[int, Field(ge=0)]
    pipeline_errors: Annotated[int, Field(ge=0)]

    false_releases: Annotated[int, Field(ge=0)]
    false_rejections: Annotated[int, Field(ge=0)]

    task_success: ProportionEstimate
    safe_release: ProportionEstimate
    false_release_rate: ProportionEstimate
    false_rejection_rate: ProportionEstimate

    total_llm_calls: Annotated[int, Field(ge=0)]
    total_input_tokens: Annotated[int, Field(ge=0)]
    total_output_tokens: Annotated[int, Field(ge=0)]
    total_estimated_cost: Annotated[float, Field(ge=0)]

    mean_execution_seconds: Annotated[float, Field(ge=0)]


class ReadinessStatus(StrEnum):
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ReadinessDecision(EvaluationModel):
    status: ReadinessStatus
    reasons: tuple[str, ...]
    policy_version: str


class QualificationPolicy(EvaluationModel):
    """
    Deterministic readiness policy.

    Thresholds are examples for a POC configuration, not universal engineering
    standards. The organization must calibrate them to task risk and expected
    human oversight.
    """

    policy_version: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    minimum_gradable_cases: Annotated[int, Field(ge=1)]

    minimum_task_success_lower_bound: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    minimum_safe_release_lower_bound: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    maximum_false_release_upper_bound: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    maximum_ungradable_fraction: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    maximum_pipeline_error_fraction: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]


class CampaignReport(EvaluationModel):
    campaign_id: str
    benchmark_id: str
    benchmark_version: str

    started_at: datetime
    completed_at: datetime

    case_results: tuple[CaseEvaluationResult, ...]

    metrics: CampaignMetrics

    readiness: ReadinessDecision


class QualificationSettings(EvaluationModel):
    confidence_level: Annotated[
        float,
        Field(gt=0.0, lt=1.0),
    ] = 0.95

    policy: QualificationPolicy

    @classmethod
    def from_yaml(cls, path: Path) -> "QualificationSettings":
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise BenchmarkValidationError(
                f"Unable to read qualification configuration: {exc}"
            ) from exc

        try:
            return cls.model_validate(raw)
        except Exception as exc:
            raise BenchmarkValidationError(
                f"Qualification configuration is invalid: {exc}"
            ) from exc
