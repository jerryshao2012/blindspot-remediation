from __future__ import annotations

from pathlib import Path

import pytest
from ai_engineering_contracts import ExecutionBudget, TaskRunRequest

from ai_engineering_change_executor.errors import ScopeViolationError
from ai_engineering_change_executor.git_workspace import GitWorkspace
from ai_engineering_change_executor.process import (
    CommandRunner,
    ExecutionBudgetTracker,
)
from ai_engineering_change_executor.tracing import ExecutionTraceRecorder


def build_task(
    repository: Path,
    base_commit: str,
) -> TaskRunRequest:
    return TaskRunRequest(
        run_id="workspace-test-1",
        task_type="X1-documentation-change",
        task_package_version="1.0.0",
        repository_url=repository.resolve().as_uri(),
        base_commit=base_commit,
        target_branch="main",
        task_description="Add a docstring to the add function.",
        acceptance_criteria=[
            "The add function retains its existing behaviour.",
            "The changed Python source compiles.",
        ],
        permitted_paths=["calculator.py", "test_calculator.py"],
        prohibited_paths=["pipeline.yaml"],
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


def build_workspace(tmp_path: Path) -> GitWorkspace:
    budget = ExecutionBudgetTracker(
        maximum_tool_calls=100,
        maximum_runtime_seconds=600,
    )
    runner = CommandRunner(
        budget=budget,
        maximum_captured_output_bytes=1_000_000,
    )
    return GitWorkspace(
        root=tmp_path / "workspace",
        git_executable="git",
        command_runner=runner,
        trace=ExecutionTraceRecorder("workspace-test-1"),
    )


def test_workspace_applies_patch_and_validates_scope(
    source_repository: tuple[Path, str],
    valid_patch: Path,
    tmp_path: Path,
) -> None:
    repository, base_commit = source_repository
    task = build_task(repository, base_commit)
    workspace = build_workspace(tmp_path)
    workspace.initialize(
        repository_url=task.repository_url,
        base_commit=base_commit,
    )
    changed_files = workspace.apply_patch(valid_patch)
    workspace.validate_scope(
        changed_files=changed_files,
        task=task,
    )
    assert changed_files == ["calculator.py"]


def test_workspace_rejects_out_of_scope_change(
    source_repository: tuple[Path, str],
    scope_violating_patch: Path,
    tmp_path: Path,
) -> None:
    repository, base_commit = source_repository
    task = build_task(repository, base_commit)
    workspace = build_workspace(tmp_path)
    workspace.initialize(
        repository_url=task.repository_url,
        base_commit=base_commit,
    )
    changed_files = workspace.apply_patch(scope_violating_patch)
    with pytest.raises(ScopeViolationError):
        workspace.validate_scope(
            changed_files=changed_files,
            task=task,
        )
