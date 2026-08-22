"""Tests for repair workspace creation, candidate export, and path enforcement."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from release_gate.git import _base_git_environment, capture_candidate
from release_gate.repair.workspace import (
    RepairWorkspace,
    RepairWorkspaceError,
    compute_approved_paths,
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

    # Base policy & initial files
    policy = """\
version: 1
scope:
  allowed_paths: ["**"]
  forbidden_paths: ["secret/**"]
  review_required_paths: [".release-gate.yaml"]
prepare: []
checks:
  - id: pytest
    mode: candidate
    severity: blocking
    argv: ["pytest"]
"""
    (path / ".release-gate.yaml").write_text(policy)
    (path / "app.py").write_text("def add(a, b): return a - b\n")
    (path / "test_app.py").write_text(
        "from app import add\ndef test_add(): assert add(1, 2) == 3\n"
    )

    subprocess.run(["git", "-C", str(path), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "Initial commit"], check=True, env=env
    )

    base_commit = (
        subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            env=env,
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )

    return base_commit


def test_repair_workspace_isolation_and_export(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    base_commit = _init_test_git_repo(repo)

    # Mutate app.py in source worktree to create initial candidate C0
    (repo / "app.py").write_text("def add(a, b): return a + b + 1\n")
    capture = capture_candidate(repo, base="HEAD")
    approved = compute_approved_paths(capture.changed_paths, capture.config.scope)
    assert approved == ("app.py",)

    # Create repair workspace
    source_mtime_before = (repo / "app.py").stat().st_mtime
    ws = RepairWorkspace.create(
        repo,
        base_commit=base_commit,
        initial_patch=capture.patch,
        approved_paths=approved,
    )
    try:
        # Check that workspace has candidate C0
        assert (
            ws.workspace_path / "app.py"
        ).read_text() == "def add(a, b): return a + b + 1\n"
        # Check that source repo was NOT touched
        assert (repo / "app.py").stat().st_mtime == source_mtime_before

        # Unchanged candidate export should fail
        with pytest.raises(RepairWorkspaceError, match="unchanged"):
            ws.export_candidate()

        # Repair: edit app.py inside workspace to fix the bug
        (ws.workspace_path / "app.py").write_text("def add(a, b): return a + b\n")

        # Export candidate C1
        c1 = ws.export_candidate()
        assert c1.candidate_tree != capture.candidate_tree
        assert c1.patch_sha256 != capture.patch_sha256
        assert c1.changed_paths == ("app.py",)

        # Disallow repeated export without further edits
        with pytest.raises(RepairWorkspaceError, match="repeated"):
            ws.record_attempt(c1.candidate_tree, c1.patch_sha256)
            ws.export_candidate()

    finally:
        ws.cleanup()


def test_repair_workspace_rejects_unapproved_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    base_commit = _init_test_git_repo(repo)

    (repo / "app.py").write_text("def add(a, b): return a + b + 1\n")
    capture = capture_candidate(repo, base="HEAD")
    approved = compute_approved_paths(capture.changed_paths, capture.config.scope)

    ws = RepairWorkspace.create(
        repo,
        base_commit=base_commit,
        initial_patch=capture.patch,
        approved_paths=approved,
    )
    try:
        # Edit unapproved file
        (ws.workspace_path / "other.py").write_text("x = 1\n")
        with pytest.raises(RepairWorkspaceError, match="outside approved paths"):
            ws.export_candidate()
    finally:
        ws.cleanup()


def test_compute_approved_paths() -> None:
    from release_gate.models import Scope

    scope = Scope(
        allowed_paths=["**"],
        forbidden_paths=["secrets/**"],
        review_required_paths=[".release-gate.yaml", "infra/**"],
    )
    changed = ("app.py", "secrets/key.pem", "infra/main.tf")
    extra = ("test_app.py",)
    approved = compute_approved_paths(changed, scope, extra_paths=extra)
    assert approved == ("app.py", "test_app.py")
