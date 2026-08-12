"""
Canonical B6 composition root.
THIS REPLACES THE TEMPORARY B4 COMPOSITION MODEL.
By B6, the repository should use the actual Components 1–12 rather than
maintaining simplified B4/B5 duplicates.
IMPORTANT
---------
The imports shown below establish the TARGET canonical structure.
If the physical files created in Components 1–12 currently use different
package names, move/re-export them into these canonical locations during B6.
Do NOT solve import disagreement by keeping two competing contract classes.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from l1_automation.configuration import (
    PlatformSettings,
    RuntimeMode,
)
# ---------------------------------------------------------------------
# PORTS USED BY THE COMPOSITION ROOT
# ---------------------------------------------------------------------
#
# If these protocols already exist in Components 2–12, import those canonical
# interfaces instead.
#
# The key rule is one authoritative interface per responsibility.
# ---------------------------------------------------------------------
class ChangeExecutionPort(Protocol):
    def execute(
        self,
        task,
        specification,
    ):
        ...
class ReleaseGatePort(Protocol):
    def evaluate(
        self,
        *,
        task,
        specification,
        candidate,
    ):
        ...
class CapabilityRegistryPort(Protocol):
    def resolve(
        self,
        task_type: str,
    ):
        ...
class EvidenceRepositoryPort(Protocol):
    def save(
        self,
        artifact,
    ) -> None:
        ...
class WorkflowPublisherPort(Protocol):
    def publish(
        self,
        event,
    ) -> None:
        ...
class OrchestratorPort(Protocol):
    def run(
        self,
        task,
    ):
        ...
@dataclass(frozen=True, slots=True)
class ApplicationComposition:
    """
    Fully constructed object graph.
    Keeping important services visible is useful for:
        tests
        diagnostics
        explicit startup
        evaluation adapters
    It avoids a global service-locator pattern.
    """
    settings: PlatformSettings
    capability_registry: CapabilityRegistryPort
    change_execution_service: ChangeExecutionPort
    release_gate_service: ReleaseGatePort
    evidence_repository: EvidenceRepositoryPort
    workflow_publisher: WorkflowPublisherPort
    orchestrator: OrchestratorPort
def build_application(
    settings: PlatformSettings,
) -> ApplicationComposition:
    """
    Build the application for the selected runtime.
    Runtime branching occurs ONLY at composition time.
    Domain services should not contain repeated code like:
        if azure:
            ...
        else:
            ...
    because infrastructure selection is not domain logic.
    """
    if settings.runtime_mode == RuntimeMode.LOCAL:
        return _build_local_application(
            settings
        )
    if settings.runtime_mode == RuntimeMode.AZURE_POC:
        return _build_azure_application(
            settings
        )
    raise RuntimeError(
        f"Unsupported runtime mode: "
        f"{settings.runtime_mode!r}"
    )
def _build_local_application(
    settings: PlatformSettings,
) -> ApplicationComposition:
    """
    Construct local deterministic/test adapters.
    IMPORTANT:
    The concrete imports should point to the existing Components 2–12 after
    physical repository reconciliation.
    They are imported inside the function so merely importing this module does
    not initialize infrastructure.
    """
    # Replace these module paths only if the earlier components use different
    # physical locations. Do not duplicate their implementations.
    from l1_automation.capabilities.local_registry import (
        LocalCapabilityRegistry,
    )
    from l1_automation.change_execution.local_service import (
        LocalChangeExecutionService,
    )
    from l1_automation.evidence.in_memory_repository import (
        InMemoryEvidenceRepository,
    )
    from l1_automation.release_gate.local_service import (
        LocalReleaseGateService,
    )
    from l1_automation.workflow.in_memory_publisher import (
        InMemoryWorkflowPublisher,
    )
    from l1_automation.orchestration.service import (
        OrchestrationService,
    )
    evidence_repository = (
        InMemoryEvidenceRepository()
    )
    capability_registry = (
        LocalCapabilityRegistry()
    )
    change_execution = (
        LocalChangeExecutionService(
            evidence_repository=(
                evidence_repository
            )
        )
    )
    release_gate = (
        LocalReleaseGateService(
            evidence_repository=(
                evidence_repository
            )
        )
    )
    workflow_publisher = (
        InMemoryWorkflowPublisher()
    )
    orchestrator = OrchestrationService(
        capability_registry=(
            capability_registry
        ),
        change_execution_service=(
            change_execution
        ),
        release_gate_service=(
            release_gate
        ),
        evidence_repository=(
            evidence_repository
        ),
        workflow_publisher=(
            workflow_publisher
        ),
    )
    return ApplicationComposition(
        settings=settings,
        capability_registry=(
            capability_registry
        ),
        change_execution_service=(
            change_execution
        ),
        release_gate_service=(
            release_gate
        ),
        evidence_repository=(
            evidence_repository
        ),
        workflow_publisher=(
            workflow_publisher
        ),
        orchestrator=orchestrator,
    )
def _build_azure_application(
    settings: PlatformSettings,
) -> ApplicationComposition:
    """
    Construct the real Azure POC object graph.
    B6 intentionally refuses to pretend that Azure adapters exist when the
    enterprise-specific implementations are still outstanding.
    Once the Azure adapters documented in NOT-IMPLEMENTED.md are completed,
    this function should be implemented using those real classes.
    Until then it raises NotImplementedError.
    """
    if settings.azure is None:
        raise RuntimeError(
            "AZURE_POC composition requires Azure settings."
        )
    raise NotImplementedError(
        "Azure POC composition is not complete. "
        "Implement the enterprise-approved Azure adapters for "
        "Container Apps Jobs, evidence storage, Service Bus, "
        "Azure OpenAI authentication, Azure DevOps workflow, and "
        "hidden-oracle isolation before enabling AZURE_POC."
    )

