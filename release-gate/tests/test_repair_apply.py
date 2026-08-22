"""Tests for safe apply of passing repair candidates to source worktree."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from release_gate.git import _base_git_environment, capture_candidate
from release_gate.repair.models import FinalApproval, RepairAttempt
from release_gate.repair.workspace import (
    RepairWorkspace,
    apply_candidate_to_source,
)


def _init_test_git_repo(path: Path) -> str:
    env = _base_git_environment()
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        env=env,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"], check=True, env=env
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
        env=env,
    )

    policy = """\
version: 1
scope:
  allowed_paths: ["**"]
  forbidden_paths: []
  review_required_paths: [".release-gate.yaml"]
prepare: []
checks:
  - id: test
    mode: candidate
    severity: blocking
    argv: ["true"]
"""
    (path / ".release-gate.yaml").write_text(policy)
    (path / "app.py").write_text("def run(): return 1\n")
    (path / "unrelated.py").write_text("x = 10\n")

    subprocess.run(["git", "-C", str(path), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "Initial commit"], check=True, env=env
    )

    return (
        subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            env=env,
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )


def test_apply_candidate_to_source_success(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    base_commit = _init_test_git_repo(repo)

    # Initial buggy candidate C0 in source
    (repo / "app.py").write_text("def run(): return 2\n")
    c0_capture = capture_candidate(repo, base="HEAD")

    # In workspace, create passing candidate C1
    ws = RepairWorkspace.create(
        repo,
        base_commit=base_commit,
        initial_patch=c0_capture.patch,
        approved_paths=("app.py",),
    )
    try:
        (ws.workspace_path / "app.py").write_text("def run(): return 42\n")
        c1 = ws.export_candidate()
    finally:
        ws.cleanup()

    c0_attempt = RepairAttempt(
        candidate_label="C0",
        gate_run_id="run-c0",
        base_commit=base_commit,
        candidate_tree=c0_capture.candidate_tree,
        patch_digest=c0_capture.patch_sha256,
        result_digest="a" * 64,
        manifest_digest="b" * 64,
        verdict="FAIL",
        reason_codes=("COMMAND_FAILED",),
        failed_check_ids=("test",),
    )
    c1_attempt = RepairAttempt(
        candidate_label="C1",
        gate_run_id="run-c1",
        base_commit=base_commit,
        candidate_tree=c1.candidate_tree,
        patch_digest=c1.patch_sha256,
        result_digest="c" * 64,
        manifest_digest="d" * 64,
        verdict="PASS",
        reason_codes=(),
        failed_check_ids=(),
    )

    final_approval = FinalApproval(
        session_id="rep-123",
        final_candidate_tree=c1.candidate_tree,
        final_patch_digest=c1.patch_sha256,
        approved_at="2026-08-21T21:30:00Z",
    )

    # Apply candidate
    apply_candidate_to_source(
        repo_path=repo,
        base_commit=base_commit,
        c0_attempt=c0_attempt,
        passing_attempt=c1_attempt,
        original_patch=c0_capture.patch,
        final_patch=c1.patch,
        final_approval=final_approval,
    )

    # Verify source worktree updated and matches C1
    assert (repo / "app.py").read_text() == "def run(): return 42\n"
    # Verify unrelated file untouched
    assert (repo / "unrelated.py").read_text() == "x = 10\n"

    # Verify candidate capture on source worktree matches C1
    post_capture = capture_candidate(repo, base="HEAD")
    assert post_capture.candidate_tree == c1.candidate_tree
    assert post_capture.patch_sha256 == c1.patch_sha256


def test_apply_candidate_rejects_modified_source(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    base_commit = _init_test_git_repo(repo)

    (repo / "app.py").write_text("def run(): return 2\n")
    c0_capture = capture_candidate(repo, base="HEAD")

    ws = RepairWorkspace.create(
        repo,
        base_commit=base_commit,
        initial_patch=c0_capture.patch,
        approved_paths=("app.py",),
    )
    try:
        (ws.workspace_path / "app.py").write_text("def run(): return 42\n")
        c1 = ws.export_candidate()
    finally:
        ws.cleanup()

    c0_attempt = RepairAttempt(
        candidate_label="C0",
        gate_run_id="run-c0",
        base_commit=base_commit,
        candidate_tree=c0_capture.candidate_tree,
        patch_digest=c0_capture.patch_sha256,
        result_digest="a" * 64,
        manifest_digest="b" * 64,
        verdict="FAIL",
        reason_codes=("COMMAND_FAILED",),
        failed_check_ids=("test",),
    )
    c1_attempt = RepairAttempt(
        candidate_label="C1",
        gate_run_id="run-c1",
        base_commit=base_commit,
        candidate_tree=c1.candidate_tree,
        patch_digest=c1.patch_sha256,
        result_digest="c" * 64,
        manifest_digest="d" * 64,
        verdict="PASS",
        reason_codes=(),
        failed_check_ids=(),
    )
    final_approval = FinalApproval(
        session_id="rep-123",
        final_candidate_tree=c1.candidate_tree,
        final_patch_digest=c1.patch_sha256,
        approved_at="2026-08-21T21:30:00Z",
    )

    # Source is modified concurrently before apply!
    (repo / "app.py").write_text("def run(): return 999\n")

    from release_gate.repair.workspace import RepairWorkspaceError

    with pytest.raises(RepairWorkspaceError, match="source_changed"):
        apply_candidate_to_source(
            repo_path=repo,
            base_commit=base_commit,
            c0_attempt=c0_attempt,
            passing_attempt=c1_attempt,
            original_patch=c0_capture.patch,
            final_patch=c1.patch,
            final_approval=final_approval,
        )

    # Source should remain what user wrote
    assert (repo / "app.py").read_text() == "def run(): return 999\n"


def test_apply_rolls_back_files_added_by_passing_patch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    base_commit = _init_test_git_repo(repo)

    (repo / "app.py").write_text("def run(): return 2\n")
    c0_capture = capture_candidate(repo, base="HEAD")
    ws = RepairWorkspace.create(
        repo,
        base_commit=base_commit,
        initial_patch=c0_capture.patch,
        approved_paths=("app.py", "new_module.py"),
    )
    try:
        (ws.workspace_path / "app.py").write_text("def run(): return 42\n")
        (ws.workspace_path / "new_module.py").write_text("value = 42\n")
        c1 = ws.export_candidate()
    finally:
        ws.cleanup()

    c0_attempt = RepairAttempt(
        candidate_label="C0",
        gate_run_id="run-c0",
        base_commit=base_commit,
        candidate_tree=c0_capture.candidate_tree,
        patch_digest=c0_capture.patch_sha256,
        result_digest="a" * 64,
        manifest_digest="b" * 64,
        verdict="FAIL",
        reason_codes=("COMMAND_FAILED",),
        failed_check_ids=("test",),
    )
    # Force post-apply verification to fail after the patch adds new_module.py.
    passing_attempt = RepairAttempt(
        candidate_label="C1",
        gate_run_id="run-c1",
        base_commit=base_commit,
        candidate_tree="f" * 40,
        patch_digest=c1.patch_sha256,
        result_digest="c" * 64,
        manifest_digest="d" * 64,
        verdict="PASS",
        reason_codes=(),
        failed_check_ids=(),
    )
    final_approval = FinalApproval(
        session_id="rep-123",
        final_candidate_tree=passing_attempt.candidate_tree,
        final_patch_digest=c1.patch_sha256,
        approved_at="2026-08-21T21:30:00Z",
    )

    from release_gate.repair.workspace import RepairWorkspaceError

    with pytest.raises(RepairWorkspaceError, match="rollback_failed"):
        apply_candidate_to_source(
            repo_path=repo,
            base_commit=base_commit,
            c0_attempt=c0_attempt,
            passing_attempt=passing_attempt,
            original_patch=c0_capture.patch,
            final_patch=c1.patch,
            final_approval=final_approval,
        )

    assert (repo / "app.py").read_text() == "def run(): return 2\n"
    assert not (repo / "new_module.py").exists()
