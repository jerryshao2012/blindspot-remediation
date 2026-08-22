"""Tests for base-trusted repair playbooks discovery and validation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from release_gate.git import _base_git_environment
from release_gate.repair.playbooks import (
    has_harness_changes,
    load_playbooks_from_base,
)


def _init_repo_with_playbook(path: Path) -> str:
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

    # Base policy
    policy = """\
version: 1
scope:
  allowed_paths: ["**"]
  forbidden_paths: ["secrets/**"]
  review_required_paths: [".release-gate.yaml"]
prepare: []
checks:
  - id: pytest
    mode: candidate
    severity: blocking
    argv: ["pytest"]
"""
    (path / ".release-gate.yaml").write_text(policy)
    (path / "app.py").write_text("def add(a, b): return a + b\n")

    # Base playbook
    playbook_dir = path / ".release-gate" / "repair"
    playbook_dir.mkdir(parents=True)
    playbook_yaml = """\
check_id: pytest
name: Pytest Repair Guide
description: Steps to fix broken pytest runs
allowed_paths:
  - tests/conftest.py
guidance: Check assertion output and fix corresponding unit tests.
"""
    (playbook_dir / "pytest.yaml").write_text(playbook_yaml)

    subprocess.run(["git", "-C", str(path), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "Initial commit with playbooks"],
        check=True,
        env=env,
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


def test_missing_playbook_returns_generic_fallback(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = _base_git_environment()
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        env=env,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"], check=True, env=env
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
        env=env,
    )
    (repo / "README.md").write_text("Hello\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "Init"], check=True, env=env
    )

    base_commit = (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            env=env,
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )

    playbooks = load_playbooks_from_base(repo, base_commit, failed_check_ids=["pytest"])
    assert not playbooks.is_custom
    assert playbooks.extra_approved_paths == ()
    assert playbooks.warnings == ()
    assert "Generic repair workflow" in playbooks.guidance_for_checks(["pytest"])


def test_load_playbooks_from_base(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    base_commit = _init_repo_with_playbook(repo)

    # In worktree, modify playbook (candidate modification)
    (repo / ".release-gate" / "repair" / "pytest.yaml").write_text(
        "corrupted / modified in worktree"
    )

    # Load from base commit -> should read base commit playbook, not worktree
    playbooks = load_playbooks_from_base(
        repo, base_commit, failed_check_ids=["pytest"]
    )
    assert playbooks.is_custom
    assert "tests/conftest.py" in playbooks.extra_approved_paths
    assert "Pytest Repair Guide" in playbooks.guidance_for_checks(["pytest"])
    assert playbooks.warnings == ()


def test_candidate_harness_changes_detection() -> None:
    assert has_harness_changes([".release-gate/repair/pytest.yaml"])
    assert has_harness_changes(["src/app.py", ".release-gate/repair/playbook.md"])
    assert not has_harness_changes(
        ["src/app.py", "tests/test_app.py", ".release-gate.yaml"]
    )


def test_malformed_playbook_in_base_emits_warning(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = _base_git_environment()
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        env=env,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"], check=True, env=env
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
        env=env,
    )

    playbook_dir = repo / ".release-gate" / "repair"
    playbook_dir.mkdir(parents=True)
    (playbook_dir / "bad.yaml").write_text("::: not valid yaml :::")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "Bad playbook"], check=True, env=env
    )

    base_commit = (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            env=env,
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )

    playbooks = load_playbooks_from_base(repo, base_commit, failed_check_ids=["pytest"])
    assert len(playbooks.warnings) == 1
    assert "bad.yaml" in playbooks.warnings[0]


def test_loads_check_mapping_and_markdown_guidance_from_base(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_playbook(repo)
    playbook_dir = repo / ".release-gate" / "repair"
    (playbook_dir / "workflow.yaml").write_text(
        """\
version: 1
checks:
  pytest:
    guidance: Fix the implementation, not the test.
    extra_approved_paths: [src/helper.py]
"""
    )
    (playbook_dir / "lint.md").write_text("Use the formatter and preserve behavior.\n")
    subprocess.run(
        ["git", "-C", str(repo), "add", ".release-gate/repair"],
        check=True,
        env=_base_git_environment(),
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "Add mapped playbooks"],
        check=True,
        env=_base_git_environment(),
    )
    base_commit = (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            env=_base_git_environment(),
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )

    playbooks = load_playbooks_from_base(
        repo, base_commit, failed_check_ids=["pytest", "lint"]
    )

    assert "src/helper.py" in playbooks.extra_approved_paths
    assert "Fix the implementation" in playbooks.guidance_for_checks(["pytest"])
    assert "Use the formatter" in playbooks.guidance_for_checks(["lint"])
