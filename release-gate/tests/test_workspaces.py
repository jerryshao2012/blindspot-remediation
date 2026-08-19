from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from release_gate.git import capture_candidate
from release_gate.workspaces import WorkspaceError, clean_workspaces

POLICY = """\
version: 1
scope:
  allowed_paths: ["**"]
  review_required_paths: ["/.release-gate.yaml"]
checks:
  - id: tests
    mode: differential
    severity: blocking
    argv: ["project-check"]
"""


def git(repo: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True,
        check=True,
    ).stdout


@pytest.fixture
def captured_repository(tmp_path: Path):  # type: ignore[no-untyped-def]
    repo = tmp_path / "source"
    repo.mkdir()
    git(repo, "init", "-q", "--initial-branch=main")
    git(repo, "config", "user.email", "gate@example.invalid")
    git(repo, "config", "user.name", "Release Gate Test")
    (repo / ".release-gate.yaml").write_text(POLICY, encoding="utf-8")
    (repo / "keep.txt").write_text("base\n", encoding="utf-8")
    (repo / "remove.txt").write_text("remove\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    (repo / "keep.txt").write_text("candidate\n", encoding="utf-8")
    (repo / "remove.txt").unlink()
    (repo / "binary.bin").write_bytes(b"\x00\xffcandidate")
    return capture_candidate(repo, base="HEAD")


def test_reconstructs_independent_base_and_candidate(captured_repository) -> None:  # type: ignore[no-untyped-def]
    capture = captured_repository
    with clean_workspaces(capture) as workspaces:
        assert workspaces.base != workspaces.candidate
        assert (workspaces.base / "keep.txt").read_text() == "base\n"
        assert (workspaces.candidate / "keep.txt").read_text() == "candidate\n"
        assert (workspaces.base / "remove.txt").exists()
        assert not (workspaces.candidate / "remove.txt").exists()
        assert (
            workspaces.candidate / "binary.bin"
        ).read_bytes() == b"\x00\xffcandidate"
        assert (
            git(workspaces.base, "rev-parse", "HEAD^{tree}").decode().strip()
            == capture.base_tree
        )
        assert (
            git(workspaces.candidate, "write-tree").decode().strip()
            == capture.candidate_tree
        )


def test_generated_files_never_cross_between_workspaces(captured_repository) -> None:  # type: ignore[no-untyped-def]
    with clean_workspaces(captured_repository) as workspaces:
        (workspaces.base / "base-output.txt").write_text("base")
        (workspaces.candidate / "candidate-output.txt").write_text("candidate")
        assert not (workspaces.base / "candidate-output.txt").exists()
        assert not (workspaces.candidate / "base-output.txt").exists()


def test_cleans_both_workspaces_after_success_and_exception(
    captured_repository,
) -> None:  # type: ignore[no-untyped-def]
    with clean_workspaces(captured_repository) as successful:
        successful_root = successful.root
        assert successful_root.exists()
    assert not successful_root.exists()

    with pytest.raises(RuntimeError, match="boom"):
        with clean_workspaces(captured_repository) as failed:
            failed_root = failed.root
            raise RuntimeError("boom")
    assert not failed_root.exists()


@pytest.mark.parametrize(
    "patch",
    [b"not a patch\n", b"diff --git a/../../escape b/../../escape\n"],
)
def test_rejects_invalid_or_escaping_patch(captured_repository, patch: bytes) -> None:  # type: ignore[no-untyped-def]
    tampered = replace(captured_repository, patch=patch)
    with pytest.raises(WorkspaceError, match="patch"):
        with clean_workspaces(tampered):
            pytest.fail("invalid patch was accepted")


def test_rejects_workspace_parent_inside_source(captured_repository) -> None:  # type: ignore[no-untyped-def]
    inside = captured_repository.repository / "workspaces"
    inside.mkdir()

    with pytest.raises(WorkspaceError, match="overlaps"):
        with clean_workspaces(captured_repository, parent=inside):
            pytest.fail("overlapping workspace root was accepted")
