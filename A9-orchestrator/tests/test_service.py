from datetime import datetime, timezone
from pathlib import Path

from ai_engineering_orchestrator.models import (
    CandidatePatch,
    ChangeExecutionResult,
    GateDisposition,
    ReleaseGateResult,
    TaskRequest,
)
from ai_engineering_orchestrator.ports import (
    ChangeExecutionPort,
    EvidencePort,
    ReleaseGatePort,
    ReleasePort,
)
from ai_engineering_orchestrator.registry import (
    TaskDefinitionRegistry,
)
from ai_engineering_orchestrator.service import (
    EngineeringAutomationOrchestrator,
)


NOW = datetime.now(timezone.utc)


class FakeChangeExecution(ChangeExecutionPort):
    def execute(
        self,
        *,
        run_id,
        task,
        definition,
    ):
        return ChangeExecutionResult(
            succeeded=True,
            candidate=CandidatePatch(
                candidate_id="candidate-001",
                task_id=task.task_id,
                run_id=run_id,
                base_revision=task.base_revision,
                candidate_revision="def456",
                evidence_reference="evidence://candidate",
                created_at=NOW,
            ),
            input_tokens=1000,
            output_tokens=200,
            llm_requests=2,
        )


class FakeReleaseGate(ReleaseGatePort):
    def evaluate(
        self,
        *,
        run_id,
        task,
        candidate,
        definition,
        evidence_cycle,
    ):
        return ReleaseGateResult(
            disposition=GateDisposition.PASS,
            evidence_reference="evidence://gate",
            input_tokens=2000,
            output_tokens=300,
            llm_requests=3,
            reason_codes=("ALL_REQUIRED_CHECKS_PASSED",),
        )


class FakeEvidence(EvidencePort):
    def __init__(self):
        self.counter = 0

    def record_run(self, run):
        self.counter += 1
        return f"evidence://run/{self.counter}"

    def record_outcome(self, outcome):
        return "evidence://outcome"


class FakeRelease(ReleasePort):
    def release(
        self,
        *,
        run_id,
        task,
        candidate,
    ):
        return "deployment://001"


def write_definition(
    root: Path,
    *,
    automatic_release: bool,
) -> None:
    (root / "x1.yaml").write_text(
        f"""
task_type: X1
definition_version: 1.0.0
enabled: true

skill_reference: skills/x1/1.0.0

change_execution_profile: x1-execution
release_gate_profile: x1-gate

required_evidence_types:
  - build_result
  - independent_test_result

allowed_repository_patterns:
  - engineering-poc

budget:
  maximum_execution_attempts: 2
  maximum_gate_attempts: 3
  maximum_total_llm_input_tokens: 100000
  maximum_total_llm_output_tokens: 20000
  maximum_total_llm_requests: 100
  maximum_elapsed_seconds: 3600

maximum_more_evidence_cycles: 2

automatic_release_allowed: {str(automatic_release).lower()}
""",
        encoding="utf-8",
    )


def test_successful_orchestration(
    tmp_path: Path,
) -> None:
    write_definition(
        tmp_path,
        automatic_release=True,
    )

    orchestrator = EngineeringAutomationOrchestrator(
        registry=TaskDefinitionRegistry(tmp_path),
        change_execution=FakeChangeExecution(),
        release_gate=FakeReleaseGate(),
        evidence=FakeEvidence(),
        release=FakeRelease(),
    )

    task = TaskRequest(
        task_id="X1-001",
        task_type="X1",
        title="POC engineering task",
        description="Perform the defined engineering modification.",
        repository_uri=(
            "https://example.invalid/engineering-poc"
        ),
        base_revision="abc123",
        requested_by="poc-operator",
        created_at=NOW,
    )

    outcome = orchestrator.run(task)

    assert outcome.disposition.value == "released"

    assert outcome.candidate_id == "candidate-001"

    assert outcome.usage.input_tokens == 3000

    assert outcome.usage.output_tokens == 500

    assert outcome.usage.llm_requests == 5

    assert outcome.usage.execution_attempts == 1

    assert outcome.usage.gate_attempts == 1
