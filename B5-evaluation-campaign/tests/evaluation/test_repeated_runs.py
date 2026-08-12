"""
Repeated-run semantics.

This test protects against a subtle statistical mistake:

    10 stochastic reruns of one task

must not be described as:

    10 different benchmark tasks.

B5 records every run, but campaign interpretation must retain case identity.
"""

from l1_automation.evaluation.campaign_runner import (
    EvaluationCampaignRunner,
)

from l1_automation.evaluation.contracts import (
    CampaignConfiguration,
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

from .test_x1_campaign import (
    DeterministicCampaignPipeline,
)


def test_repeated_runs_preserve_case_identity() -> None:

    runner = EvaluationCampaignRunner(
        online_pipeline=(
            DeterministicCampaignPipeline()
        ),
        hidden_oracle=(
            DeterministicHiddenX1Oracle(
                definitions=X1_HIDDEN_DEFINITIONS
            )
        ),
    )

    configuration = CampaignConfiguration(
        campaign_id="campaign-repeat-test",
        benchmark_id=BENCHMARK_ID,
        benchmark_version=BENCHMARK_VERSION,
        capability_id="X1",
        capability_version="1.0.0",
        runs_per_case=3,
    )

    report = runner.run(
        configuration=configuration,
        benchmark_cases=X1_BENCHMARK_CASES,
    )

    # Four unique tasks × three stochastic-style repetitions.

    assert len(report.case_results) == 12

    unique_cases = {
        result.case_id
        for result in report.case_results
    }

    assert len(unique_cases) == 4

    for case_id in unique_cases:

        case_runs = [
            result
            for result in report.case_results
            if result.case_id == case_id
        ]

        assert len(case_runs) == 3

        assert {
            result.run_index
            for result in case_runs
        } == {0, 1, 2}

