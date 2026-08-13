"""
First deterministic end-to-end test for the X1 POC.
WHAT THIS TEST PROVES
---------------------
This test verifies one complete software path:
    TaskRequest
        ↓
    CapabilityRegistry
        ↓
    ChangeExecutionService
        ↓
    CandidateArtifact
        ↓
    ReleaseGateService
        ↓
    EvidenceRepository
        ↓
    GateDecision
        ↓
    Orchestrator
        ↓
    WorkflowPublisher
It also explicitly tests several assurance invariants.
WHAT THIS TEST DOES NOT PROVE
-----------------------------
It does NOT prove that:
    - an LLM reliably performs X1;
    - generated tests are sufficiently diverse;
    - the Evidence Diversity Mapper improves detection;
    - production gate thresholds are calibrated;
    - Azure Container Apps provides the required enterprise isolation;
    - Azure DevOps integration works;
    - the false-release rate is acceptable;
    - synthetic benchmark performance transfers to real L1 work.
Those questions belong to:
    integration tests
    +
    Component 5 evaluation campaigns
    +
    enterprise security/platform validation.
This separation prevents a green pytest result from being mistaken for
evidence that the AI capability itself is qualified.
"""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
import pytest
from l1_automation.bootstrap.settings import (
    PlatformSettings,
    RuntimeMode,
)
from l1_automation.bootstrap.x1_poc import (
    CandidateArtifact,
    DeterministicX1EvidenceCollector,
    DeterministicX1ReleaseGateService,
    GateOutcome,
    InMemoryEvidenceRepository,
    RunState,
    TaskRequest,
    X1_SPECIFICATION,
    build_application,
    build_azure_x1_poc,
)
def sha256_text(value: str) -> str:
    """Test-side digest helper used to independently verify artifact identity."""
    return sha256(value.encode("utf-8")).hexdigest()
@pytest.fixture
def local_settings() -> PlatformSettings:
    """
    Explicit local configuration.
    Do not let this test inherit developer-machine environment variables.
    E2E software tests should be deterministic and self-contained.
    """
    return PlatformSettings(
        runtime_mode=RuntimeMode.LOCAL,
        service_name="l1-engineering-automation-test",
        environment_name="pytest",
        evidence_namespace="x1-e2e-test",
    )
@pytest.fixture
def x1_task() -> TaskRequest:
    """
    Narrow X1 task used by the first vertical slice.
    The task is deliberately simple enough to possess a clear deterministic
    oracle:
        incorrect baseline:
            a - b
        requested behavior:
            a + b
    The simplicity is intentional. The first E2E test is testing architecture,
    not attempting to demonstrate the maximum complexity of an AI coding
    agent.
    """
    return TaskRequest(
        task_request_id="task-x1-e2e-001",
        task_type="X1",
        repository_id="synthetic/x1-calculator",
        baseline_revision="baseline-x1-v1",
        instruction=(
            "Correct the integer addition function in "
            "src/calculator.py so that it returns a + b rather "
            "than a - b. Do not modify other files."
        ),
    )
def test_x1_end_to_end_pass_path(
    local_settings: PlatformSettings,
    x1_task: TaskRequest,
) -> None:
    """
    Execute the complete deterministic X1 PASS path.
    This is the central B4 test.
    """
    application = build_application(local_settings)
    result = application.orchestrator.run(x1_task)
    # -------------------------------------------------------------
    # ASSERTION 1 — task/run correlation survives orchestration.
    # -------------------------------------------------------------
    assert result.task_request_id == x1_task.task_request_id
    assert result.run_id.startswith("run-")
    # -------------------------------------------------------------
    # ASSERTION 2 — a real immutable candidate artifact exists.
    # -------------------------------------------------------------
    candidate = result.candidate
    assert candidate.task_request_id == x1_task.task_request_id
    assert candidate.baseline_revision == (
        x1_task.baseline_revision
    )
    assert candidate.patch_text
    # Independently recompute the digest rather than merely checking that
    # the field is non-empty. This protects the candidate-binding invariant.
    assert candidate.sha256 == sha256_text(
        candidate.patch_text
    )
    # -------------------------------------------------------------
    # ASSERTION 3 — gate decision is bound to EXACT candidate.
    # -------------------------------------------------------------
    decision = result.gate_decision
    assert decision.candidate_id == candidate.candidate_id
    assert decision.candidate_sha256 == candidate.sha256
    # -------------------------------------------------------------
    # ASSERTION 4 — required heterogeneous evidence exists.
    # -------------------------------------------------------------
    evidence = (
        application.evidence_repository.evidence_for_candidate(
            candidate.candidate_id
        )
    )
    evidence_types = {
        artifact.evidence_type
        for artifact in evidence
    }
    assert evidence_types == set(
        X1_SPECIFICATION.required_evidence
    )
    # Every evidence artifact must refer to the same candidate.
    #
    # This guards against a subtle but dangerous implementation defect where
    # evidence from Candidate C1 could accidentally be reused for Candidate C2.
    assert all(
        artifact.candidate_id == candidate.candidate_id
        for artifact in evidence
    )
    # -------------------------------------------------------------
    # ASSERTION 5 — PASS requires all required evidence to pass.
    # -------------------------------------------------------------
    assert all(
        artifact.passed
        for artifact in evidence
    )
    assert decision.outcome == GateOutcome.PASS
    assert decision.reason_codes == (
        "all_required_x1_evidence_passed",
    )
    # -------------------------------------------------------------
    # ASSERTION 6 — deterministic orchestration maps PASS correctly.
    # -------------------------------------------------------------
    assert result.final_state == RunState.READY_FOR_RELEASE
    # IMPORTANT:
    #
    # READY_FOR_RELEASE means the technical gate permits progression.
    #
    # It does NOT mean "autonomously deployed to production."
    #
    # Organizational release approval remains external to this B4 slice.
    # -------------------------------------------------------------
    # ASSERTION 7 — decision was persisted.
    # -------------------------------------------------------------
    persisted_decision = (
        application.evidence_repository.get_gate_decision(
            decision.decision_id
        )
    )
    assert persisted_decision == decision
    # -------------------------------------------------------------
    # ASSERTION 8 — workflow receives candidate-bound result.
    # -------------------------------------------------------------
    publications = application.workflow_publisher.publications
    assert len(publications) == 1
    publication = publications[0]
    assert publication.run_id == result.run_id
    assert publication.task_request_id == (
        x1_task.task_request_id
    )
    assert publication.candidate_id == candidate.candidate_id
    assert publication.gate_outcome == GateOutcome.PASS
    assert publication.final_state == (
        RunState.READY_FOR_RELEASE
    )
def test_modified_candidate_invalidates_previous_candidate_binding(
    local_settings: PlatformSettings,
    x1_task: TaskRequest,
) -> None:
    """
    Protect one of the repository's most important invariants:
        a gate decision applies to an exact candidate.
    If candidate bytes change, the old PASS cannot be treated as approval for
    the modified candidate.
    """
    application = build_application(local_settings)
    result = application.orchestrator.run(x1_task)
    original = result.candidate
    original_decision = result.gate_decision
    modified_patch = (
        original.patch_text
        + "\n# unauthorized post-gate modification\n"
    )
    modified_digest = sha256_text(modified_patch)
    modified = CandidateArtifact(
        candidate_id=f"candidate-{modified_digest[:16]}",
        task_request_id=original.task_request_id,
        baseline_revision=original.baseline_revision,
        patch_text=modified_patch,
        sha256=modified_digest,
    )
    assert modified.sha256 != original.sha256
    assert modified.candidate_id != original.candidate_id
    # The old gate decision remains a historical fact about the ORIGINAL
    # candidate. It must not magically change identity.
    assert original_decision.candidate_id == (
        original.candidate_id
    )
    assert original_decision.candidate_sha256 == (
        original.sha256
    )
    assert original_decision.candidate_sha256 != (
        modified.sha256
    )
def test_gate_fails_candidate_with_decisive_negative_evidence() -> None:
    """
    Demonstrate failure dominance.
    A candidate containing the original incorrect subtraction implementation
    should not be rescued by averaging or by an AI confidence score.
    Required deterministic evidence fails, therefore the gate returns FAIL.
    """
    repository = InMemoryEvidenceRepository()
    gate = DeterministicX1ReleaseGateService(
        evidence_repository=repository,
        evidence_collector=DeterministicX1EvidenceCollector(),
    )
    incorrect_patch = (
        "--- a/src/calculator.py\n"
        "+++ b/src/calculator.py\n"
        "@@\n"
        "-    return a - b\n"
        "+    return a - b\n"
    )
    digest = sha256_text(incorrect_patch)
    candidate = CandidateArtifact(
        candidate_id=f"candidate-{digest[:16]}",
        task_request_id="task-negative-x1",
        baseline_revision="baseline-x1-v1",
        patch_text=incorrect_patch,
        sha256=digest,
    )
    decision = gate.evaluate(
        candidate,
        X1_SPECIFICATION,
    )
    assert decision.outcome == GateOutcome.FAIL
    assert decision.reason_codes
    assert all(
        reason.startswith("required_evidence_failed:")
        for reason in decision.reason_codes
    )
def test_candidate_hash_mismatch_fails_closed() -> None:
    """
    The gate must not evaluate bytes whose declared identity is incorrect.
    This is an integrity check, not a correctness check.
    """
    repository = InMemoryEvidenceRepository()
    gate = DeterministicX1ReleaseGateService(
        evidence_repository=repository,
        evidence_collector=DeterministicX1EvidenceCollector(),
    )
    candidate = CandidateArtifact(
        candidate_id="candidate-corrupted",
        task_request_id="task-corrupted",
        baseline_revision="baseline-x1-v1",
        patch_text="unexpected bytes",
        sha256="0" * 64,
    )
    with pytest.raises(
        ValueError,
        match="Candidate content hash",
    ):
        gate.evaluate(
            candidate,
            X1_SPECIFICATION,
        )
def test_unknown_capability_fails_closed(
    local_settings: PlatformSettings,
) -> None:
    """
    The orchestrator must not improvise behavior for an unapproved task type.
    X2 is intentionally not registered in this POC.
    """
    application = build_application(local_settings)
    unknown_task = TaskRequest(
        task_request_id="task-x2-unapproved",
        task_type="X2",
        repository_id="synthetic/unknown",
        baseline_revision="baseline",
        instruction="Perform an unregistered task.",
    )
    with pytest.raises(
        ValueError,
        match="not an approved capability",
    ):
        application.orchestrator.run(unknown_task)
def test_azure_composition_fails_explicitly_until_enterprise_inputs_exist(
) -> None:
    """
    Protect against accidental fake-Azure execution.
    B4 must not silently return local adapters when AZURE_POC was requested.
    When the enterprise-approved Azure adapters are implemented, this test
    should be replaced by genuine Azure integration tests rather than simply
    deleted.
    """
    settings = PlatformSettings(
        runtime_mode=RuntimeMode.AZURE_POC,
        service_name="l1-engineering-automation",
        environment_name="azure-poc",
        evidence_namespace="x1-poc",
    )
    with pytest.raises(
        NotImplementedError,
        match="enterprise-approved Azure",
    ):
        build_azure_x1_poc(settings)

