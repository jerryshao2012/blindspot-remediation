from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from release_gate.cli import main
from release_gate.config import load_config


def test_init_creates_valid_generic_draft_and_gitignore(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del capsys
    assert main(["init", "--repo", str(tmp_path)]) == 0

    policy = tmp_path / ".release-gate.yaml"
    assert policy.exists()
    value = yaml.safe_load(policy.read_text(encoding="utf-8"))
    assert value["checks"][0]["argv"] == ["release-gate-configure-me"]
    assert value["scope"]["allowed_paths"] == ["**"]
    assert load_config(policy).version == 1
    assert (
        "/.release-gate/runs/"
        in (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    )


def test_init_preserves_existing_gitignore_content(tmp_path: Path) -> None:
    ignore = tmp_path / ".gitignore"
    ignore.write_text("dist/\n", encoding="utf-8")

    assert main(["init", "--repo", str(tmp_path)]) == 0

    assert ignore.read_text(encoding="utf-8") == "dist/\n/.release-gate/runs/\n"


def test_init_refuses_to_overwrite_existing_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del capsys
    policy = tmp_path / ".release-gate.yaml"
    policy.write_text("owned by user\n", encoding="utf-8")

    assert main(["init", "--repo", str(tmp_path)]) == 3
    assert policy.read_text(encoding="utf-8") == "owned by user\n"


def test_validate_reads_working_copy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del capsys
    assert main(["init", "--repo", str(tmp_path)]) == 0
    assert main(["validate", "--repo", str(tmp_path)]) == 0

    policy = tmp_path / ".release-gate.yaml"
    policy.write_text("version: 2\n", encoding="utf-8")
    assert main(["validate", "--repo", str(tmp_path)]) == 3


def test_validate_output_and_diagnostics_use_stable_streams(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init", "--repo", str(tmp_path)]) == 0
    capsys.readouterr()

    assert main(["validate", "--repo", str(tmp_path)]) == 0
    valid = capsys.readouterr()
    assert valid.out == f"VALID: {tmp_path / '.release-gate.yaml'}\n"
    assert valid.err == ""

    (tmp_path / ".release-gate.yaml").write_text("not: valid\n", encoding="utf-8")
    assert main(["validate", "--repo", str(tmp_path)]) == 3
    invalid = capsys.readouterr()
    assert invalid.out == ""
    assert invalid.err.startswith("ERROR: ")


def test_invalid_cli_usage_returns_exit_3(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["unknown-command"]) == 3
    result = capsys.readouterr()
    assert result.out == ""
    assert result.err.startswith("ERROR: ")
