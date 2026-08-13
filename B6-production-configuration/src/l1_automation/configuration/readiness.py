"""
Startup readiness validation.
CONFIGURATION VALIDITY IS NOT THE SAME AS PRODUCTION READINESS.
For example:
    L1_HIDDEN_ORACLE_JOB_NAME=x1-oracle
is syntactically valid.
That does NOT prove:
    - the resource exists;
    - RBAC is correct;
    - the online gate cannot read hidden storage;
    - the container image is approved;
    - networking is correctly restricted.
B6 therefore represents readiness checks explicitly.
Local checks can run without Azure.
Azure-resource checks are provided through a port so the real adapter can be
implemented without putting Azure SDK dependencies into domain/configuration
code.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from .models import (
    PlatformSettings,
    RuntimeMode,
)
class ReadinessStatus(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"
@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    """
    Result of one explicit startup/readiness assertion.
    """
    name: str
    passed: bool
    details: str
@dataclass(frozen=True, slots=True)
class ReadinessReport:
    """
    Complete readiness result.
    A report is READY only when every required check passes.
    """
    status: ReadinessStatus
    checks: tuple[ReadinessCheck, ...]
    @property
    def failures(
        self,
    ) -> tuple[ReadinessCheck, ...]:
        return tuple(
            check
            for check in self.checks
            if not check.passed
        )
class AzureResourceVerifierPort(ABC):
    """
    Infrastructure adapter used to verify Azure POC prerequisites.
    This interface intentionally describes capabilities rather than exposing
    Azure SDK clients throughout the application.
    """
    @abstractmethod
    def verify_container_job(
        self,
        *,
        job_name: str,
    ) -> bool:
        raise NotImplementedError
    @abstractmethod
    def verify_evidence_store(
        self,
        *,
        account_name: str,
        container_name: str,
    ) -> bool:
        raise NotImplementedError
    @abstractmethod
    def verify_service_bus_queue(
        self,
        *,
        namespace: str,
        queue_name: str,
    ) -> bool:
        raise NotImplementedError
    @abstractmethod
    def verify_model_endpoint(
        self,
        *,
        endpoint: str,
        deployment: str,
    ) -> bool:
        raise NotImplementedError
    @abstractmethod
    def verify_hidden_oracle_isolation(
        self,
        *,
        change_job_name: str,
        gate_job_name: str,
        oracle_job_name: str,
    ) -> bool:
        """
        Verify the infrastructure-level trust boundary.
        A strong implementation should verify that change execution and
        release gating do NOT possess the identity/permissions required to
        read hidden oracle artifacts.
        """
        raise NotImplementedError
def evaluate_readiness(
    *,
    settings: PlatformSettings,
    azure_verifier: AzureResourceVerifierPort | None = None,
) -> ReadinessReport:
    """
    Evaluate startup readiness.
    LOCAL mode requires no Azure verifier.
    AZURE_POC fails explicitly if no real Azure verifier is provided.
    This prevents code such as:
        if verifier is None:
            return READY
    which would create false assurance.
    """
    checks: list[ReadinessCheck] = []
    checks.append(
        ReadinessCheck(
            name="runtime_configuration_valid",
            passed=True,
            details=(
                "PlatformSettings was successfully constructed."
            ),
        )
    )
    if settings.runtime_mode == RuntimeMode.LOCAL:
        checks.append(
            ReadinessCheck(
                name="azure_resources_not_required",
                passed=True,
                details=(
                    "LOCAL mode intentionally uses no Azure POC resources."
                ),
            )
        )
        return ReadinessReport(
            status=ReadinessStatus.READY,
            checks=tuple(checks),
        )
    assert settings.azure is not None
    if azure_verifier is None:
        checks.append(
            ReadinessCheck(
                name="azure_resource_verifier",
                passed=False,
                details=(
                    "AZURE_POC requires a real AzureResourceVerifierPort "
                    "implementation. No local/fake fallback is permitted."
                ),
            )
        )
        return ReadinessReport(
            status=ReadinessStatus.NOT_READY,
            checks=tuple(checks),
        )
    azure = settings.azure
    checks.extend(
        (
            ReadinessCheck(
                name="change_execution_job",
                passed=azure_verifier.verify_container_job(
                    job_name=azure.change_execution_job_name,
                ),
                details=azure.change_execution_job_name,
            ),
            ReadinessCheck(
                name="release_gate_job",
                passed=azure_verifier.verify_container_job(
                    job_name=azure.release_gate_job_name,
                ),
                details=azure.release_gate_job_name,
            ),
            ReadinessCheck(
                name="hidden_oracle_job",
                passed=azure_verifier.verify_container_job(
                    job_name=azure.hidden_oracle_job_name,
                ),
                details=azure.hidden_oracle_job_name,
            ),
            ReadinessCheck(
                name="evidence_store",
                passed=azure_verifier.verify_evidence_store(
                    account_name=azure.evidence_storage_account,
                    container_name=azure.evidence_container,
                ),
                details=(
                    f"{azure.evidence_storage_account}/"
                    f"{azure.evidence_container}"
                ),
            ),
            ReadinessCheck(
                name="service_bus_queue",
                passed=azure_verifier.verify_service_bus_queue(
                    namespace=azure.service_bus_namespace,
                    queue_name=azure.task_queue_name,
                ),
                details=(
                    f"{azure.service_bus_namespace}/"
                    f"{azure.task_queue_name}"
                ),
            ),
            ReadinessCheck(
                name="model_endpoint",
                passed=azure_verifier.verify_model_endpoint(
                    endpoint=azure.azure_openai_endpoint,
                    deployment=azure.azure_openai_deployment,
                ),
                details=azure.azure_openai_deployment,
            ),
            ReadinessCheck(
                name="hidden_oracle_isolation",
                passed=(
                    azure_verifier.verify_hidden_oracle_isolation(
                        change_job_name=(
                            azure.change_execution_job_name
                        ),
                        gate_job_name=(
                            azure.release_gate_job_name
                        ),
                        oracle_job_name=(
                            azure.hidden_oracle_job_name
                        ),
                    )
                ),
                details=(
                    "Online change/gate identities must not be able to "
                    "read hidden-oracle resources."
                ),
            ),
        )
    )
    status = (
        ReadinessStatus.READY
        if all(
            check.passed
            for check in checks
        )
        else ReadinessStatus.NOT_READY
    )
    return ReadinessReport(
        status=status,
        checks=tuple(checks),
    )

