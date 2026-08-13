"""
Evaluation-specific contracts for Component 5.

These contracts describe experiments and observations.

They deliberately distinguish:

    PUBLIC TASK INFORMATION

from

    HIDDEN EVALUATION INFORMATION.

That distinction is one of the most important trust boundaries in the
repository.

Junior engineers extending these classes should resist adding hidden fields
to PublicTaskPackage merely because doing so simplifies an evaluation.

If the online pipeline can see the answer, the benchmark is no longer
measuring the capability we think it is measuring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Mapping


def utc_now() -> datetime:
    """
    Return a timezone-aware UTC timestamp.

    Evaluation evidence frequently comes from multiple processes and
    execution environments. Naive timestamps make ordering and correlation
    unnecessarily ambiguous.
    """

    return datetime.now(timezone.utc)


class GateOutcome(StrEnum):
    """
    Canonical gate outcomes used by B5.

    During repository reconciliation this enum should be imported directly
    from B1 if B1 already defines GateOutcome.
    """

    PASS = "pass"
    FAIL = "fail"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class OracleAcceptability(StrEnum):
    """
    Hidden ground-truth judgement for a candidate.

    ACCEPTABLE
        Candidate satisfies the benchmark's hidden acceptance criteria.

    UNACCEPTABLE
        Candidate violates at least one decisive hidden criterion.

    ORACLE_ERROR
        The benchmark environment could not produce a trustworthy judgement.

    ORACLE_ERROR is deliberately NOT interpreted as UNACCEPTABLE.

    A broken evaluator is an evaluation-system problem, not evidence that
    the candidate itself is wrong.
    """

    ACCEPTABLE = "acceptable"
    UNACCEPTABLE = "unacceptable"
    ORACLE_ERROR = "oracle_error"


class DecisionClassification(StrEnum):
    """
    Relationship between the online gate decision and hidden truth.

    CORRECT_PASS
        Gate passed a candidate that the hidden oracle accepts.

    FALSE_RELEASE
        Gate passed a candidate that the hidden oracle rejects.

        This is a particularly important failure because the online system
        would have permitted an unacceptable candidate to progress.

    CORRECT_REJECTION
        Gate failed an unacceptable candidate.

    FALSE_REJECTION
        Gate failed a candidate that the hidden oracle considers acceptable.

    CORRECT_REVIEW
        Gate abstained / requested human review.

        B5 reports this separately rather than forcing abstention into a
        binary correct/incorrect classification.

    ORACLE_ERROR
        Hidden evaluation did not produce a trustworthy truth label.
    """

    CORRECT_PASS = "correct_pass"
    FALSE_RELEASE = "false_release"
    CORRECT_REJECTION = "correct_rejection"
    FALSE_REJECTION = "false_rejection"
    REVIEW_REQUIRED = "review_required"
    ORACLE_ERROR = "oracle_error"


@dataclass(frozen=True, slots=True)
class PublicTaskPackage:
    """
    Information legitimately available to the ONLINE automation pipeline.

    The object must never contain:

        hidden tests
        expected candidate
        reference patch
        known defect label
        expected gate result
        hidden acceptance properties
    """

    case_id: str
    task_type: str
    repository_id: str
    baseline_revision: str
    instruction: str
    public_metadata: Mapping[str, str] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """
    Public identity of one validated benchmark case.

    The actual hidden oracle is deliberately stored separately.

    `benchmark_case_version` allows the same logical case to be corrected or
    strengthened without silently rewriting historical campaign results.
    """

    public_task: PublicTaskPackage
    benchmark_case_version: str


@dataclass(frozen=True, slots=True)
class PipelineCandidate:
    """
    Minimal candidate information required by Component 5.

    In the integrated repository, this should normally adapt/import the
    canonical B1 CandidateArtifact rather than introduce a second candidate
    model.

    The evaluation layer needs immutable candidate identity because hidden
    oracle results and gate decisions must refer to the exact same artifact.
    """

    candidate_id: str
    candidate_sha256: str
    content: str


@dataclass(frozen=True, slots=True)
class PipelineRunObservation:
    """
    Observable result returned by the ONLINE pipeline to Component 5.

    IMPORTANT:

    This object contains only information that the online system legitimately
    produced.

    There is no oracle label here.
    """

    run_id: str
    case_id: str
    candidate: PipelineCandidate
    gate_outcome: GateOutcome
    gate_decision_id: str
    gate_reason_codes: tuple[str, ...]

    input_tokens: int = 0
    output_tokens: int = 0
    model_calls: int = 0

    wall_time_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class OracleAssessment:
    """
    Hidden assessment of an exact candidate.

    The assessment is created AFTER the online pipeline has produced its
    candidate and gate decision.
    """

    case_id: str
    candidate_id: str
    candidate_sha256: str
    acceptability: OracleAcceptability
    passed_hidden_checks: int
    failed_hidden_checks: int
    reason_codes: tuple[str, ...]
    oracle_version: str


@dataclass(frozen=True, slots=True)
class CaseEvaluationResult:
    """
    Complete evaluation result for one benchmark case and one pipeline run.

    This object joins:

        public case
        online observation
        hidden assessment
        derived classification

    only inside Component 5.
    """

    campaign_id: str
    case_id: str
    case_version: str

    run_id: str
    run_index: int

    candidate_id: str
    candidate_sha256: str

    gate_outcome: GateOutcome
    oracle_acceptability: OracleAcceptability

    classification: DecisionClassification

    gate_reason_codes: tuple[str, ...]
    oracle_reason_codes: tuple[str, ...]

    input_tokens: int
    output_tokens: int
    model_calls: int

    wall_time_seconds: float

    evaluated_at: datetime = field(
        default_factory=utc_now
    )


@dataclass(frozen=True, slots=True)
class CampaignConfiguration:
    """
    Frozen configuration for one evaluation campaign.

    Repeated runs can help estimate stochastic variability, but repeated runs
    of the same benchmark case are NOT automatically treated as independent
    new benchmark cases.

    B5 therefore stores `runs_per_case` explicitly.
    """

    campaign_id: str
    benchmark_id: str
    benchmark_version: str

    capability_id: str
    capability_version: str

    runs_per_case: int = 1

    confidence_level: float = 0.95

    def __post_init__(self) -> None:
        if not self.campaign_id.strip():
            raise ValueError(
                "campaign_id must be non-empty."
            )

        if self.runs_per_case < 1:
            raise ValueError(
                "runs_per_case must be at least 1."
            )

        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError(
                "confidence_level must be strictly between 0 and 1."
            )


@dataclass(frozen=True, slots=True)
class ProportionEstimate:
    """
    One proportion plus an uncertainty interval.

    `numerator` and `denominator` remain visible deliberately.

    Reporting:

        false release = 2%

    without the underlying counts can create a misleading impression of
    precision.
    """

    numerator: int
    denominator: int

    estimate: float | None

    lower_bound: float | None
    upper_bound: float | None

    confidence_level: float

    method: str


@dataclass(frozen=True, slots=True)
class CampaignMetrics:
    """
    Aggregate campaign metrics.

    IMPORTANT:

    These metrics describe observed benchmark performance.

    They are NOT automatically estimates of performance on all real L1 work.

    External validity depends on benchmark representativeness.
    """

    total_case_runs: int
    oracle_valid_case_runs: int

    correct_passes: int
    false_releases: int

    correct_rejections: int
    false_rejections: int

    human_reviews: int
    oracle_errors: int

    automated_decisions: int
    automated_passes: int

    automation_coverage: ProportionEstimate
    false_release_per_total: ProportionEstimate
    false_release_given_pass: ProportionEstimate
    false_rejection_per_total: ProportionEstimate
    human_review_rate: ProportionEstimate

    total_input_tokens: int
    total_output_tokens: int
    total_model_calls: int

    total_wall_time_seconds: float


@dataclass(frozen=True, slots=True)
class CampaignReport:
    """
    Immutable result of one completed evaluation campaign.
    """

    configuration: CampaignConfiguration
    case_results: tuple[CaseEvaluationResult, ...]
    metrics: CampaignMetrics

    started_at: datetime
    completed_at: datetime

