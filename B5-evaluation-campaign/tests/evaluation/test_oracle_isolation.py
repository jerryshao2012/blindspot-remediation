"""
Tests documenting the hidden-oracle trust boundary.

Python typing cannot by itself prove that production credentials are isolated.

This test verifies the APPLICATION interface:

    OnlinePipelinePort.execute(...)

receives only:

    PublicTaskPackage
    run_index

and not HiddenOraclePort.

Infrastructure-level credential isolation must later be tested separately.
"""

import inspect

from l1_automation.evaluation.campaign_runner import (
    OnlinePipelinePort,
)


def test_online_pipeline_interface_has_no_hidden_oracle_parameter() -> None:

    signature = inspect.signature(
        OnlinePipelinePort.execute
    )

    parameters = set(
        signature.parameters
    )

    assert "hidden_oracle" not in parameters
    assert "oracle" not in parameters
    assert "expected_answer" not in parameters
    assert "reference_patch" not in parameters

