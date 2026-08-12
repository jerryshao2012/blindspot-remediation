from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


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


@pytest.fixture
def source_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "source-repository"
    repository.mkdir()
    run_git(repository, "init")
    run_git(repository, "config", "user.name", "Test Author")
    run_git(repository, "config", "user.email", "test-author@example.test")
    (repository / "calculator.py").write_text(
        (
            "def add(left: int, right: int) -> int:\n"
            "    return left + right\n"
        ),
        encoding="utf-8",
    )
    (repository / "test_calculator.py").write_text(
        (
            "from calculator import add\n\n"
            "\n"
            "def test_add() -> None:\n"
            "    assert add(2, 3) == 5\n"
        ),
        encoding="utf-8",
    )
    (repository / "pipeline.yaml").write_text(
        "name: protected-pipeline\n",
        encoding="utf-8",
    )
    run_git(repository, "add", "--all")
    run_git(repository, "commit", "-m", "Initial repository")
    base_commit = run_git(repository, "rev-parse", "HEAD")
    return repository, base_commit


@pytest.fixture
def valid_patch(
    source_repository: tuple[Path, str],
    tmp_path: Path,
) -> Path:
    repository, _ = source_repository
    (repository / "calculator.py").write_text(
        (
            "def add(left: int, right: int) -> int:\n"
            "    \"\"\"Return the sum of two integers.\"\"\"\n"
            "    return left + right\n"
        ),
        encoding="utf-8",
    )
    patch_text = run_git(
        repository,
        "diff",
        "--binary",
        "--full-index",
    )
    run_git(repository, "restore", "--worktree", "--staged", ".")
    patch_path = tmp_path / "valid.patch"
    patch_path.write_text(patch_text, encoding="utf-8")
    return patch_path


@pytest.fixture
def scope_violating_patch(
    source_repository: tuple[Path, str],
    tmp_path: Path,
) -> Path:
    repository, _ = source_repository
    (repository / "pipeline.yaml").write_text(
        "name: unauthorized-change\n",
        encoding="utf-8",
    )
    patch_text = run_git(
        repository,
        "diff",
        "--binary",
        "--full-index",
    )
    run_git(repository, "restore", "--worktree", "--staged", ".")
    patch_path = tmp_path / "scope-violating.patch"
    patch_path.write_text(patch_text, encoding="utf-8")
    return patch_path
