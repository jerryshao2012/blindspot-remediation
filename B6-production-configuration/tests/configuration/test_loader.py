from __future__ import annotations
import pytest
from l1_automation.configuration import (
    ConfigurationError,
    RuntimeMode,
    load_platform_settings,
)
def test_local_configuration_requires_no_azure_settings() -> None:
    settings = load_platform_settings(
        {
            "L1_RUNTIME_MODE": "local",
            "L1_ENVIRONMENT_NAME": "pytest",
        }
    )
    assert (
        settings.runtime_mode
        == RuntimeMode.LOCAL
    )
    assert settings.azure is None
def test_azure_mode_requires_all_required_resources() -> None:
    with pytest.raises(
        ConfigurationError,
        match="L1_AZURE_SUBSCRIPTION_ID",
    ):
        load_platform_settings(
            {
                "L1_RUNTIME_MODE": "azure_poc",
            }
        )
def test_unknown_runtime_mode_fails_closed() -> None:
    with pytest.raises(
        ConfigurationError,
        match="Unsupported",
    ):
        load_platform_settings(
            {
                "L1_RUNTIME_MODE": "magic",
            }
        )
def test_azure_configuration_requires_three_distinct_jobs() -> None:
    common = {
        "L1_RUNTIME_MODE": "azure_poc",
        "L1_ENVIRONMENT_NAME": "pytest",
        "L1_AZURE_SUBSCRIPTION_ID": "subscription",
        "L1_AZURE_RESOURCE_GROUP": "rg",
        "L1_APP_CONFIGURATION_ENDPOINT": (
            "https://example.azconfig.io"
        ),
        "L1_EVIDENCE_STORAGE_ACCOUNT": "evidenceaccount",
        "L1_EVIDENCE_CONTAINER": "evidence",
        "L1_SERVICE_BUS_NAMESPACE": "namespace",
        "L1_TASK_QUEUE_NAME": "taskqueue",
        # Deliberately incorrect:
        # same execution boundary for all three responsibilities.
        "L1_CHANGE_EXECUTION_JOB_NAME": "shared-job",
        "L1_RELEASE_GATE_JOB_NAME": "shared-job",
        "L1_HIDDEN_ORACLE_JOB_NAME": "shared-job",
        "L1_AZURE_OPENAI_ENDPOINT": (
            "https://example.openai.azure.com"
        ),
        "L1_AZURE_OPENAI_DEPLOYMENT": "model",
        "L1_AZURE_DEVOPS_ORGANIZATION": "organization",
        "L1_AZURE_DEVOPS_PROJECT": "project",
        "L1_AZURE_DEVOPS_REPOSITORY": "repository",
    }
    with pytest.raises(
        ConfigurationError,
        match="three distinct",
    ):
        load_platform_settings(
            common
        )
def test_plain_http_service_endpoint_is_rejected() -> None:
    env = {
        "L1_RUNTIME_MODE": "azure_poc",
        "L1_AZURE_SUBSCRIPTION_ID": "subscription",
        "L1_AZURE_RESOURCE_GROUP": "rg",
        "L1_APP_CONFIGURATION_ENDPOINT": (
            "http://example.azconfig.io"
        ),
        "L1_EVIDENCE_STORAGE_ACCOUNT": "evidenceaccount",
        "L1_EVIDENCE_CONTAINER": "evidence",
        "L1_SERVICE_BUS_NAMESPACE": "namespace",
        "L1_TASK_QUEUE_NAME": "taskqueue",
        "L1_CHANGE_EXECUTION_JOB_NAME": "change-job",
        "L1_RELEASE_GATE_JOB_NAME": "gate-job",
        "L1_HIDDEN_ORACLE_JOB_NAME": "oracle-job",
        "L1_AZURE_OPENAI_ENDPOINT": (
            "https://example.openai.azure.com"
        ),
        "L1_AZURE_OPENAI_DEPLOYMENT": "model",
        "L1_AZURE_DEVOPS_ORGANIZATION": "organization",
        "L1_AZURE_DEVOPS_PROJECT": "project",
        "L1_AZURE_DEVOPS_REPOSITORY": "repository",
    }
    with pytest.raises(
        ConfigurationError,
        match="HTTPS",
    ):
        load_platform_settings(
            env
        )

