from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from release_gate.git import CaptureError, capture_candidate

POLICY = """\
version: 1
scope:
  allowed_paths: ["**"]
  forbidden_paths: []
  review_required_paths: ["/.release-gate.yaml"]
prepare: []
checks:
  - id: base-check
    mode: candidate
    severity: blocking
    argv: ["project-check"]
"""


def git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        capture_output=True,
        check=True,
    ).stdout


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "--initial-branch=main")
    git(repo, "config", "user.email", "gate@example.invalid")
    git(repo, "config", "user.name", "Release Gate Test")
    (repo / ".release-gate.yaml").write_text(POLICY, encoding="utf-8")
    (repo / ".gitignore").write_text("ignored.txt\n/.release-gate/runs/\n")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    (repo / "delete-me.txt").write_text("delete\n", encoding="utf-8")
    (repo / "rename-me.txt").write_text("rename\n", encoding="utf-8")
    (repo / "script.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    return repo


def object_inventory(repo: Path) -> dict[str, str]:
    object_dir = Path(
        git(repo, "rev-parse", "--path-format=absolute", "--git-path", "objects")
        .decode()
        .strip()
    )
    return {
        path.relative_to(object_dir).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in object_dir.rglob("*")
        if path.is_file()
    }


def repository_snapshot(repo: Path) -> tuple[bytes, bytes, bytes, dict[str, str]]:
    git_dir = Path(
        git(repo, "rev-parse", "--path-format=absolute", "--git-dir").decode().strip()
    )
    index = (git_dir / "index").read_bytes()
    status = git(repo, "status", "--porcelain=v2", "-z", "--untracked-files=all")
    refs = git(repo, "show-ref")
    return index, status, refs, object_inventory(repo)


def test_policy_is_loaded_from_base_and_candidate_change_is_only_recorded(
    repository: Path,
) -> None:
    before = repository_snapshot(repository)
    candidate_policy = POLICY.replace("base-check", "candidate-check")
    (repository / ".release-gate.yaml").write_text(candidate_policy, encoding="utf-8")

    capture = capture_candidate(repository, base="HEAD")

    assert capture.config.checks[0].id == "base-check"
    assert capture.policy_changed is True
    assert ".release-gate.yaml" in capture.changed_paths
    assert repository_snapshot(repository) == (
        before[0],
        git(repository, "status", "--porcelain=v2", "-z", "--untracked-files=all"),
        before[2],
        before[3],
    )


def test_captures_complete_worktree_without_ignored_files(repository: Path) -> None:
    (repository / "tracked.txt").write_text("staged\n", encoding="utf-8")
    git(repository, "add", "tracked.txt")
    (repository / "tracked.txt").write_text("unstaged wins\n", encoding="utf-8")
    (repository / "new file.txt").write_text("untracked\n", encoding="utf-8")
    (repository / "ignored.txt").write_text("ignored\n", encoding="utf-8")
    (repository / "binary.bin").write_bytes(b"\x00\xff\x10binary\n")
    git(repository, "mv", "rename-me.txt", "renamed.txt")
    (repository / "delete-me.txt").unlink()
    os.chmod(repository / "script.sh", 0o755)
    before = repository_snapshot(repository)

    capture = capture_candidate(repository, base="HEAD")

    assert {
        "tracked.txt",
        "new file.txt",
        "binary.bin",
        "rename-me.txt",
        "renamed.txt",
        "delete-me.txt",
        "script.sh",
    } <= set(capture.changed_paths)
    assert "ignored.txt" not in capture.changed_paths
    assert b"GIT binary patch" in capture.patch
    assert capture.patch_sha256 == hashlib.sha256(capture.patch).hexdigest()
    assert repository_snapshot(repository) == before


def test_capture_ignores_existing_evidence_directory(repository: Path) -> None:
    evidence = repository / ".release-gate" / "runs" / "previous-run"
    evidence.mkdir(parents=True)
    (evidence / "result.json").write_text("{}\n", encoding="utf-8")
    (repository / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    before = repository_snapshot(repository)

    capture = capture_candidate(repository, base="HEAD")

    assert "tracked.txt" in capture.changed_paths
    assert not any(
        path.startswith(".release-gate/runs/") for path in capture.changed_paths
    )
    assert repository_snapshot(repository) == before


def test_capture_is_deterministic_and_keeps_source_object_store_unchanged(
    repository: Path,
) -> None:
    (repository / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    before = repository_snapshot(repository)

    first = capture_candidate(repository, base="HEAD")
    second = capture_candidate(repository, base="HEAD")

    assert first.base_commit == second.base_commit
    assert first.candidate_tree == second.candidate_tree
    assert first.patch == second.patch
    assert first.patch_sha256 == second.patch_sha256
    assert repository_snapshot(repository) == before


def test_rejects_empty_candidate(repository: Path) -> None:
    with pytest.raises(CaptureError, match="empty candidate"):
        capture_candidate(repository, base="HEAD")


def test_rejects_invalid_base_and_missing_base_policy(repository: Path) -> None:
    with pytest.raises(CaptureError, match="base ref"):
        capture_candidate(repository, base="does-not-exist")

    git(repository, "rm", ".release-gate.yaml")
    git(repository, "commit", "-qm", "remove policy")
    (repository / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    with pytest.raises(CaptureError, match="base policy"):
        capture_candidate(repository, base="HEAD")


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
@pytest.mark.parametrize("component", [".release-gate", ".release-gate/runs"])
def test_rejects_redirected_default_evidence_components(
    repository: Path, component: str
) -> None:
    target = repository / "redirect-target"
    target.mkdir()
    entry = repository / component
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.symlink_to(target, target_is_directory=True)
    before = repository_snapshot(repository)

    with pytest.raises(CaptureError, match="evidence"):
        capture_candidate(repository, base="HEAD")

    assert repository_snapshot(repository) == before
    assert not any(target.iterdir())


def test_rejects_unmerged_index_without_mutation(repository: Path) -> None:
    git(repository, "checkout", "-qb", "other")
    (repository / "tracked.txt").write_text("other\n", encoding="utf-8")
    git(repository, "commit", "-qam", "other")
    git(repository, "checkout", "-q", "main")
    (repository / "tracked.txt").write_text("main\n", encoding="utf-8")
    git(repository, "commit", "-qam", "main")
    subprocess.run(
        ["git", "-C", str(repository), "merge", "other"],
        capture_output=True,
        check=False,
    )
    before = repository_snapshot(repository)

    with pytest.raises(CaptureError, match="unmerged"):
        capture_candidate(repository, base="HEAD")

    assert repository_snapshot(repository) == before
