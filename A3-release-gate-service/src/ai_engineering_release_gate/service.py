"""
Public ReleaseGateService façade.

Workflow
--------
validate immutable inputs
    ↓
load requirement, evaluation, and policy documents
    ↓
verify task and version consistency
    ↓
create clean repository clone at the exact base commit
    ↓
reconstruct candidate from immutable normalized patch
    ↓
perform authoritative path-scope validation
    ↓
run deterministic controls
    ↓
parse and normalize evidence
    ↓
apply deterministic policy
    ↓
write immutable evidence package and trace
    ↓
return GateResult

The service does not merge or deploy code.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_engineering_contracts import (
    ArtifactKind,
    CheckStatus,
    ControlResult,
    ControlSeverity,
    EvidenceStrategy,
    GateResult,
    TokenUsage,
)

from .artifacts import LocalArtifactLoader, LocalArtifactStore
from .errors import (
    CandidateIntegrityError,
    ReleaseGateError,
    ScopeViolationError,
)
from .evidence import (
    DeterministicControlRunner,
    EvidenceReportParser,
    namespace_metrics,
)
from .models import (
    DeterministicGateExecutionRequest,
    EvaluationSpecification,
    GateRuntimeSettings,
    ReleasePolicy,
    RequirementContract,
)
from .policy import GatePolicyEngine
from .process import CommandRunner, GateBudgetTracker
from .tracing import GateTraceRecorder
from .workspace import GateWorkspace


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReleaseGateService:
    """
    Produce authoritative evidence and a deterministic gate recommendation.

    Responsibilities
    ----------------
    * Verify candidate-patch identity and integrity.
    * Reconstruct the candidate in a clean repository clone.
    * Run authoritative deterministic controls.
    * Normalize reports and metrics.
    * Apply a versioned deterministic release policy.
    * Preserve evidence and decision provenance.

    Explicit non-responsibilities
    -----------------------------
    * Trust executor-local checks as release evidence.
    * Generate tests with AI.
    * Access hidden benchmark oracles.
    * Ask a human to work inside the gate.
    * Merge, release, or deploy code.
    """

    GATE_VERSION = "0.1.0"

    def __init__(
        self,
        *,
        settings: GateRuntimeSettings,
        artifact_loader: LocalArtifactLoader | None = None,
        artifact_store: LocalArtifactStore | None = None,
        policy_engine: GatePolicyEngine | None = None,
    ) -> None:
        self._settings = settings
        self._artifact_loader = artifact_loader or LocalArtifactLoader()
        self._artifact_store = artifact_store or LocalArtifactStore(
            settings.artifact_root
        )
        self._policy_engine = policy_engine or GatePolicyEngine()

    async def evaluate(
        self,
        request: DeterministicGateExecutionRequest,
    ) -> GateResult:
        started_at = utc_now()
        gate_request = request.gate_request
        trace = GateTraceRecorder(gate_request.run_id)
        trace.record(
            "gate_started",
            "Deterministic release gate started.",
            gate_version=self.GATE_VERSION,
            configured_gate_version=gate_request.gate_version,
            task_type=gate_request.task_type,
            base_commit=gate_request.base_commit,
            candidate_commit=gate_request.candidate_commit,
            candidate_patch_sha256=request.candidate_patch.sha256,
        )
        self._validate_gate_version(request)
        requirement = self._load_model(
            gate_request.requirement_contract,
            RequirementContract,
        )
        evaluation = self._load_model(
            gate_request.evaluation_specification,
            EvaluationSpecification,
        )
        policy = self._load_model(
            gate_request.release_policy,
            ReleasePolicy,
        )
        self._validate_document_consistency(
            request=request,
            requirement=requirement,
            evaluation=evaluation,
            policy=policy,
        )
        patch_bytes = self._artifact_loader.read_bytes(
            request.candidate_patch
        )
        budget = GateBudgetTracker(
            maximum_tool_calls=gate_request.evidence_budget.maximum_tool_calls,
            maximum_runtime_seconds=(
                gate_request.evidence_budget.maximum_runtime_seconds
            ),
        )
        command_runner = CommandRunner(
            budget=budget,
            maximum_captured_output_bytes=(
                self._settings.maximum_captured_output_bytes
            ),
        )
        controls: list[ControlResult] = []
        candidate_tree = ""
        changed_files: list[str] = []
        with tempfile.TemporaryDirectory(
            prefix=f"release-gate-{gate_request.run_id}-"
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            patch_path = temporary_root / "candidate.patch"
            patch_path.write_bytes(patch_bytes)
            workspace = GateWorkspace(
                root=temporary_root / "workspace",
                git_executable=self._settings.git_executable,
                command_runner=command_runner,
                trace=trace,
            )
            try:
                workspace.initialize(
                    repository_url=gate_request.repository_url,
                    base_commit=gate_request.base_commit,
                )
                changed_files = workspace.reconstruct_candidate(patch_path)
                candidate_tree = workspace.candidate_tree
                controls.append(
                    self._passed_builtin_control(
                        control_id="candidate-integrity",
                        name="Candidate integrity",
                        summary=(
                            "Candidate patch digest and commit metadata were "
                            "validated, and the patch was reconstructed from the "
                            "exact base commit."
                        ),
                        strategy=EvidenceStrategy.COMPILATION,
                        metrics={
                            "changed_files": float(len(changed_files)),
                        },
                    )
                )
                workspace.validate_scope(
                    changed_files=changed_files,
                    permitted_paths=requirement.permitted_paths,
                    prohibited_paths=requirement.prohibited_paths,
                )
                controls.append(
                    self._passed_builtin_control(
                        control_id="change-scope",
                        name="Authorized change scope",
                        summary=(
                            "All changed files are permitted by the requirement "
                            "contract and none match a prohibited path."
                        ),
                        strategy=EvidenceStrategy.STATIC_ANALYSIS,
                        metrics={
                            "changed_files": float(len(changed_files)),
                            "scope_violations": 0.0,
                        },
                    )
                )
            except ScopeViolationError as exc:
                controls.append(
                    self._failed_builtin_control(
                        control_id="change-scope",
                        name="Authorized change scope",
                        summary=str(exc),
                        strategy=EvidenceStrategy.STATIC_ANALYSIS,
                        severity=ControlSeverity.DOMINANT_FAILURE,
                        metrics={"scope_violations": 1.0},
                    )
                )
            except ReleaseGateError as exc:
                controls.append(
                    self._failed_builtin_control(
                        control_id="candidate-integrity",
                        name="Candidate integrity",
                        summary=str(exc),
                        strategy=EvidenceStrategy.COMPILATION,
                        severity=ControlSeverity.DOMINANT_FAILURE,
                        metrics={"candidate_integrity_failure": 1.0},
                    )
                )
            dominant_failure = any(
                control.severity == ControlSeverity.DOMINANT_FAILURE
                and control.status in {CheckStatus.FAILED, CheckStatus.ERROR}
                for control in controls
            )
            if not dominant_failure:
                control_runner = DeterministicControlRunner(
                    command_runner=command_runner,
                    artifact_store=self._artifact_store,
                    report_parser=EvidenceReportParser(),
                    trace=trace,
                )
                for specification in evaluation.controls:
                    result = control_runner.run_control(
                        run_id=gate_request.run_id,
                        specification=specification,
                        workspace=workspace,
                    )
                    controls.append(result)
                    if (
                        result.status in {
                            CheckStatus.FAILED,
                            CheckStatus.ERROR,
                        }
                        and not specification.continue_after_failure
                    ):
                        trace.record(
                            "control_sequence_stopped",
                            "Control sequence stopped after configured failure.",
                            control_id=specification.control_id,
                        )
                        break
        try:
            metrics = namespace_metrics(controls)
        except ReleaseGateError as exc:
            controls.append(
                self._failed_builtin_control(
                    control_id="evidence-normalization",
                    name="Evidence normalization",
                    summary=str(exc),
                    strategy=EvidenceStrategy.STATIC_ANALYSIS,
                    severity=ControlSeverity.MANDATORY,
                    metrics={"normalization_failure": 1.0},
                )
            )
            metrics = namespace_metrics(
                [
                    control
                    for control in controls
                    if control.control_id != "evidence-normalization"
                ]
            )
        decision = self._policy_engine.decide(
            controls=controls,
            metrics=metrics,
            policy=policy,
        )
        trace.record(
            "gate_decision",
            "Deterministic release policy produced a gate recommendation.",
            decision=decision.decision.value,
            reasons=list(decision.reasons),
            deterministic_tool_calls=budget.tool_calls,
        )
        evidence_payload: dict[str, Any] = {
            "evidence_package_version": "1.0.0",
            "run_id": gate_request.run_id,
            "gate_version": self.GATE_VERSION,
            "policy_version": policy.version,
            "evaluation_specification_version": evaluation.version,
            "requirement_contract_version": requirement.version,
            "task_type": gate_request.task_type,
            "base_commit": gate_request.base_commit,
            "candidate_commit": gate_request.candidate_commit,
            "candidate_patch": request.candidate_patch.to_json_compatible_dict(),
            "candidate_tree": candidate_tree or None,
            "changed_files": changed_files,
            "controls": [
                control.to_json_compatible_dict()
                for control in controls
            ],
            "metrics": metrics,
            "decision": decision.decision.value,
            "decision_reasons": list(decision.reasons),
            "unmet_obligations": list(decision.unmet_obligations),
            "contradictions": list(decision.contradictions),
            "deterministic_tool_calls": budget.tool_calls,
            "llm_usage": {
                "llm_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "estimated_cost": 0.0,
            },
        }
        evidence_artifact = self._artifact_store.store_json(
            run_id=gate_request.run_id,
            filename="evidence-package.json",
            kind=ArtifactKind.EVIDENCE_PACKAGE,
            payload=evidence_payload,
            metadata={
                "gate_version": self.GATE_VERSION,
                "policy_version": policy.version,
                "candidate_commit": gate_request.candidate_commit,
                "candidate_tree": candidate_tree,
                "decision": decision.decision.value,
            },
        )
        trace_artifact = self._artifact_store.store_json(
            run_id=gate_request.run_id,
            filename="gate-trace.json",
            kind=ArtifactKind.OTHER,
            payload=trace.to_payload(),
            metadata={
                "gate_version": self.GATE_VERSION,
                "decision": decision.decision.value,
            },
        )
        return GateResult(
            run_id=gate_request.run_id,
            gate_version=self.GATE_VERSION,
            policy_version=policy.version,
            decision=decision.decision,
            base_commit=gate_request.base_commit,
            candidate_commit=gate_request.candidate_commit,
            evidence_package=evidence_artifact,
            hard_control_results=controls,
            evidence_metrics=metrics,
            unmet_obligations=list(decision.unmet_obligations),
            contradictions=list(decision.contradictions),
            decision_reasons=list(decision.reasons),
            token_usage=TokenUsage(),
            evidence_rounds_completed=1,
            generated_tests_considered=0,
            qualified_generated_tests=0,
            mutants_generated=0,
            meaningful_mutants_survived=0,
            started_at=started_at,
            completed_at=utc_now(),
            metadata={
                "gate_mode": "deterministic_clean_room",
                "candidate_tree": candidate_tree,
                "changed_file_count": str(len(changed_files)),
                "deterministic_tool_calls": str(budget.tool_calls),
                "trace_artifact_uri": trace_artifact.uri,
            },
        )

    def _load_model(
        self,
        reference: Any,
        model_type: Any,
    ) -> Any:
        return self._artifact_loader.read_structured_model(
            reference,
            model_type,
        )

    def _validate_gate_version(
        self,
        request: DeterministicGateExecutionRequest,
    ) -> None:
        configured = request.gate_request.gate_version
        if configured != self.GATE_VERSION:
            raise CandidateIntegrityError(
                f"GateRequest requires gate version {configured}, but this "
                f"service is version {self.GATE_VERSION}."
            )

    @staticmethod
    def _validate_document_consistency(
        *,
        request: DeterministicGateExecutionRequest,
        requirement: RequirementContract,
        evaluation: EvaluationSpecification,
        policy: ReleasePolicy,
    ) -> None:
        task_type = request.gate_request.task_type
        mismatches = {
            "requirement_contract": requirement.task_type,
            "evaluation_specification": evaluation.task_type,
            "release_policy": policy.task_type,
        }
        invalid = {
            name: value
            for name, value in mismatches.items()
            if value != task_type
        }
        if invalid:
            raise CandidateIntegrityError(
                f"Task-type mismatch for GateRequest {task_type!r}: {invalid}."
            )
        if (
            request.gate_request.policy_version
            if hasattr(request.gate_request, "policy_version")
            else None
        ):
            # GateRequest from Component 1 does not currently contain a separate
            # policy_version field. The release-policy artifact and GateResult
            # carry the authoritative version instead.
            pass

    @staticmethod
    def _passed_builtin_control(
        *,
        control_id: str,
        name: str,
        summary: str,
        strategy: EvidenceStrategy,
        metrics: dict[str, float],
    ) -> ControlResult:
        now = utc_now()
        return ControlResult(
            control_id=control_id,
            name=name,
            status=CheckStatus.PASSED,
            severity=ControlSeverity.MANDATORY,
            strategy=strategy,
            deterministic_authority=True,
            summary=summary,
            started_at=now,
            completed_at=now,
            metrics=metrics,
        )

    @staticmethod
    def _failed_builtin_control(
        *,
        control_id: str,
        name: str,
        summary: str,
        strategy: EvidenceStrategy,
        severity: ControlSeverity,
        metrics: dict[str, float],
    ) -> ControlResult:
        now = utc_now()
        return ControlResult(
            control_id=control_id,
            name=name,
            status=CheckStatus.FAILED,
            severity=severity,
            strategy=strategy,
            deterministic_authority=True,
            summary=summary,
            started_at=now,
            completed_at=now,
            metrics=metrics,
            reasons=[summary],
        )
