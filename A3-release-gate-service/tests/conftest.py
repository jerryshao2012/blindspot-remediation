from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from ai_engineering_contracts import (
    ArtifactKind,
    ArtifactReference,
    EvidenceBudget,
    EvidenceStrategy,
    GateRequest,
)

from ai_engineering_release_gate.models import (
    DeterministicGateExecutionRequest,
)


def run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def artifact(
    path: Path,
    *,
    artifact_id: str,
    kind: ArtifactKind,
    media_type: str,
    metadata: dict[str, str] | None = None,
) -> ArtifactReference:
    content = path.read_bytes()
    return ArtifactReference(
        artifact_id=artifact_id,
        kind=kind,
        uri=path.resolve().as_uri(),
        sha256=sha256(content),
        media_type=media_type,
        size_bytes=len(content),
        immutable=True,
        metadata=metadata or {},
    )


@pytest.fixture
def source_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "source"
    repository.mkdir()
    run_git(repository, "init")
    run_git(repository, "config", "user.name", "Test Author")
    run_git(repository, "config", "user.email", "author@example.test")
    (repository / "calculator.py").write_text(
        "def add(left: int, right: int) -> int:\n"
        "    return left + right\n",
        encoding="utf-8",
    )
    (repository / "pipeline.yaml").write_text(
        "name: protected\n",
        encoding="utf-8",
    )
    run_git(repository, "add", "--all")
    run_git(repository, "commit", "-m", "Initial")
    return repository, run_git(repository, "rev-parse", "HEAD")


@pytest.fixture
def candidate_patch(
    source_repository: tuple[Path, str],
    tmp_path: Path,
) -> tuple[Path, str]:
    repository, _ = source_repository
    (repository / "calculator.py").write_text(
        "def add(left: int, right: int) -> int:\n"
        "    \"\"\"Return the sum of two integers.\"\"\"\n"
        "    return left + right\n",
        encoding="utf-8",
    )
    patch_text = run_git(
        repository,
        "diff",
        "--binary",
        "--full-index",
    )
    run_git(repository, "add", "--all")
    run_git(repository, "commit", "-m", "Candidate")
    candidate_commit = run_git(repository, "rev-parse", "HEAD")
    run_git(repository, "reset", "--hard", "HEAD~1")
    patch_path = tmp_path / "candidate.patch"
    patch_path.write_text(patch_text, encoding="utf-8")
    return patch_path, candidate_commit


def write_yaml(path: Path, content: str) -> ArtifactReference:
    path.write_text(content, encoding="utf-8")
    kind_by_name = {
        "requirement.yaml": ArtifactKind.REQUIREMENT_CONTRACT,
        "evaluation.yaml": ArtifactKind.EVALUATION_SPECIFICATION,
        "policy.yaml": ArtifactKind.RELEASE_POLICY,
    }
    return artifact(
        path,
        artifact_id=path.stem,
        kind=kind_by_name[path.name],
        media_type="application/yaml",
    )


@pytest.fixture
def gate_execution_request(
    source_repository: tuple[Path, str],
    candidate_patch: tuple[Path, str],
    tmp_path: Path,
) -> DeterministicGateExecutionRequest:
    repository, base_commit = source_repository
    patch_path, candidate_commit = candidate_patch
    requirement = write_yaml(
        tmp_path / "requirement.yaml",
        """
version: "1.0.0"
task_type: "X1-test"
title: "Test task"
task_description: "Add documentation without changing behaviour."
acceptance_criteria:
  - "The Python source compiles."
permitted_paths:
  - "calculator.py"
prohibited_paths:
  - "pipeline.yaml"
metadata: {}
""".strip()
        + "\n",
    )
    evaluation = write_yaml(
        tmp_path / "evaluation.yaml",
        """
version: "1.0.0"
task_type: "X1-test"
controls:
  - control_id: "compile"
    name: "Compile"
    description: "Compile calculator.py."
    command:
      - "python"
      - "-m"
      - "py_compile"
      - "calculator.py"
    timeout_seconds: 60
    working_directory: "."
    environment:
      PYTHONDONTWRITEBYTECODE: "1"
    severity: "mandatory"
    strategy: "compilation"
    expected_exit_codes:
      - 0
    reports: []
    continue_after_failure: true
metadata: {}
""".strip()
        + "\n",
    )
    policy = write_yaml(
        tmp_path / "policy.yaml",
        """
version: "1.0.0"
task_type: "X1-test"
fail_on_mandatory_control_failure: true
fail_on_dominant_failure: true
human_review_on_advisory_failure: true
human_review_on_warning: true
more_evidence_on_skipped_mandatory_control: true
more_evidence_on_missing_required_report: true
metric_thresholds: []
metadata: {}
""".strip()
        + "\n",
    )
    gate_request = GateRequest(
        run_id="gate-test-1",
        task_type="X1-test",
        task_package_version="1.0.0",
        gate_version="0.1.0",
        repository_url=repository.resolve().as_uri(),
        base_commit=base_commit,
        candidate_commit=candidate_commit,
        requirement_contract=requirement,
        evaluation_specification=evaluation,
        release_policy=policy,
        evidence_budget=EvidenceBudget(
            maximum_llm_calls=0,
            maximum_input_tokens=0,
            maximum_output_tokens=0,
            maximum_evidence_rounds=1,
            maximum_generated_tests=0,
            maximum_mutants=0,
            maximum_tool_calls=100,
            maximum_runtime_seconds=600,
            maximum_estimated_cost=0.0,
            allowed_strategies=[
                EvidenceStrategy.COMPILATION,
            ],
        ),
    )
    patch_reference = artifact(
        patch_path,
        artifact_id="candidate-patch",
        kind=ArtifactKind.PATCH,
        media_type="text/x-diff",
        metadata={
            "base_commit": base_commit,
            "candidate_commit": candidate_commit,
            "executor_version": "0.1.0",
        },
    )
    return DeterministicGateExecutionRequest(
        gate_request=gate_request,
        candidate_patch=patch_reference,
    )
