"""
EvaluationCampaignRunner — Component 5 application service.

This is the core B5 class.

Its role is intentionally narrow:

    1. iterate validated benchmark cases;
    2. expose only PUBLIC task data to the online pipeline;
    3. collect the online candidate and gate result;
    4. ask the HIDDEN oracle to assess that exact candidate;
    5. classify the relationship between gate and hidden truth;
    6. preserve case-level results;
    7. calculate aggregate metrics.

The campaign runner does NOT:

    - help ChangeExecutionService solve the task;
    - provide hidden tests to ReleaseGateService;
    - change a candidate after seeing the oracle;
    - retry until the benchmark passes;
    - alter gate thresholds based on qualification results;
    - declare production approval.

Those would contaminate the experiment.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from time import perf_counter

from .contracts import (
    BenchmarkCase,
    CampaignConfiguration,
    CampaignReport,
    CaseEvaluationResult,
    DecisionClassification,
    GateOutcome,
    OracleAcceptability,
    PipelineRunObservation,
    PublicTaskPackage,
)

from .metrics import build_campaign_metrics
from .oracle import HiddenOraclePort


class OnlinePipelinePort(ABC):
    """
    Boundary through which Component 5 invokes the real ONLINE pipeline.

    A production adapter should invoke:

        Component 9 orchestration

    which in turn uses:

        Component 11 capability resolution
        Component 2 ChangeExecutionService
        Component 3 ReleaseGateService
        Component 4 evidence persistence
        Component 10 execution environment

    Component 5 should not reimplement those services.
    """

    @abstractmethod
    def execute(
        self,
        *,
        public_task: PublicTaskPackage,
        run_index: int,
    ) -> PipelineRunObservation:
        """
        Execute one online pipeline attempt.

        The implementation MUST NOT receive HiddenOraclePort.
        """
        raise NotImplementedError


def classify_gate_against_oracle(
    *,
    gate_outcome: GateOutcome,
    oracle_acceptability: OracleAcceptability,
) -> DecisionClassification:
    """
    Deterministically classify one gate decision against hidden truth.

    The function intentionally has no AI dependency.

    HUMAN_REVIEW_REQUIRED remains an abstention/review outcome rather than
    being coerced into PASS or FAIL.
    """

    if (
        oracle_acceptability
        == OracleAcceptability.ORACLE_ERROR
    ):
        return DecisionClassification.ORACLE_ERROR

    if gate_outcome == GateOutcome.HUMAN_REVIEW_REQUIRED:
        return DecisionClassification.REVIEW_REQUIRED

    if (
        gate_outcome == GateOutcome.PASS
        and oracle_acceptability
        == OracleAcceptability.ACCEPTABLE
    ):
        return DecisionClassification.CORRECT_PASS

    if (
        gate_outcome == GateOutcome.PASS
        and oracle_acceptability
        == OracleAcceptability.UNACCEPTABLE
    ):
        return DecisionClassification.FALSE_RELEASE

    if (
        gate_outcome == GateOutcome.FAIL
        and oracle_acceptability
        == OracleAcceptability.UNACCEPTABLE
    ):
        return DecisionClassification.CORRECT_REJECTION

    if (
        gate_outcome == GateOutcome.FAIL
        and oracle_acceptability
        == OracleAcceptability.ACCEPTABLE
    ):
        return DecisionClassification.FALSE_REJECTION

    # GateOutcome and OracleAcceptability are enums, so reaching this branch
    # indicates that one of them was expanded without updating classification
    # semantics.
    raise RuntimeError(
        "Unhandled gate/oracle combination. "
        "Update deterministic evaluation semantics."
    )


class EvaluationCampaignRunner:
    """
    Execute one immutable evaluation campaign.

    The online pipeline and hidden oracle are separate constructor
    dependencies.

    This is intentional and testable.
    """

    def __init__(
        self,
        *,
        online_pipeline: OnlinePipelinePort,
        hidden_oracle: HiddenOraclePort,
    ) -> None:
        self._online_pipeline = online_pipeline
        self._hidden_oracle = hidden_oracle

    def run(
        self,
        *,
        configuration: CampaignConfiguration,
        benchmark_cases: tuple[BenchmarkCase, ...],
    ) -> CampaignReport:
        """
        Execute the complete campaign.

        A benchmark with zero cases fails explicitly.

        Producing an attractive report from an empty benchmark would be
        meaningless.
        """

        if not benchmark_cases:
            raise ValueError(
                "Evaluation campaign requires at least one benchmark case."
            )

        self._validate_case_identity(
            benchmark_cases
        )

        started_at = datetime.now(
            timezone.utc
        )

        case_results: list[
            CaseEvaluationResult
        ] = []

        for benchmark_case in benchmark_cases:

            for run_index in range(
                configuration.runs_per_case
            ):

                run_start = perf_counter()

                observation = (
                    self._online_pipeline.execute(
                        public_task=(
                            benchmark_case.public_task
                        ),
                        run_index=run_index,
                    )
                )

                elapsed = (
                    perf_counter()
                    - run_start
                )

                self._validate_observation_identity(
                    benchmark_case=benchmark_case,
                    observation=observation,
                )

                assessment = (
                    self._hidden_oracle.assess(
                        benchmark_case=benchmark_case,
                        candidate=observation.candidate,
                    )
                )

                self._validate_oracle_binding(
                    observation=observation,
                    assessment=assessment,
                )

                classification = (
                    classify_gate_against_oracle(
                        gate_outcome=(
                            observation.gate_outcome
                        ),
                        oracle_acceptability=(
                            assessment.acceptability
                        ),
                    )
                )

                # Prefer latency reported by the actual pipeline when
                # available. The local elapsed timer is a defensive fallback.
                #
                # In a distributed production campaign, wall time should be
                # obtained from authoritative run telemetry rather than
                # process-local timing alone.

                wall_time = (
                    observation.wall_time_seconds
                    if observation.wall_time_seconds > 0.0
                    else elapsed
                )

                case_results.append(
                    CaseEvaluationResult(
                        campaign_id=(
                            configuration.campaign_id
                        ),
                        case_id=(
                            benchmark_case.public_task.case_id
                        ),
                        case_version=(
                            benchmark_case
                            .benchmark_case_version
                        ),
                        run_id=observation.run_id,
                        run_index=run_index,
                        candidate_id=(
                            observation
                            .candidate
                            .candidate_id
                        ),
                        candidate_sha256=(
                            observation
                            .candidate
                            .candidate_sha256
                        ),
                        gate_outcome=(
                            observation.gate_outcome
                        ),
                        oracle_acceptability=(
                            assessment.acceptability
                        ),
                        classification=classification,
                        gate_reason_codes=(
                            observation.gate_reason_codes
                        ),
                        oracle_reason_codes=(
                            assessment.reason_codes
                        ),
                        input_tokens=(
                            observation.input_tokens
                        ),
                        output_tokens=(
                            observation.output_tokens
                        ),
                        model_calls=(
                            observation.model_calls
                        ),
                        wall_time_seconds=wall_time,
                    )
                )

        frozen_results = tuple(
            case_results
        )

        metrics = build_campaign_metrics(
            results=frozen_results,
            confidence_level=(
                configuration.confidence_level
            ),
        )

        completed_at = datetime.now(
            timezone.utc
        )

        return CampaignReport(
            configuration=configuration,
            case_results=frozen_results,
            metrics=metrics,
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _validate_case_identity(
        benchmark_cases: tuple[BenchmarkCase, ...],
    ) -> None:
        """
        Prevent duplicate benchmark case IDs inside one campaign.

        Duplicate cases would silently overweight a task in aggregate metrics.
        If intentional weighting is ever introduced, it should be explicit
        rather than achieved through accidental duplication.
        """

        case_ids = [
            case.public_task.case_id
            for case in benchmark_cases
        ]

        if len(case_ids) != len(set(case_ids)):
            raise ValueError(
                "Duplicate benchmark case IDs are not permitted "
                "within one campaign."
            )

    @staticmethod
    def _validate_observation_identity(
        *,
        benchmark_case: BenchmarkCase,
        observation: PipelineRunObservation,
    ) -> None:
        """
        Ensure the online result belongs to the requested benchmark case.
        """

        expected = (
            benchmark_case.public_task.case_id
        )

        if observation.case_id != expected:
            raise ValueError(
                "Online pipeline returned an observation for the wrong "
                f"benchmark case: expected={expected!r}, "
                f"actual={observation.case_id!r}."
            )

    @staticmethod
    def _validate_oracle_binding(
        *,
        observation: PipelineRunObservation,
        assessment,
    ) -> None:
        """
        Ensure oracle truth refers to the EXACT candidate that was gated.

        This protects against accidental evaluation of:

            Candidate C2

        while recording the gate outcome for:

            Candidate C1.
        """

        candidate = observation.candidate

        if assessment.candidate_id != candidate.candidate_id:
            raise ValueError(
                "Oracle assessment candidate_id does not match the "
                "online candidate."
            )

        if (
            assessment.candidate_sha256
            != candidate.candidate_sha256
        ):
            raise ValueError(
                "Oracle assessment candidate hash does not match the "
                "online candidate."
            )

