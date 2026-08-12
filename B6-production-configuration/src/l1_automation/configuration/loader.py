"""
Environment-based configuration loader.
WHY ENVIRONMENT VARIABLES HERE?
-------------------------------
Environment variables are suitable for locating infrastructure resources and
selecting runtime mode.
They are NOT used for assurance-policy thresholds.
The loader never reads:
    L1_GATE_MIN_MUTATION_SCORE
    L1_FALSE_RELEASE_TOLERANCE
    L1_REQUIRED_EVIDENCE
because those values belong in versioned policy artifacts.
SECURITY
--------
This module deliberately has no:
    AZURE_OPENAI_API_KEY
    STORAGE_CONNECTION_STRING
    SERVICE_BUS_CONNECTION_STRING
settings.
Azure adapters should prefer managed identity/keyless access.
If enterprise architecture later requires a secret, it should be introduced
through a dedicated secret abstraction and documented explicitly rather than
quietly added to this configuration object.
"""
from __future__ import annotations
import os
from collections.abc import Mapping
from .errors import ConfigurationError
from .models import (
    AzurePocSettings,
    PlatformSettings,
    RuntimeMode,
)
def _required(
    environment: Mapping[str, str],
    key: str,
) -> str:
    """
    Read one required environment variable.
    """
    value = environment.get(
        key,
        "",
    ).strip()
    if not value:
        raise ConfigurationError(
            f"Required environment variable {key!r} is missing."
        )
    return value
def _optional(
    environment: Mapping[str, str],
    key: str,
    default: str,
) -> str:
    """
    Read one optional environment variable with a non-secret default.
    """
    return environment.get(
        key,
        default,
    ).strip()
def load_platform_settings(
    environment: Mapping[str, str] | None = None,
) -> PlatformSettings:
    """
    Load and validate startup configuration.
    Passing an explicit mapping makes this function deterministic in tests and
    prevents unit tests from depending on a developer workstation's process
    environment.
    """
    env: Mapping[str, str] = (
        os.environ
        if environment is None
        else environment
    )
    raw_mode = _optional(
        env,
        "L1_RUNTIME_MODE",
        RuntimeMode.LOCAL.value,
    ).lower()
    try:
        runtime_mode = RuntimeMode(
            raw_mode
        )
    except ValueError as exc:
        allowed = ", ".join(
            mode.value
            for mode in RuntimeMode
        )
        raise ConfigurationError(
            f"Unsupported L1_RUNTIME_MODE={raw_mode!r}. "
            f"Allowed values: {allowed}."
        ) from exc
    environment_name = _optional(
        env,
        "L1_ENVIRONMENT_NAME",
        "local",
    )
    service_name = _optional(
        env,
        "L1_SERVICE_NAME",
        "l1-engineering-automation",
    )
    if runtime_mode == RuntimeMode.LOCAL:
        try:
            return PlatformSettings(
                runtime_mode=runtime_mode,
                environment_name=environment_name,
                service_name=service_name,
                azure=None,
            )
        except ValueError as exc:
            raise ConfigurationError(
                str(exc)
            ) from exc
    # -------------------------------------------------------------
    # AZURE_POC
    # -------------------------------------------------------------
    #
    # Every important resource identifier is explicit.
    #
    # We do not infer:
    #
    #     resource group from subscription
    #     queue name from environment
    #     model deployment from endpoint
    #
    # because convention-based guessing creates difficult-to-debug and
    # potentially unsafe deployment behavior.
    try:
        azure = AzurePocSettings(
            subscription_id=_required(
                env,
                "L1_AZURE_SUBSCRIPTION_ID",
            ),
            resource_group=_required(
                env,
                "L1_AZURE_RESOURCE_GROUP",
            ),
            app_configuration_endpoint=_required(
                env,
                "L1_APP_CONFIGURATION_ENDPOINT",
            ),
            evidence_storage_account=_required(
                env,
                "L1_EVIDENCE_STORAGE_ACCOUNT",
            ),
            evidence_container=_required(
                env,
                "L1_EVIDENCE_CONTAINER",
            ),
            service_bus_namespace=_required(
                env,
                "L1_SERVICE_BUS_NAMESPACE",
            ),
            task_queue_name=_required(
                env,
                "L1_TASK_QUEUE_NAME",
            ),
            change_execution_job_name=_required(
                env,
                "L1_CHANGE_EXECUTION_JOB_NAME",
            ),
            release_gate_job_name=_required(
                env,
                "L1_RELEASE_GATE_JOB_NAME",
            ),
            hidden_oracle_job_name=_required(
                env,
                "L1_HIDDEN_ORACLE_JOB_NAME",
            ),
            azure_openai_endpoint=_required(
                env,
                "L1_AZURE_OPENAI_ENDPOINT",
            ),
            azure_openai_deployment=_required(
                env,
                "L1_AZURE_OPENAI_DEPLOYMENT",
            ),
            azure_devops_organization=_required(
                env,
                "L1_AZURE_DEVOPS_ORGANIZATION",
            ),
            azure_devops_project=_required(
                env,
                "L1_AZURE_DEVOPS_PROJECT",
            ),
            azure_devops_repository=_required(
                env,
                "L1_AZURE_DEVOPS_REPOSITORY",
            ),
        )
        return PlatformSettings(
            runtime_mode=runtime_mode,
            environment_name=environment_name,
            service_name=service_name,
            azure=azure,
        )
    except ValueError as exc:
        raise ConfigurationError(
            str(exc)
        ) from exc

