"""
Validated runtime settings for the L1 automation platform.
Important distinction
---------------------
Runtime infrastructure configuration and assurance policy are NOT the same
thing.
Examples of runtime configuration:
    - execution mode
    - Azure resource identifiers
    - evidence-storage location
    - model deployment identifier
Examples of assurance policy:
    - required evidence classes
    - mutation threshold
    - hard-veto findings
    - evidence-generation budget
    - gate escalation rules
Assurance policy belongs to the versioned task capability / GatePolicy
artifacts and must not be casually replaced with environment variables.
This module therefore intentionally contains only bootstrap/runtime concerns.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
import os
class RuntimeMode(StrEnum):
    """Supported platform runtime modes."""
    LOCAL = "local"
    AZURE_POC = "azure_poc"
@dataclass(frozen=True, slots=True)
class PlatformSettings:
    """
    Immutable bootstrap configuration.
    The first E2E test uses LOCAL mode deliberately. A software integration
    test should not require an Azure subscription or live LLM endpoint merely
    to prove that the architecture is wired correctly.
    Production/Azure-specific settings should be introduced only through
    concrete infrastructure adapters.
    """
    runtime_mode: RuntimeMode = RuntimeMode.LOCAL
    service_name: str = "l1-engineering-automation"
    environment_name: str = "local"
    evidence_namespace: str = "x1-e2e"
    @classmethod
    def from_environment(cls) -> "PlatformSettings":
        """
        Construct settings from environment variables.
        Unknown runtime modes fail immediately. We do not silently fall back
        to LOCAL because accidentally running a production-shaped process
        with local adapters would create a misleading operating state.
        """
        raw_mode = os.getenv(
            "L1_AUTOMATION_RUNTIME_MODE",
            RuntimeMode.LOCAL.value,
        ).strip().lower()
        try:
            runtime_mode = RuntimeMode(raw_mode)
        except ValueError as exc:
            allowed = ", ".join(mode.value for mode in RuntimeMode)
            raise ValueError(
                "Unsupported L1_AUTOMATION_RUNTIME_MODE="
                f"{raw_mode!r}. Allowed values: {allowed}."
            ) from exc
        service_name = os.getenv(
            "L1_AUTOMATION_SERVICE_NAME",
            "l1-engineering-automation",
        ).strip()
        environment_name = os.getenv(
            "L1_AUTOMATION_ENVIRONMENT",
            "local",
        ).strip()
        evidence_namespace = os.getenv(
            "L1_AUTOMATION_EVIDENCE_NAMESPACE",
            "x1-e2e",
        ).strip()
        for name, value in (
            ("service_name", service_name),
            ("environment_name", environment_name),
            ("evidence_namespace", evidence_namespace),
        ):
            if not value:
                raise ValueError(
                    f"{name} must contain a non-empty value."
                )
        return cls(
            runtime_mode=runtime_mode,
            service_name=service_name,
            environment_name=environment_name,
            evidence_namespace=evidence_namespace,
        )

