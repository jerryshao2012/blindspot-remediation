"""
End-to-end SOFTWARE test of the B5 evaluation campaign.

This uses a deterministic fake online pipeline so that the evaluation
machinery itself can be tested with known outcomes.

The fake deliberately creates all important categories:

    correct PASS
    false release
    correct rejection
    human review

This lets us test the metrics before connecting the campaign runner to a
stochastic LLM pipeline.

When the real Component 2 + Component 3 stack is wired through
OnlinePipelinePort, the SAME EvaluationCampaignRunner can be used without
changing hidden-oracle logic or metric definitions.
"""

from __future__ import annotations

from hashlib import sha256

from l1_automation.evaluation.campaign_runner import (
    EvaluationCampaignRunner,
    OnlinePipelinePort,
)

from l1_automation.evaluation.contracts import (
    CampaignConfiguration,
    GateOutcome,
    PipelineCandidate,
    PipelineRunObservation,
    PublicTaskPackage,
)

from l1_automation.evaluation.oracle import (
    DeterministicHiddenX1Oracle,
)

from l1_automation.evaluation.synthetic_x1_benchmark import (
    BENCHMARK_ID,
    BENCHMARK_VERSION,
    X1_BENCHMARK_CASES,
    X1_HIDDEN_DEFINITIONS,
)


def _candidate(
    *,
    case_id: str,
    content: str,
) -> PipelineCandidate:

    digest = sha256(
        content.encode("utf-8")
    ).hexdigest()

    return PipelineCandidate(
        candidate_id=(
            f"candidate-{case_id}-{digest[:12]}"
        ),
        candidate_sha256=digest,
        content=content,
    )


class DeterministicCampaignPipeline(
    OnlinePipelinePort
):
    """
    Test double with deliberately known gate behavior.

    This object has NO access to the HiddenOraclePort.

    It receives only public task information.

    The outputs are hard-coded by public case ID because this is a software
    test of the campaign evaluator, not a capability evaluation.
    """

    def execute(
        self,
        *,
        public_task: PublicTaskPackage,
        run_index: int,
    ) -> PipelineRunObservation:

        case_id = public_task.case_id

        if case_id == "X1-001":

            candidate = _candidate(
                case_id=case_id,
                content=(
                    "def calculate(a, b):\n"
                    "    return a + b\n"
                ),
            )

            gate = GateOutcome.PASS

        elif case_id == "X1-002":

            # Deliberately incorrect candidate.
            #
            # The online gate deliberately makes a mistake and emits PASS.
            #
            # Hidden oracle must therefore classify this as FALSE RELEASE.

            candidate = _candidate(
                case_id=case_id,
                content=(
                    "def within_limit(value, limit):\n"
                    "    return value < limit\n"
                ),
            )

            gate = GateOutcome.PASS

        elif case_id == "X1-003":

            candidate = _candidate(
                case_id=case_id,
                content=(
                    "def first_or_none(values):\n"
                    "    return values[0]\n"
                ),
            )

            gate = GateOutcome.FAIL

        elif case_id == "X1-004":

            candidate = _candidate(
                case_id=case_id,
                content=(
                    "def apply_discount(amount, discount):\n"
                    "    return max(0, amount - discount)\n"
                ),
            )

            gate = (
                GateOutcome.HUMAN_REVIEW_REQUIRED
            )

        else:
            raise ValueError(
                f"Unexpected test case: {case_id}"
            )

        return PipelineRunObservation(
            run_id=(
                f"run-{case_id}-{run_index}"
            ),
            case_id=case_id,
            candidate=candidate,
            gate_outcome=gate,
            gate_decision_id=(
                f"gate-{case_id}-{run_index}"
            ),
            gate_reason_codes=(
                f"test-gate:{gate.value}",
            ),

            # Synthetic accounting values are included to verify that
            # Component 5 aggregates usage correctly.
            #
            # These are NOT cost claims.
            input_tokens=100,
            output_tokens=50,
            model_calls=2,
            wall_time_seconds=1.0,
        )


def test_first_x1_evaluation_campaign() -> None:
    """
    Exercise the complete Component 5 software path.

    Expected outcomes:

        X1-001
            candidate acceptable
            gate PASS
            => CORRECT_PASS

        X1-002
            candidate unacceptable
            gate PASS
            => FALSE_RELEASE

        X1-003
            candidate unacceptable
            gate FAIL
            => CORRECT_REJECTION

        X1-004
            candidate acceptable
            gate REVIEW
            => REVIEW_REQUIRED
    """

    online_pipeline = (
        DeterministicCampaignPipeline()
    )

    hidden_oracle = (
        DeterministicHiddenX1Oracle(
            definitions=X1_HIDDEN_DEFINITIONS
        )
    )

    runner = EvaluationCampaignRunner(
        online_pipeline=online_pipeline,
        hidden_oracle=hidden_oracle,
    )

    configuration = CampaignConfiguration(
        campaign_id=(
            "campaign-x1-b5-smoke"
        ),
        benchmark_id=BENCHMARK_ID,
        benchmark_version=BENCHMARK_VERSION,
        capability_id="X1",
        capability_version="1.0.0",
        runs_per_case=1,
        confidence_level=0.95,
    )

    report = runner.run(
        configuration=configuration,
        benchmark_cases=X1_BENCHMARK_CASES,
    )

    metrics = report.metrics

    assert metrics.total_case_runs == 4

    assert metrics.oracle_valid_case_runs == 4

    assert metrics.correct_passes == 1

    assert metrics.false_releases == 1

    assert metrics.correct_rejections == 1

    assert metrics.false_rejections == 0

    assert metrics.human_reviews == 1

    assert metrics.oracle_errors == 0

    # Three out of four cases received an automated binary decision:
    #
    #   PASS
    #   PASS
    #   FAIL
    #
    # One case abstained / requested review.

    assert metrics.automated_decisions == 3

    assert (
        metrics.automation_coverage.estimate
        == 0.75
    )

    # One false release occurred among all four oracle-valid case runs.

    assert (
        metrics.false_release_per_total.estimate
        == 0.25
    )

    # More importantly, one of two PASS decisions was wrong.

    assert (
        metrics.false_release_given_pass.estimate
        == 0.50
    )

    assert (
        metrics.human_review_rate.estimate
        == 0.25
    )

    # Synthetic usage accounting:
    #
    # 4 cases × 100 input tokens
    # 4 cases × 50 output tokens
    # 4 cases × 2 model calls

    assert metrics.total_input_tokens == 400
    assert metrics.total_output_tokens == 200
    assert metrics.total_model_calls == 8

    # Confidence interval must remain visibly broad for N=4.
    #
    # The test intentionally does not hard-code the exact numeric Wilson
    # bounds because the important requirement is that uncertainty is NOT
    # collapsed to the point estimate.

    assert (
        metrics.false_release_per_total
        .lower_bound
        is not None
    )

    assert (
        metrics.false_release_per_total
        .upper_bound
        is not None
    )

    assert (
        metrics.false_release_per_total
        .upper_bound
        >
        metrics.false_release_per_total
        .estimate
    )

