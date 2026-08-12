"""
Production-shaped process entry point.
The entrypoint performs only startup/bootstrap responsibilities.
It does not contain:
    candidate-generation logic
    gate logic
    benchmark logic
    business KPI logic.
"""
from __future__ import annotations
from l1_automation.bootstrap.composition import (
    build_application,
)
from l1_automation.configuration import (
    load_platform_settings,
)
from l1_automation.configuration.readiness import (
    ReadinessStatus,
    evaluate_readiness,
)
def main() -> int:
    """
    Start the platform.
    Returns an operating-system-style exit code:
        0
            startup successful
        non-zero
            startup rejected
    A production Azure entrypoint should inject the real
    AzureResourceReadinessVerifier before enabling AZURE_POC.
    """
    settings = load_platform_settings()
    # LOCAL mode can evaluate readiness without Azure infrastructure.
    #
    # AZURE_POC intentionally remains NOT READY until the real Azure verifier
    # is supplied by the Azure composition layer.
    readiness = evaluate_readiness(
        settings=settings,
        azure_verifier=None,
    )
    if (
        readiness.status
        != ReadinessStatus.READY
    ):
        for failure in readiness.failures:
            print(
                f"STARTUP NOT READY: "
                f"{failure.name}: "
                f"{failure.details}"
            )
        return 2
    application = build_application(
        settings
    )
    # Starting a workflow consumer/server is intentionally outside the
    # current B6 scope.
    #
    # The composition is nevertheless constructed here so configuration
    # and dependency errors occur before accepting engineering work.
    if application.orchestrator is None:
        raise RuntimeError(
            "Composition produced no orchestrator."
        )
    return 0
if __name__ == "__main__":
    raise SystemExit(
        main()
    )

