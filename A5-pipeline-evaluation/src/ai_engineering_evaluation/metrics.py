"""
Campaign-level metrics.

This module converts individual benchmark observations into system-level
measurements.

We distinguish two different kinds of correctness:

1. CODE CORRECTNESS

   Did the candidate satisfy the hidden oracle?

2. RELEASE-DECISION CORRECTNESS

   Did the gate make an appropriate decision given actual candidate
   correctness?

This distinction is critical.

A coding agent can fail while the gate correctly blocks the candidate.

Conversely, the coding agent can fail and the gate can incorrectly release it.

The latter is much more concerning for autonomous operation.
"""

from __future__ import annotations

from statistics import mean

from .models import (
    CampaignMetrics,
    CaseEvaluationResult,
    GateOutcome,
    OracleOutcome,
)
from .statistics import StatisticalAnalyzer


class CampaignMetricsCalculator:
    def __init__(
        self,
        statistical_analyzer: StatisticalAnalyzer,
    ) -> None:
        self._statistics = statistical_analyzer

    def calculate(
        self,
        results: tuple[CaseEvaluationResult, ...],
        *,
        confidence_level: float,
    ) -> CampaignMetrics:
        total = len(results)

        gradable = [
            result
            for result in results
            if result.oracle_outcome != OracleOutcome.UNGRADABLE
        ]

        correct = [
            result
            for result in gradable
            if result.oracle_outcome == OracleOutcome.CORRECT
        ]

        incorrect = [
            result
            for result in gradable
            if result.oracle_outcome == OracleOutcome.INCORRECT
        ]

        released = [
            result
            for result in results
            if result.gate_outcome == GateOutcome.PASS
        ]

        rejected = [
            result
            for result in results
            if result.gate_outcome == GateOutcome.FAIL
        ]

        review = [
            result
            for result in results
            if result.gate_outcome == GateOutcome.HUMAN_REVIEW_REQUIRED
        ]

        more_evidence = [
            result
            for result in results
            if result.gate_outcome == GateOutcome.MORE_EVIDENCE_REQUIRED
        ]

        pipeline_errors = [
            result
            for result in results
            if result.gate_outcome == GateOutcome.PIPELINE_ERROR
        ]

        false_releases = [
            result
            for result in gradable
            if (
                result.gate_outcome == GateOutcome.PASS
                and result.oracle_outcome == OracleOutcome.INCORRECT
            )
        ]

        false_rejections = [
            result
            for result in gradable
            if (
                result.gate_outcome == GateOutcome.FAIL
                and result.oracle_outcome == OracleOutcome.CORRECT
            )
        ]

        # Safe release asks:
        #
        #   Of candidates actually released, how many were correct?
        #
        # It is different from overall task success.
        released_gradable = [
            result
            for result in released
            if result.oracle_outcome != OracleOutcome.UNGRADABLE
        ]

        safe_releases = [
            result
            for result in released_gradable
            if result.oracle_outcome == OracleOutcome.CORRECT
        ]

        task_success = self._statistics.proportion(
            successes=len(correct),
            trials=len(gradable),
            confidence_level=confidence_level,
        )

        safe_release = self._statistics.proportion(
            successes=len(safe_releases),
            trials=len(released_gradable),
            confidence_level=confidence_level,
        )

        false_release_rate = self._statistics.proportion(
            successes=len(false_releases),
            trials=len(released_gradable),
            confidence_level=confidence_level,
        )

        # False rejection is measured against candidates that the oracle says
        # were actually correct.
        false_rejection_rate = self._statistics.proportion(
            successes=len(false_rejections),
            trials=len(correct),
            confidence_level=confidence_level,
        )

        return CampaignMetrics(
            total_cases=total,
            gradable_cases=len(gradable),
            correct_cases=len(correct),
            incorrect_cases=len(incorrect),
            ungradable_cases=total - len(gradable),
            released_cases=len(released),
            rejected_cases=len(rejected),
            review_cases=len(review),
            more_evidence_cases=len(more_evidence),
            pipeline_errors=len(pipeline_errors),
            false_releases=len(false_releases),
            false_rejections=len(false_rejections),
            task_success=task_success,
            safe_release=safe_release,
            false_release_rate=false_release_rate,
            false_rejection_rate=false_rejection_rate,
            total_llm_calls=sum(
                result.llm_calls
                for result in results
            ),
            total_input_tokens=sum(
                result.input_tokens
                for result in results
            ),
            total_output_tokens=sum(
                result.output_tokens
                for result in results
            ),
            total_estimated_cost=sum(
                result.estimated_cost
                for result in results
            ),
            mean_execution_seconds=(
                mean(
                    result.execution_seconds
                    for result in results
                )
                if results
                else 0.0
            ),
        )
