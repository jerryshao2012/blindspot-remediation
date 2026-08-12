from __future__ import annotations
import pytest
from l1_automation.bootstrap.composition import (
    build_application,
)
from l1_automation.configuration.models import (
    PlatformSettings,
    RuntimeMode,
)
def test_local_runtime_builds_local_application() -> None:
    settings = PlatformSettings(
        runtime_mode=RuntimeMode.LOCAL,
        environment_name="pytest",
        service_name="l1-test",
    )
    composition = build_application(
        settings
    )
    assert (
        composition.settings
        is settings
    )
    assert (
        composition.orchestrator
        is not None
    )
    assert (
        composition.release_gate_service
        is not None
    )
def test_azure_runtime_cannot_fall_back_to_local_adapters(
    complete_azure_settings,
) -> None:
    with pytest.raises(
        NotImplementedError,
        match="Azure POC composition",
    ):
        build_application(
            complete_azure_settings
        )

