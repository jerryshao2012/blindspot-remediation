"""
Deterministic campaign metric calculation.

This module should contain NO LLM calls.

Once Component 5 has:

    gate decision
    +
    hidden oracle assessment

classification and aggregation are ordinary deterministic analytics.

Keeping this layer deterministic makes metric definitions reviewable and
reproducible.
"""

from __future__ import annotations

from .contracts import (
    CampaignMetrics,
    CaseEvaluationResult,
    DecisionClassification,
)

from .statistics import wilson_interval


def build_campaign_metrics(
    *,
    results: tuple[CaseEvaluationResult, ...],
    confidence_level: float,
) -> CampaignMetrics:
    """
    Aggregate case/run-level observations into campaign metrics.

    IMPORTANT DENOMINATOR DISCIPLINE
    --------------------------------

    B5 reports two false-release quantities:

    1. false_release_per_total

       false releases
       -----------------------------
       all oracle-valid case runs


    2. false_release_given_pass

       false releases
       -----------------------------
       automated PASS decisions


    These answer different questions.

    The second is especially relevant when asking:

        "When the system autonomously says PASS, how frequently was
         that decision wrong on this benchmark?"

    Neither should be reported without its numerator and denominator.
    """

    total_case_runs = len(results)

    oracle_valid = tuple(
        result
        for result in results
        if (
            result.classification
            != DecisionClassification.ORACLE_ERROR
        )
    )

    oracle_valid_count = len(oracle_valid)

    correct_passes = sum(
        result.classification
        == DecisionClassification.CORRECT_PASS
        for result in oracle_valid
    )

    false_releases = sum(
        result.classification
        == DecisionClassification.FALSE_RELEASE
        for result in oracle_valid
    )

    correct_rejections = sum(
        result.classification
        == DecisionClassification.CORRECT_REJECTION
        for result in oracle_valid
    )

    false_rejections = sum(
        result.classification
        == DecisionClassification.FALSE_REJECTION
        for result in oracle_valid
    )

    human_reviews = sum(
        result.classification
        == DecisionClassification.REVIEW_REQUIRED
        for result in oracle_valid
    )

    oracle_errors = (
        total_case_runs
        - oracle_valid_count
    )

    automated_decisions = (
        correct_passes
        + false_releases
        + correct_rejections
        + false_rejections
    )

    automated_passes = (
        correct_passes
        + false_releases
    )

    return CampaignMetrics(
        total_case_runs=total_case_runs,
        oracle_valid_case_runs=oracle_valid_count,
        correct_passes=correct_passes,
        false_releases=false_releases,
        correct_rejections=correct_rejections,
        false_rejections=false_rejections,
        human_reviews=human_reviews,
        oracle_errors=oracle_errors,
        automated_decisions=automated_decisions,
        automated_passes=automated_passes,

        automation_coverage=wilson_interval(
            successes=automated_decisions,
            trials=oracle_valid_count,
            confidence_level=confidence_level,
        ),

        false_release_per_total=wilson_interval(
            successes=false_releases,
            trials=oracle_valid_count,
            confidence_level=confidence_level,
        ),

        false_release_given_pass=wilson_interval(
            successes=false_releases,
            trials=automated_passes,
            confidence_level=confidence_level,
        ),

        false_rejection_per_total=wilson_interval(
            successes=false_rejections,
            trials=oracle_valid_count,
            confidence_level=confidence_level,
        ),

        human_review_rate=wilson_interval(
            successes=human_reviews,
            trials=oracle_valid_count,
            confidence_level=confidence_level,
        ),

        total_input_tokens=sum(
            result.input_tokens
            for result in results
        ),

        total_output_tokens=sum(
            result.output_tokens
            for result in results
        ),

        total_model_calls=sum(
            result.model_calls
            for result in results
        ),

        total_wall_time_seconds=sum(
            result.wall_time_seconds
            for result in results
        ),
    )

