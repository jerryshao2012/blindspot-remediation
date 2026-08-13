from __future__ import annotations
from l1_automation.configuration.models import (
    PlatformSettings,
    RuntimeMode,
)
from l1_automation.configuration.readiness import (
    ReadinessStatus,
    evaluate_readiness,
)
def test_local_runtime_is_ready_without_azure_verifier() -> None:
    settings = PlatformSettings(
        runtime_mode=RuntimeMode.LOCAL,
        environment_name="pytest",
        service_name="l1-test",
    )
    report = evaluate_readiness(
        settings=settings
    )
    assert (
        report.status
        == ReadinessStatus.READY
    )
def test_azure_runtime_is_not_ready_without_real_verifier(
    azure_settings,
) -> None:
    """
    `azure_settings` should be the complete validated test fixture used by
    the configuration tests.
    The important assertion is architectural:
        AZURE_POC
        +
        no real verifier
        !=
        READY
    """
    report = evaluate_readiness(
        settings=azure_settings,
        azure_verifier=None,
    )
    assert (
        report.status
        == ReadinessStatus.NOT_READY
    )
    assert any(
        failure.name
        == "azure_resource_verifier"
        for failure in report.failures
    )

