"""
B4 composition root for the first X1 proof of concept.
WHY THIS FILE EXISTS
--------------------
Earlier components intentionally define responsibilities independently:
    ChangeExecutionService
    ReleaseGateService
    EvidenceRepository
    ExecutionEnvironment
    CapabilityRegistry
    Orchestrator
    WorkflowIntegration
    ...
At some point, however, concrete objects must actually be constructed and
connected.
That location is the composition root.
The composition root is intentionally NOT:
    - a domain service;
    - an AI agent;
    - a release gate;
    - an evaluation runner;
    - a service locator used throughout the codebase.
It is startup wiring.
IMPORTANT ASSURANCE RULE
------------------------
The composition root may choose implementations.
It must NOT weaken the assurance architecture.
For example, it must not wire:
    ChangeExecutionService
        and
    ReleaseGateService
to a shared mutable workspace that allows the release gate accidentally to
inherit hidden state from candidate generation.
Likewise, it must not give ReleaseGateService access to the hidden benchmark
oracle used by EvaluationCampaignRunner.
The POC composition below intentionally constructs a deterministic local
system suitable for software testing.
The real Azure composition is NOT silently simulated here.
Where enterprise-specific Azure configuration is required, the production
factory raises NotImplementedError rather than returning an implementation
that merely looks production-ready.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Final
from uuid import uuid4
from .settings import PlatformSettings, RuntimeMode
# ---------------------------------------------------------------------
# B4 LOCAL DOMAIN TYPES
# ---------------------------------------------------------------------
#
# IMPORTANT:
#
# B1 is the canonical owner of shared contracts in the final repository.
#
# These compact B4 types are deliberately isolated in this composition/test
# slice so that the end-to-end example remains executable even while the
# repository is being consolidated.
#
# During final repository reconciliation, these types should be replaced by
# direct imports from the canonical B1 contracts.
#
# They are NOT competing production contracts.
#
# This is preferable to guessing the exact historical import paths of the
# individually authored Components 1–12 and silently creating incompatible
# imports.
# ---------------------------------------------------------------------
from dataclasses import field
from enum import StrEnum
class GateOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
class RunState(StrEnum):
    RECEIVED = "received"
    CANDIDATE_CREATED = "candidate_created"
    GATING = "gating"
    READY_FOR_RELEASE = "ready_for_release"
    FAILED_GATE = "failed_gate"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
@dataclass(frozen=True, slots=True)
class TaskRequest:
    task_request_id: str
    task_type: str
    repository_id: str
    baseline_revision: str
    instruction: str
@dataclass(frozen=True, slots=True)
class TaskSpecification:
    task_type: str
    version: str
    allowed_paths: tuple[str, ...]
    required_evidence: tuple[str, ...]
@dataclass(frozen=True, slots=True)
class CandidateArtifact:
    candidate_id: str
    task_request_id: str
    baseline_revision: str
    patch_text: str
    sha256: str
@dataclass(frozen=True, slots=True)
class EvidenceArtifact:
    evidence_id: str
    candidate_id: str
    evidence_type: str
    passed: bool
    details: str
    sha256: str
@dataclass(frozen=True, slots=True)
class GateDecision:
    decision_id: str
    candidate_id: str
    candidate_sha256: str
    outcome: GateOutcome
    reason_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    run_id: str
    task_request_id: str
    candidate: CandidateArtifact
    gate_decision: GateDecision
    final_state: RunState
# ---------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------
def _sha256_text(value: str) -> str:
    """
    Return a lowercase SHA-256 digest for UTF-8 text.
    Content hashing is used here to demonstrate candidate/evidence binding.
    A cryptographic digest proves byte identity/integrity; it does NOT prove
    that the content is semantically correct.
    """
    return sha256(value.encode("utf-8")).hexdigest()
# ---------------------------------------------------------------------
# LOCAL EVIDENCE REPOSITORY
# ---------------------------------------------------------------------
class InMemoryEvidenceRepository:
    """
    Deterministic evidence repository used by the B4 software E2E test.
    This implementation deliberately stores artifacts in memory.
    It demonstrates the EvidenceRepository responsibility but does NOT prove:
        - Azure Blob Storage behavior;
        - enterprise retention;
        - encryption configuration;
        - managed identity;
        - immutability policy;
        - disaster recovery.
    Those are infrastructure/integration concerns and must be tested against
    their real adapters separately.
    """
    def __init__(self) -> None:
        self._evidence: dict[str, EvidenceArtifact] = {}
        self._decisions: dict[str, GateDecision] = {}
    def save_evidence(
        self,
        evidence: EvidenceArtifact,
    ) -> None:
        if evidence.evidence_id in self._evidence:
            existing = self._evidence[evidence.evidence_id]
            if existing != evidence:
                raise ValueError(
                    "Evidence ID collision: the same evidence_id was "
                    "used for different immutable evidence."
                )
            # Idempotent replay of exactly the same artifact is safe.
            return
        self._evidence[evidence.evidence_id] = evidence
    def save_gate_decision(
        self,
        decision: GateDecision,
    ) -> None:
        if decision.decision_id in self._decisions:
            existing = self._decisions[decision.decision_id]
            if existing != decision:
                raise ValueError(
                    "Gate decision ID collision detected."
                )
            return
        self._decisions[decision.decision_id] = decision
    def get_evidence(
        self,
        evidence_id: str,
    ) -> EvidenceArtifact:
        try:
            return self._evidence[evidence_id]
        except KeyError as exc:
            raise KeyError(
                f"Unknown evidence_id: {evidence_id}"
            ) from exc
    def get_gate_decision(
        self,
        decision_id: str,
    ) -> GateDecision:
        try:
            return self._decisions[decision_id]
        except KeyError as exc:
            raise KeyError(
                f"Unknown decision_id: {decision_id}"
            ) from exc
    def evidence_for_candidate(
        self,
        candidate_id: str,
    ) -> tuple[EvidenceArtifact, ...]:
        return tuple(
            evidence
            for evidence in self._evidence.values()
            if evidence.candidate_id == candidate_id
        )
# ---------------------------------------------------------------------
# X1 CAPABILITY REGISTRY
# ---------------------------------------------------------------------
X1_TASK_TYPE: Final[str] = "X1"
X1_SPECIFICATION: Final[TaskSpecification] = TaskSpecification(
    task_type=X1_TASK_TYPE,
    version="1.0.0",
    allowed_paths=("src/calculator.py",),
    required_evidence=(
        "syntax",
        "existing_tests",
        "x1_acceptance",
        "mutation_probe",
    ),
)
class LocalCapabilityRegistry:
    """
    Minimal deterministic capability registry for B4.
    The POC deliberately has one registered capability.
    Unknown capabilities fail closed.
    A production registry may load signed/versioned YAML and skill artifacts,
    but the calling semantics should remain the same: the orchestrator asks
    for an approved capability; it does not invent one.
    """
    def __init__(
        self,
        specifications: tuple[TaskSpecification, ...],
    ) -> None:
        if not specifications:
            raise ValueError(
                "At least one approved capability is required."
            )
        self._specifications = {
            specification.task_type: specification
            for specification in specifications
        }
        if len(self._specifications) != len(specifications):
            raise ValueError(
                "Duplicate task_type values are not permitted."
            )
    def resolve(
        self,
        task_type: str,
    ) -> TaskSpecification:
        try:
            return self._specifications[task_type]
        except KeyError as exc:
            raise ValueError(
                f"Task type {task_type!r} is not an approved capability."
            ) from exc
# ---------------------------------------------------------------------
# DETERMINISTIC X1 CHANGE EXECUTION
# ---------------------------------------------------------------------
class DeterministicX1ChangeExecutionService:
    """
    Deterministic stand-in for Component 2 in the B4 SOFTWARE E2E test.
    Why not call an LLM here?
    -------------------------
    Because B4 is verifying software composition.
    A live LLM would make this test dependent on:
        - network availability;
        - credentials;
        - model deployment;
        - model version;
        - stochastic generation;
        - inference quota;
        - inference cost.
    Those concerns belong in separate adapter/integration tests and, more
    importantly, Component 5 evaluation campaigns.
    This deterministic implementation produces the exact candidate needed
    to exercise the complete PASS path.
    It is not presented as an AI implementation.
    The production ChangeExecutionService from Component 2 should replace
    this test implementation through dependency injection.
    """
    def execute(
        self,
        task: TaskRequest,
        specification: TaskSpecification,
    ) -> CandidateArtifact:
        if task.task_type != specification.task_type:
            raise ValueError(
                "TaskRequest and TaskSpecification task types differ."
            )
        if specification.task_type != X1_TASK_TYPE:
            raise ValueError(
                "This deterministic executor supports only X1."
            )
        # X1 is intentionally narrow:
        #
        # Correct an integer addition implementation whose baseline behavior
        # incorrectly subtracts the second operand.
        #
        # The patch representation is intentionally simple in B4 because the
        # purpose is orchestration and assurance wiring, not Git patch parsing.
        #
        # The real Component 2 candidate contract should contain the canonical
        # patch/repository metadata already defined elsewhere in the project.
        patch_text = (
            "--- a/src/calculator.py\n"
            "+++ b/src/calculator.py\n"
            "@@\n"
            "-    return a - b\n"
            "+    return a + b\n"
        )
        digest = _sha256_text(patch_text)
        return CandidateArtifact(
            candidate_id=f"candidate-{digest[:16]}",
            task_request_id=task.task_request_id,
            baseline_revision=task.baseline_revision,
            patch_text=patch_text,
            sha256=digest,
        )
# ---------------------------------------------------------------------
# DETERMINISTIC X1 EVIDENCE COLLECTOR
# ---------------------------------------------------------------------
class DeterministicX1EvidenceCollector:
    """
    Produce heterogeneous deterministic evidence for the B4 PASS path.
    This collector intentionally models FOUR distinct evidence categories.
    It does NOT claim that these four checks are sufficient for production
    release gating.
    The purpose is to verify that:
        evidence can be generated;
        evidence can be candidate-bound;
        evidence can be persisted;
        gate policy can consume heterogeneous evidence.
    Component 3 remains the owner of the full production release-gating
    architecture, including evidence planning, diversity mapping, generated
    tests, static analysis, mutation/adversarial analysis, and uncertainty.
    """
    EXPECTED_PATCH: Final[str] = (
        "--- a/src/calculator.py\n"
        "+++ b/src/calculator.py\n"
        "@@\n"
        "-    return a - b\n"
        "+    return a + b\n"
    )
    def collect(
        self,
        candidate: CandidateArtifact,
        specification: TaskSpecification,
    ) -> tuple[EvidenceArtifact, ...]:
        if candidate.sha256 != _sha256_text(candidate.patch_text):
            raise ValueError(
                "Candidate content hash does not match candidate bytes."
            )
        if specification.task_type != X1_TASK_TYPE:
            raise ValueError(
                "X1 evidence collector received non-X1 specification."
            )
        expected_patch_present = (
            candidate.patch_text == self.EXPECTED_PATCH
        )
        checks = (
            (
                "syntax",
                expected_patch_present,
                "Candidate patch has the expected syntactically valid "
                "X1 replacement form.",
            ),
            (
                "existing_tests",
                expected_patch_present,
                "Deterministic X1 regression fixture remains satisfied.",
            ),
            (
                "x1_acceptance",
                expected_patch_present,
                "Acceptance property verified: the X1 implementation "
                "performs integer addition rather than subtraction.",
            ),
            (
                "mutation_probe",
                expected_patch_present,
                "Known X1 subtraction mutant is distinguishable from "
                "the accepted addition behavior.",
            ),
        )
        artifacts: list[EvidenceArtifact] = []
        for evidence_type, passed, details in checks:
            payload = (
                f"{candidate.sha256}|"
                f"{evidence_type}|"
                f"{passed}|"
                f"{details}"
            )
            digest = _sha256_text(payload)
            artifacts.append(
                EvidenceArtifact(
                    evidence_id=f"evidence-{digest[:16]}",
                    candidate_id=candidate.candidate_id,
                    evidence_type=evidence_type,
                    passed=passed,
                    details=details,
                    sha256=digest,
                )
            )
        return tuple(artifacts)
# ---------------------------------------------------------------------
# DETERMINISTIC RELEASE GATE
# ---------------------------------------------------------------------
class DeterministicX1ReleaseGateService:
    """
    B4 integration implementation of the release-gate boundary.
    The full Component 3 remains richer than this class.
    This B4 gate intentionally verifies the architectural invariants that are
    most important for the first end-to-end software test:
        1. decision is candidate-bound;
        2. all required evidence classes must exist;
        3. decisive failing evidence produces FAIL;
        4. missing evidence produces HUMAN_REVIEW_REQUIRED;
        5. complete passing evidence produces PASS;
        6. the gate decision itself is persisted.
    Notice what is NOT done:
        - no LLM declares PASS;
        - no weighted "AI confidence score" determines release;
        - no hidden benchmark oracle is available;
        - no human is secretly called from inside the gate;
        - no candidate is repaired inside the gate.
    Those boundaries are intentional.
    """
    def __init__(
        self,
        *,
        evidence_repository: InMemoryEvidenceRepository,
        evidence_collector: DeterministicX1EvidenceCollector,
    ) -> None:
        self._evidence_repository = evidence_repository
        self._evidence_collector = evidence_collector
    def evaluate(
        self,
        candidate: CandidateArtifact,
        specification: TaskSpecification,
    ) -> GateDecision:
        evidence = self._evidence_collector.collect(
            candidate,
            specification,
        )
        for artifact in evidence:
            self._evidence_repository.save_evidence(artifact)
        by_type = {
            artifact.evidence_type: artifact
            for artifact in evidence
        }
        missing = tuple(
            required
            for required in specification.required_evidence
            if required not in by_type
        )
        if missing:
            outcome = GateOutcome.HUMAN_REVIEW_REQUIRED
            reasons = tuple(
                f"missing_required_evidence:{item}"
                for item in missing
            )
        else:
            failing = tuple(
                evidence_type
                for evidence_type in specification.required_evidence
                if not by_type[evidence_type].passed
            )
            if failing:
                outcome = GateOutcome.FAIL
                reasons = tuple(
                    f"required_evidence_failed:{item}"
                    for item in failing
                )
            else:
                outcome = GateOutcome.PASS
                reasons = ("all_required_x1_evidence_passed",)
        evidence_ids = tuple(
            artifact.evidence_id
            for artifact in evidence
        )
        decision_material = (
            candidate.candidate_id
            + "|"
            + candidate.sha256
            + "|"
            + outcome.value
            + "|"
            + "|".join(reasons)
            + "|"
            + "|".join(evidence_ids)
        )
        decision_digest = _sha256_text(decision_material)
        decision = GateDecision(
            decision_id=f"gate-{decision_digest[:16]}",
            candidate_id=candidate.candidate_id,
            candidate_sha256=candidate.sha256,
            outcome=outcome,
            reason_codes=reasons,
            evidence_ids=evidence_ids,
        )
        self._evidence_repository.save_gate_decision(decision)
        return decision
# ---------------------------------------------------------------------
# WORKFLOW PUBLICATION
# ---------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class WorkflowPublication:
    run_id: str
    task_request_id: str
    candidate_id: str
    gate_outcome: GateOutcome
    final_state: RunState
class InMemoryWorkflowPublisher:
    """
    Deterministic Component-12-side test adapter.
    The real Azure DevOps adapter should publish candidate-bound status to the
    external engineering workflow.
    This in-memory implementation records publications so the E2E test can
    prove that orchestration routed the result correctly.
    It intentionally does NOT pretend to prove Azure DevOps connectivity.
    """
    def __init__(self) -> None:
        self._publications: list[WorkflowPublication] = []
    def publish(
        self,
        publication: WorkflowPublication,
    ) -> None:
        self._publications.append(publication)
    @property
    def publications(self) -> tuple[WorkflowPublication, ...]:
        return tuple(self._publications)
# ---------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------
class X1PocOrchestrator:
    """
    Deterministic orchestration for the first X1 vertical slice.
    The orchestrator coordinates components.
    It does NOT decide whether code is correct.
    Specifically:
        ChangeExecutionService
            produces the candidate.
        ReleaseGateService
            produces the technical gate decision.
        Orchestrator
            maps that decision into lifecycle state.
    This distinction prevents workflow control and assurance semantics from
    becoming tangled.
    """
    def __init__(
        self,
        *,
        capability_registry: LocalCapabilityRegistry,
        change_execution_service: DeterministicX1ChangeExecutionService,
        release_gate_service: DeterministicX1ReleaseGateService,
        workflow_publisher: InMemoryWorkflowPublisher,
    ) -> None:
        self._capability_registry = capability_registry
        self._change_execution_service = change_execution_service
        self._release_gate_service = release_gate_service
        self._workflow_publisher = workflow_publisher
    def run(
        self,
        task: TaskRequest,
    ) -> OrchestrationResult:
        run_id = f"run-{uuid4()}"
        specification = self._capability_registry.resolve(
            task.task_type
        )
        candidate = self._change_execution_service.execute(
            task,
            specification,
        )
        decision = self._release_gate_service.evaluate(
            candidate,
            specification,
        )
        # The mapping below is intentionally deterministic.
        #
        # An LLM must not invent workflow transitions.
        #
        # If a future GateOutcome is introduced, this code should fail
        # explicitly until orchestration semantics are intentionally updated.
        if decision.outcome == GateOutcome.PASS:
            final_state = RunState.READY_FOR_RELEASE
        elif decision.outcome == GateOutcome.FAIL:
            final_state = RunState.FAILED_GATE
        elif (
            decision.outcome
            == GateOutcome.HUMAN_REVIEW_REQUIRED
        ):
            final_state = RunState.HUMAN_REVIEW_REQUIRED
        else:
            raise RuntimeError(
                "Unsupported GateOutcome encountered. "
                "Update deterministic orchestration policy."
            )
        result = OrchestrationResult(
            run_id=run_id,
            task_request_id=task.task_request_id,
            candidate=candidate,
            gate_decision=decision,
            final_state=final_state,
        )
        self._workflow_publisher.publish(
            WorkflowPublication(
                run_id=result.run_id,
                task_request_id=result.task_request_id,
                candidate_id=candidate.candidate_id,
                gate_outcome=decision.outcome,
                final_state=final_state,
            )
        )
        return result
# ---------------------------------------------------------------------
# COMPOSED APPLICATION
# ---------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class X1PocApplication:
    """
    Object graph returned by the composition root.
    Tests intentionally receive the composed application rather than
    constructing internal dependencies themselves.
    This gives B4 one authoritative wiring location.
    """
    settings: PlatformSettings
    orchestrator: X1PocOrchestrator
    evidence_repository: InMemoryEvidenceRepository
    workflow_publisher: InMemoryWorkflowPublisher
def build_local_x1_poc(
    settings: PlatformSettings | None = None,
) -> X1PocApplication:
    """
    Build the complete deterministic local X1 POC object graph.
    This is the primary B4 composition root.
    No component below reaches back into this function or uses a global
    service locator.
    Dependencies flow explicitly through constructors.
    """
    resolved_settings = settings or PlatformSettings(
        runtime_mode=RuntimeMode.LOCAL,
        service_name="l1-engineering-automation",
        environment_name="local-e2e",
        evidence_namespace="x1-e2e",
    )
    if resolved_settings.runtime_mode != RuntimeMode.LOCAL:
        raise ValueError(
            "build_local_x1_poc requires RuntimeMode.LOCAL."
        )
    evidence_repository = InMemoryEvidenceRepository()
    capability_registry = LocalCapabilityRegistry(
        specifications=(X1_SPECIFICATION,)
    )
    change_execution_service = (
        DeterministicX1ChangeExecutionService()
    )
    evidence_collector = DeterministicX1EvidenceCollector()
    release_gate_service = DeterministicX1ReleaseGateService(
        evidence_repository=evidence_repository,
        evidence_collector=evidence_collector,
    )
    workflow_publisher = InMemoryWorkflowPublisher()
    orchestrator = X1PocOrchestrator(
        capability_registry=capability_registry,
        change_execution_service=change_execution_service,
        release_gate_service=release_gate_service,
        workflow_publisher=workflow_publisher,
    )
    return X1PocApplication(
        settings=resolved_settings,
        orchestrator=orchestrator,
        evidence_repository=evidence_repository,
        workflow_publisher=workflow_publisher,
    )
def build_azure_x1_poc(
    settings: PlatformSettings,
) -> X1PocApplication:
    """
    Build the Azure POC composition.
    NOT IMPLEMENTED IN B4.
    This is intentionally explicit.
    A responsible Azure implementation requires the final enterprise-specific
    choices documented in B2, including at minimum:
        - Azure subscription/resource layout;
        - managed-identity assignments;
        - Container Apps Job resource identifiers;
        - evidence-storage account/container;
        - approved Azure DevOps organization/project/repository;
        - model deployment identifiers;
        - network restrictions;
        - secret/credential policy;
        - enterprise retention requirements.
    Returning the local implementation from this function would be dangerous
    because callers could believe they were exercising Azure controls when
    they were not.
    See NOT-IMPLEMENTED.md for the production implementation plan.
    """
    if settings.runtime_mode != RuntimeMode.AZURE_POC:
        raise ValueError(
            "build_azure_x1_poc requires RuntimeMode.AZURE_POC."
        )
    raise NotImplementedError(
        "Azure X1 composition requires the enterprise-approved Azure "
        "resource, identity, network, evidence-retention, model, and "
        "Azure DevOps configuration documented in NOT-IMPLEMENTED.md. "
        "B4 deliberately does not fabricate those values."
    )
def build_application(
    settings: PlatformSettings | None = None,
) -> X1PocApplication:
    """
    Public bootstrap entry point.
    Runtime selection happens HERE rather than throughout domain code.
    This keeps Azure-specific branching out of ChangeExecutionService,
    ReleaseGateService, and orchestration policy.
    """
    resolved_settings = (
        settings
        if settings is not None
        else PlatformSettings.from_environment()
    )
    if resolved_settings.runtime_mode == RuntimeMode.LOCAL:
        return build_local_x1_poc(resolved_settings)
    if resolved_settings.runtime_mode == RuntimeMode.AZURE_POC:
        return build_azure_x1_poc(resolved_settings)
    # RuntimeMode is currently exhaustive, but keeping an explicit terminal
    # failure protects this function if the enum is expanded later without
    # corresponding composition logic.
    raise RuntimeError(
        f"No composition is defined for runtime mode "
        f"{resolved_settings.runtime_mode!r}."
    )

