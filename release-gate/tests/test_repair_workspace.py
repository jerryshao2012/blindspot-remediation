"""Tests for repair workspace creation, candidate export, and path enforcement."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from release_gate.git import _base_git_environment, capture_candidate
from release_gate.repair.workspace import (
    RepairWorkspace,
    RepairWorkspaceError,
    cleanup_repair_workspace,
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


@pytest.mark.parametrize("protected", ["source", "evidence"])
def test_cleanup_refuses_protected_paths(tmp_path: Path, protected: str) -> None:
    root = tmp_path / "release-gate-repair-ws-protected"
    workspace = root / "worktree"
    workspace.mkdir(parents=True)
    repository = workspace if protected == "source" else tmp_path / "source"
    evidence_root = root / "evidence" if protected == "evidence" else tmp_path / "runs"
    (root / ".release-gate-repair-owner").write_text(
        f"{repository.resolve()}\n{workspace}\n", encoding="utf-8"
    )

    with pytest.raises(RepairWorkspaceError, match="protected repair path"):
        cleanup_repair_workspace(workspace, repository, evidence_root)

    assert workspace.exists()
    assert (root / ".release-gate-repair-owner").exists()


def test_cleanup_keeps_unmarked_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "release-gate-repair-ws-legacy" / "worktree"
    workspace.mkdir(parents=True)

    cleanup_repair_workspace(workspace, tmp_path / "source", tmp_path / "runs")

    assert workspace.exists()


@pytest.mark.parametrize("readonly", [True, False])
def test_cleanup_retries_only_readonly_file_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, readonly: bool
) -> None:
    import os
    import shutil
    import stat

    repo = tmp_path / "repo"
    repo.mkdir()
    root = tmp_path / "release-gate-repair-ws-test"
    workspace = root / "worktree"
    workspace.mkdir(parents=True)
    (root / ".release-gate-repair-owner").write_text(f"{repo.resolve()}\n{workspace}\n")
    blob = workspace / "git-object"
    blob.write_bytes(b"object")
    if readonly:
        blob.chmod(stat.S_IREAD)
    real_rmtree = shutil.rmtree

    def remove_file(path):
        assert Path(path).stat().st_mode & stat.S_IWRITE
        os.unlink(path)

    def windows_rmtree(path, *, onerror=None):
        error = PermissionError("Access is denied")
        if onerror is None:
            raise error
        onerror(remove_file, str(blob), (PermissionError, error, None))
        real_rmtree(path)

    with monkeypatch.context() as patch:
        patch.setattr("release_gate.repair.workspace.shutil.rmtree", windows_rmtree)
        if readonly:
            cleanup_repair_workspace(workspace, repo)
            assert not root.exists()
        else:
            with pytest.raises(RepairWorkspaceError, match="cleanup failed"):
                cleanup_repair_workspace(workspace, repo)
            assert blob.exists()
    if root.exists():
        real_rmtree(root)
