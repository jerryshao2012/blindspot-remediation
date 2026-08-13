from __future__ import annotations

from pathlib import Path

import pytest
from ai_engineering_contracts import (
    ArtifactKind,
    GateDecision,
)

from ai_engineering_release_gate.models import GateRuntimeSettings
from ai_engineering_release_gate.service import ReleaseGateService


@pytest.mark.asyncio
async def test_service_passes_valid_candidate(
    gate_execution_request,
    tmp_path: Path,
) -> None:
    service = ReleaseGateService(
        settings=GateRuntimeSettings(
            artifact_root=tmp_path / "gate-artifacts",
        )
    )
    result = await service.evaluate(gate_execution_request)
    assert result.decision == GateDecision.PASS
    assert result.evidence_package.kind == ArtifactKind.EVIDENCE_PACKAGE
    assert result.token_usage.llm_calls == 0
    assert result.generated_tests_considered == 0
    assert result.mutants_generated == 0
    assert result.metadata["candidate_tree"]
    assert any(
        item.control_id == "candidate-integrity"
        and item.status.value == "passed"
        for item in result.hard_control_results
    )
    assert any(
        item.control_id == "compile"
        and item.status.value == "passed"
        for item in result.hard_control_results
    )


@pytest.mark.asyncio
async def test_service_returns_fail_for_scope_violation(
    gate_execution_request,
    tmp_path: Path,
) -> None:
    request = gate_execution_request
    repository_url = request.gate_request.repository_url
    # Replace the requirement contract with one that does not permit
    # calculator.py. The candidate patch is therefore an authoritative
    # scope violation.
    requirement_path = tmp_path / "restrictive-requirement.yaml"
    requirement_path.write_text(
        """
version: "1.0.0"
task_type: "X1-test"
title: "Restrictive test task"
task_description: "No calculator source change is authorized."
acceptance_criteria:
  - "Only documentation files may change."
permitted_paths:
  - "docs/**"
prohibited_paths:
  - "calculator.py"
metadata: {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    import hashlib

    from ai_engineering_contracts import ArtifactReference

    content = requirement_path.read_bytes()
    replacement_requirement = ArtifactReference(
        artifact_id="restrictive-requirement",
        kind=ArtifactKind.REQUIREMENT_CONTRACT,
        uri=requirement_path.resolve().as_uri(),
        sha256=hashlib.sha256(content).hexdigest(),
        media_type="application/yaml",
        size_bytes=len(content),
        immutable=True,
    )
    modified_gate_request = request.gate_request.model_copy(
        update={
            "repository_url": repository_url,
            "requirement_contract": replacement_requirement,
        }
    )
    modified_request = request.model_copy(
        update={"gate_request": modified_gate_request}
    )
    result = await ReleaseGateService(
        settings=GateRuntimeSettings(
            artifact_root=tmp_path / "gate-artifacts",
        )
    ).evaluate(modified_request)
    assert result.decision == GateDecision.FAIL
    assert any(
        item.control_id == "change-scope"
        and item.severity.value == "dominant_failure"
        for item in result.hard_control_results
    )


@pytest.mark.asyncio
async def test_service_fails_when_mandatory_command_fails(
    gate_execution_request,
    tmp_path: Path,
) -> None:
    request = gate_execution_request
    evaluation_path = tmp_path / "failing-evaluation.yaml"
    evaluation_path.write_text(
        """
version: "1.0.0"
task_type: "X1-test"
controls:
  - control_id: "mandatory-failure"
    name: "Mandatory failure"
    description: "A deliberately failing control."
    command:
      - "python"
      - "-c"
      - "raise SystemExit(9)"
    timeout_seconds: 60
    working_directory: "."
    environment: {}
    severity: "mandatory"
    strategy: "compilation"
    expected_exit_codes:
      - 0
    reports: []
    continue_after_failure: true
metadata: {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    import hashlib

    from ai_engineering_contracts import ArtifactReference

    content = evaluation_path.read_bytes()
    replacement_evaluation = ArtifactReference(
        artifact_id="failing-evaluation",
        kind=ArtifactKind.EVALUATION_SPECIFICATION,
        uri=evaluation_path.resolve().as_uri(),
        sha256=hashlib.sha256(content).hexdigest(),
        media_type="application/yaml",
        size_bytes=len(content),
        immutable=True,
    )
    modified_gate_request = request.gate_request.model_copy(
        update={"evaluation_specification": replacement_evaluation}
    )
    modified_request = request.model_copy(
        update={"gate_request": modified_gate_request}
    )
    result = await ReleaseGateService(
        settings=GateRuntimeSettings(
            artifact_root=tmp_path / "gate-artifacts",
        )
    ).evaluate(modified_request)
    assert result.decision == GateDecision.FAIL
    assert any(
        item.control_id == "mandatory-failure"
        and item.status.value == "failed"
        for item in result.hard_control_results
    )
