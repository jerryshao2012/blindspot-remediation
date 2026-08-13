"""
Validated immutable runtime configuration models.
DESIGN CHOICES
--------------
1. Standard-library dataclasses are used.
   B6 does not require an additional validation framework merely to represent
   configuration.
2. Objects are frozen.
   Runtime configuration is constructed once at startup and should not be
   mutated underneath an active campaign or gate execution.
3. Secrets are deliberately absent.
   The Azure production path should use managed identity / Azure Identity
   where possible. If a future adapter genuinely requires a secret, that
   adapter should obtain it through the enterprise-approved secret mechanism.
4. Gate thresholds are deliberately absent.
   Assurance policy is not ordinary runtime configuration.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse
class RuntimeMode(StrEnum):
    """
    Supported composition modes.
    LOCAL
        Deterministic/local development adapters.
    AZURE_POC
        Real Azure POC infrastructure.
    No implicit fallback exists from AZURE_POC to LOCAL.
    """
    LOCAL = "local"
    AZURE_POC = "azure_poc"
def _require_non_empty(
    *,
    name: str,
    value: str,
) -> str:
    """
    Validate and normalize a required string.
    """
    normalized = value.strip()
    if not normalized:
        raise ValueError(
            f"{name} must be non-empty."
        )
    return normalized
def _require_https_url(
    *,
    name: str,
    value: str,
) -> str:
    """
    Require an absolute HTTPS endpoint.
    Azure service endpoints should not silently accept malformed or plaintext
    HTTP URLs in production-shaped configuration.
    """
    normalized = _require_non_empty(
        name=name,
        value=value,
    )
    parsed = urlparse(normalized)
    if parsed.scheme.lower() != "https":
        raise ValueError(
            f"{name} must use HTTPS."
        )
    if not parsed.netloc:
        raise ValueError(
            f"{name} must be an absolute URL."
        )
    return normalized.rstrip("/")
@dataclass(frozen=True, slots=True)
class AzurePocSettings:
    """
    Azure-specific infrastructure settings.
    IMPORTANT:
    None of these fields is an assurance threshold.
    None contains a secret.
    """
    subscription_id: str
    resource_group: str
    app_configuration_endpoint: str
    evidence_storage_account: str
    evidence_container: str
    service_bus_namespace: str
    task_queue_name: str
    change_execution_job_name: str
    release_gate_job_name: str
    hidden_oracle_job_name: str
    azure_openai_endpoint: str
    azure_openai_deployment: str
    azure_devops_organization: str
    azure_devops_project: str
    azure_devops_repository: str
    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subscription_id",
            _require_non_empty(
                name="subscription_id",
                value=self.subscription_id,
            ),
        )
        object.__setattr__(
            self,
            "resource_group",
            _require_non_empty(
                name="resource_group",
                value=self.resource_group,
            ),
        )
        object.__setattr__(
            self,
            "app_configuration_endpoint",
            _require_https_url(
                name="app_configuration_endpoint",
                value=self.app_configuration_endpoint,
            ),
        )
        object.__setattr__(
            self,
            "azure_openai_endpoint",
            _require_https_url(
                name="azure_openai_endpoint",
                value=self.azure_openai_endpoint,
            ),
        )
        # These values are names/identifiers rather than URLs.
        for field_name in (
            "evidence_storage_account",
            "evidence_container",
            "service_bus_namespace",
            "task_queue_name",
            "change_execution_job_name",
            "release_gate_job_name",
            "hidden_oracle_job_name",
            "azure_openai_deployment",
            "azure_devops_organization",
            "azure_devops_project",
            "azure_devops_repository",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_empty(
                    name=field_name,
                    value=getattr(
                        self,
                        field_name,
                    ),
                ),
            )
        # The three execution responsibilities intentionally require different
        # job names.
        #
        # Reusing one job definition for all three could accidentally give the
        # online gate the same credentials/mounts as the hidden oracle.
        job_names = {
            self.change_execution_job_name,
            self.release_gate_job_name,
            self.hidden_oracle_job_name,
        }
        if len(job_names) != 3:
            raise ValueError(
                "Change execution, release gate, and hidden oracle must "
                "use three distinct Azure Container Apps Job names."
            )
@dataclass(frozen=True, slots=True)
class PlatformSettings:
    """
    Complete runtime settings.
    Azure settings are:
        forbidden in LOCAL mode;
        required in AZURE_POC mode.
    This prevents ambiguous partially-Azure configurations.
    """
    runtime_mode: RuntimeMode
    environment_name: str
    service_name: str
    azure: AzurePocSettings | None = None
    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "environment_name",
            _require_non_empty(
                name="environment_name",
                value=self.environment_name,
            ),
        )
        object.__setattr__(
            self,
            "service_name",
            _require_non_empty(
                name="service_name",
                value=self.service_name,
            ),
        )
        if (
            self.runtime_mode == RuntimeMode.LOCAL
            and self.azure is not None
        ):
            raise ValueError(
                "LOCAL runtime must not contain Azure POC settings."
            )
        if (
            self.runtime_mode == RuntimeMode.AZURE_POC
            and self.azure is None
        ):
            raise ValueError(
                "AZURE_POC runtime requires Azure settings."
            )

