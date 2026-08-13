from __future__ import annotations

from pathlib import Path

import pytest
from ai_engineering_contracts import (
    ArtifactKind,
    ArtifactReference,
    ExecutionBudget,
    ExecutionStatus,
    TaskRunRequest,
)

from ai_engineering_change_executor.artifacts import sha256_bytes
from ai_engineering_change_executor.models import (
    ExecutorSettings,
    GitIdentity,
    LocalCheckSpec,
    ManualPatchExecutionRequest,
)
from ai_engineering_change_executor.service import ChangeExecutionService


def build_patch_reference(path: Path, run_id: str) -> ArtifactReference:
    content = path.read_bytes()
    return ArtifactReference(
        artifact_id=f"{run_id}:input.patch",
        kind=ArtifactKind.PATCH,
        uri=path.resolve().as_uri(),
        sha256=sha256_bytes(content),
        media_type="text/x-diff",
        size_bytes=len(content),
        immutable=True,
    )


def build_task(
    *,
    repository: Path,
    base_commit: str,
    run_id: str,
) -> TaskRunRequest:
    return TaskRunRequest(
        run_id=run_id,
        task_type="X1-documentation-change",
        task_package_version="1.0.0",
        repository_url=repository.resolve().as_uri(),
        base_commit=base_commit,
        target_branch="main",
        task_description="Add a docstring to the add function.",
        acceptance_criteria=[
            "The add function retains its existing behaviour.",
            "The changed Python source compiles.",
            "Existing tests continue to pass.",
        ],
        permitted_paths=[
            "calculator.py",
            "test_calculator.py",
        ],
        prohibited_paths=[
            "pipeline.yaml",
        ],
        execution_budget=ExecutionBudget(
            maximum_llm_calls=0,
            maximum_input_tokens=0,
            maximum_output_tokens=0,
            maximum_tool_calls=100,
            maximum_repair_iterations=0,
            maximum_runtime_seconds=600,
            maximum_estimated_cost=0.0,
        ),
        requested_by="pytest",
    )


def build_settings(tmp_path: Path) -> ExecutorSettings:
    return ExecutorSettings(
        artifact_root=tmp_path / "artifacts",
        git_identity=GitIdentity(
            name="POC Test Executor",
            email="executor@example.test",
        ),
        local_checks=[
            LocalCheckSpec(
                check_id="python-compile",
                name="Compile changed Python module",
                command=[
                    "python",
                    "-m",
                    "py_compile",
                    "calculator.py",
                ],
                timeout_seconds=60,
                required=True,
            ),
            LocalCheckSpec(
                check_id="pytest",
                name="Run tests",
                command=[
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                ],
                timeout_seconds=60,
                required=True,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_service_produces_candidate_commit(
    source_repository: tuple[Path, str],
    valid_patch: Path,
    tmp_path: Path,
) -> None:
    repository, base_commit = source_repository
    run_id = "service-success-1"
    request = ManualPatchExecutionRequest(
        task=build_task(
            repository=repository,
            base_commit=base_commit,
            run_id=run_id,
        ),
        patch_artifact=build_patch_reference(valid_patch, run_id),
        commit_message="Add calculator function documentation",
    )
    service = ChangeExecutionService(
        settings=build_settings(tmp_path)
    )
    result = await service.execute(request)
    assert result.status == ExecutionStatus.COMPLETED
    assert result.candidate_commit is not None
    assert result.candidate_commit != base_commit
    assert result.patch_artifact is not None
    assert result.patch_artifact.kind == ArtifactKind.PATCH
    assert result.execution_trace.kind == ArtifactKind.EXECUTION_TRACE
    assert result.changed_files == ["calculator.py"]
    assert result.token_usage.llm_calls == 0
    assert all(
        check.is_authoritative_release_evidence is False
        for check in result.local_check_results
    )
    assert all(
        check.status.value == "passed"
        for check in result.local_check_results
    )


@pytest.mark.asyncio
async def test_service_returns_structured_failure_for_scope_violation(
    source_repository: tuple[Path, str],
    scope_violating_patch: Path,
    tmp_path: Path,
) -> None:
    repository, base_commit = source_repository
    run_id = "service-scope-failure-1"
    request = ManualPatchExecutionRequest(
        task=build_task(
            repository=repository,
            base_commit=base_commit,
            run_id=run_id,
        ),
        patch_artifact=build_patch_reference(
            scope_violating_patch,
            run_id,
        ),
        commit_message="Unauthorized pipeline change",
    )
    service = ChangeExecutionService(
        settings=build_settings(tmp_path)
    )
    result = await service.execute(request)
    assert result.status == ExecutionStatus.FAILED
    assert result.candidate_commit is None
    assert result.patch_artifact is None
    assert result.failure_reason is not None
    assert "ScopeViolationError" in result.failure_reason
    assert "pipeline.yaml" in result.failure_reason
    assert result.execution_trace.kind == ArtifactKind.EXECUTION_TRACE


@pytest.mark.asyncio
async def test_failed_local_check_does_not_claim_release_authority(
    source_repository: tuple[Path, str],
    valid_patch: Path,
    tmp_path: Path,
) -> None:
    repository, base_commit = source_repository
    run_id = "service-check-failure-1"
    settings = ExecutorSettings(
        artifact_root=tmp_path / "artifacts",
        local_checks=[
            LocalCheckSpec(
                check_id="intentional-failure",
                name="Intentional failed executor check",
                command=[
                    "python",
                    "-c",
                    "raise SystemExit(7)",
                ],
                timeout_seconds=60,
                required=True,
            )
        ],
    )
    request = ManualPatchExecutionRequest(
        task=build_task(
            repository=repository,
            base_commit=base_commit,
            run_id=run_id,
        ),
        patch_artifact=build_patch_reference(valid_patch, run_id),
        commit_message="Candidate with failed local feedback check",
    )
    result = await ChangeExecutionService(
        settings=settings
    ).execute(request)
    # The executor still produces the candidate. The independent gate will
    # decide how failed checks affect release eligibility.
    assert result.status == ExecutionStatus.COMPLETED
    assert len(result.local_check_results) == 1
    assert result.local_check_results[0].status.value == "failed"
    assert (
        result.local_check_results[0].is_authoritative_release_evidence
        is False
    )
