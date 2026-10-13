from __future__ import annotations

from pathlib import Path

import pytest

from release_gate.cli_init import init_repository, read_approved_config
from release_gate.config import ConfigError

_VALID_POLICY = b"""\
version: 1
scope:
  allowed_paths: ["**"]
  forbidden_paths: []
  review_required_paths: ["/.release-gate.yaml"]
checks:
  - id: tests
    mode: candidate
    severity: blocking
    argv: ["python", "-m", "pytest"]
"""


def test_init_repository_creates_policy_and_ignore_entry(tmp_path: Path) -> None:
    assert init_repository(tmp_path) == 0

    assert (tmp_path / ".release-gate.yaml").exists()
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == (
        "/.release-gate/runs/\n"
    )


def test_read_approved_config_validates_and_preserves_bytes(tmp_path: Path) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)

    assert read_approved_config(source) == _VALID_POLICY


@pytest.mark.parametrize("content", [b"version: 2\n", b"version: [\n"])
def test_read_approved_config_rejects_invalid_policy(
    tmp_path: Path, content: bytes
) -> None:
    source = tmp_path / "invalid.yaml"
    source.write_bytes(content)

    with pytest.raises(ConfigError):
        read_approved_config(source)
