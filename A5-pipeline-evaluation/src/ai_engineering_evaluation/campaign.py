"""
Evaluation campaign orchestration.

This module deliberately depends on a narrow PipelineAdapter rather than
directly importing the internal implementation of Components 2 and 3.

Why?

Because Component 5 should evaluate the same external behavior regardless of
whether the online pipeline is:

    local Python
    Azure Container Apps
    Azure Pipelines
    another isolated execution environment

The adapter boundary also makes testing straightforward.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from uuid import uuid4

from .benchmark import BenchmarkFactory
from .grading import DeterministicOracleGrader
from .metrics import CampaignMetricsCalculator
from .models import (
    CampaignReport,
    CaseEvaluationResult,
    GateOutcome,
    OracleOutcome,
    QualificationSettings,
    ValidatedGoldenBenchmark,
)
from .readiness import ReadinessEvaluator


class PipelineCaseExecution:
    """
    Result returned by the online pipeline adapter.

    The adapter is responsible for invoking Components 2–4 and returning the
    candidate workspace required by the offline oracle grader.
    """

    def __init__(
        self,
        *,
        gate_outcome: GateOutcome,
        candidate_workspace: Path | None,
        run_id: str | None,
        manifest_sha256: str | None,
        llm_calls: int,
        input_tokens: int,
        output_tokens: int,
        estimated_cost: float,
        failure_category: str | None = None,
    ) -> None:
        self.gate_outcome = gate_outcome
        self.candidate_workspace = candidate_workspace
        self.run_id = run_id
        self.manifest_sha256 = manifest_sha256
        self.llm_calls = llm_calls
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.estimated_cost = estimated_cost
        self.failure_category = failure_category


class PipelineAdapter(ABC):
    """
    Boundary between offline qualification and the online engineering system.

    There is intentionally no fake default implementation.

    The concrete deployment must supply the adapter that invokes Components
    2–4.

    Failing explicitly is safer than silently evaluating a mock pipeline.
    """

    @abstractmethod
    def execute_case(
        self,
        *,
        case_id: str,
        task_payload_uri: str,
        starting_repository_uri: str,
        starting_commit: str,
    ) -> PipelineCaseExecution:
        raise NotImplementedError(
            "A concrete PipelineAdapter must invoke the deployed "
            "Components 2–4."
        )


class EvaluationCampaignRunner:
    """
    Execute benchmark cases and construct one campaign-level report.

    Hidden oracles are loaded only AFTER online execution.

    They are never passed through PipelineAdapter.
    """

    RUNNER_VERSION = "0.1.0"

    def __init__(
        self,
        *,
        pipeline: PipelineAdapter,
        benchmark_factory: BenchmarkFactory,
        grader: DeterministicOracleGrader,
        metrics: CampaignMetricsCalculator,
        readiness: ReadinessEvaluator,
    ) -> None:
        self._pipeline = pipeline
        self._benchmark_factory = benchmark_factory
        self._grader = grader
        self._metrics = metrics
        self._readiness = readiness

    def run(
        self,
        *,
        benchmark: ValidatedGoldenBenchmark,
        settings: QualificationSettings,
        campaign_id: str | None = None,
    ) -> CampaignReport:
        if not benchmark.validated:
            raise ValueError(
                "Evaluation campaigns require a validated benchmark."
            )

        campaign_id = campaign_id or f"campaign-{uuid4()}"

        started_at = datetime.now(timezone.utc)

        results: list[CaseEvaluationResult] = []

        for case in benchmark.cases:
            case_start = monotonic()

            try:
                execution = self._pipeline.execute_case(
                    case_id=case.case_id,
                    task_payload_uri=case.task_payload_uri,
                    starting_repository_uri=case.starting_repository_uri,
                    starting_commit=case.starting_commit,
                )
            except Exception as exc:
                results.append(
                    CaseEvaluationResult(
                        case_id=case.case_id,
                        task_type=case.task_type,
                        difficulty=case.difficulty,
                        gate_outcome=GateOutcome.PIPELINE_ERROR,
                        oracle_outcome=OracleOutcome.UNGRADABLE,
                        execution_seconds=monotonic() - case_start,
                        failure_category="pipeline_adapter_exception",
                        grading_notes=(
                            f"{type(exc).__name__}: {exc}",
                        ),
                    )
                )
                continue

            if execution.candidate_workspace is None:
                results.append(
                    CaseEvaluationResult(
                        case_id=case.case_id,
                        task_type=case.task_type,
                        difficulty=case.difficulty,
                        gate_outcome=execution.gate_outcome,
                        oracle_outcome=OracleOutcome.UNGRADABLE,
                        run_id=execution.run_id,
                        manifest_sha256=execution.manifest_sha256,
                        execution_seconds=monotonic() - case_start,
                        llm_calls=execution.llm_calls,
                        input_tokens=execution.input_tokens,
                        output_tokens=execution.output_tokens,
                        estimated_cost=execution.estimated_cost,
                        failure_category=(
                            execution.failure_category
                            or "candidate_workspace_missing"
                        ),
                        grading_notes=(
                            "Pipeline produced no candidate workspace "
                            "for independent oracle grading.",
                        ),
                    )
                )
                continue

            try:
                # IMPORTANT:
                #
                # Only now do we access the hidden oracle.
                #
                # The online system has already completed its work.
                oracle = self._benchmark_factory.load_oracle(case)

                grade = self._grader.grade(
                    workspace=execution.candidate_workspace,
                    oracle=oracle,
                )

                oracle_outcome = grade.outcome
                grading_notes = grade.notes

            except Exception as exc:
                oracle_outcome = OracleOutcome.UNGRADABLE
                grading_notes = (
                    f"Oracle grading failed: "
                    f"{type(exc).__name__}: {exc}",
                )

            results.append(
                CaseEvaluationResult(
                    case_id=case.case_id,
                    task_type=case.task_type,
                    difficulty=case.difficulty,
                    gate_outcome=execution.gate_outcome,
                    oracle_outcome=oracle_outcome,
                    run_id=execution.run_id,
                    manifest_sha256=execution.manifest_sha256,
                    execution_seconds=monotonic() - case_start,
                    llm_calls=execution.llm_calls,
                    input_tokens=execution.input_tokens,
                    output_tokens=execution.output_tokens,
                    estimated_cost=execution.estimated_cost,
                    failure_category=execution.failure_category,
                    grading_notes=grading_notes,
                )
            )

        result_tuple = tuple(results)

        campaign_metrics = self._metrics.calculate(
            result_tuple,
            confidence_level=settings.confidence_level,
        )

        readiness_decision = self._readiness.evaluate(
            metrics=campaign_metrics,
            policy=settings.policy,
        )

        completed_at = datetime.now(timezone.utc)

        return CampaignReport(
            campaign_id=campaign_id,
            benchmark_id=benchmark.benchmark_id,
            benchmark_version=benchmark.benchmark_version,
            started_at=started_at,
            completed_at=completed_at,
            case_results=result_tuple,
            metrics=campaign_metrics,
            readiness=readiness_decision,
        )
