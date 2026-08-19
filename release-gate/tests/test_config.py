from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from release_gate.config import ConfigError, load_config, load_config_bytes
from release_gate.models import PlatformName

ROOT = Path(__file__).resolve().parents[1]
GENERIC_PATH = ROOT / "examples" / "generic" / ".release-gate.yaml"


def generic_value() -> dict[str, Any]:
    value = yaml.safe_load(GENERIC_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def encode(value: dict[str, Any]) -> bytes:
    return yaml.safe_dump(value, sort_keys=False).encode()


def test_loads_valid_policy_with_defaults_and_immutable_models() -> None:
    config = load_config(GENERIC_PATH)

    assert config.version == 1
    assert config.prepare == ()
    assert config.checks[0].cwd == "."
    assert config.limits.stream_bytes == 1_048_576
    assert config.requires_base_workspace is True
    with pytest.raises(ValidationError):
        config.checks[0].timeout = 5  # type: ignore[misc]


def test_rejects_legacy_scope_keys_with_json_path() -> None:
    value = generic_value()
    value["scope"] = {"allowed": ["src/**"]}

    with pytest.raises(ConfigError) as caught:
        load_config_bytes(encode(value), source="policy.yaml")

    assert "$.scope" in str(caught.value)
    assert "allowed_paths" in str(caught.value) or "allowed" in str(caught.value)


def test_rejects_unknown_keys_and_duplicate_yaml_keys() -> None:
    value = generic_value()
    value["checks"][0]["mystery"] = True
    with pytest.raises(ConfigError, match=r"\$\.checks\[0\]"):
        load_config_bytes(encode(value))

    duplicate = b"version: 1\nversion: 1\nscope: {}\nchecks: []\n"
    with pytest.raises(ConfigError, match="duplicate key"):
        load_config_bytes(duplicate)


def test_rejects_unsupported_version_and_oversized_raw_policy() -> None:
    value = generic_value()
    value["version"] = 2
    with pytest.raises(ConfigError, match=r"\$\.version"):
        load_config_bytes(encode(value))

    with pytest.raises(ConfigError, match="1 MiB"):
        load_config_bytes(b"#" * (1_048_576 + 1))


@pytest.mark.parametrize(
    "path",
    ["/tmp", "C:/tmp", "C:tmp", "../outside", "a/../outside", "\\\\host\\share"],
)
def test_rejects_unsafe_command_paths(path: str) -> None:
    value = generic_value()
    value["checks"][0]["cwd"] = path
    with pytest.raises(ConfigError, match=r"\$\.checks\[0\]\.cwd"):
        load_config_bytes(encode(value))


def test_rejects_duplicate_control_and_report_ids() -> None:
    value = generic_value()
    value["prepare"] = [{"id": "project-tests", "argv": ["python", "-V"]}]
    with pytest.raises(ConfigError, match="duplicate control id"):
        load_config_bytes(encode(value))

    value = generic_value()
    report = deepcopy(value["checks"][0]["reports"][0])
    value["checks"][0]["reports"].append(report)
    with pytest.raises(ConfigError, match="duplicate report id"):
        load_config_bytes(encode(value))


@pytest.mark.parametrize(
    ("field", "code"),
    [("pass", -1), ("fail", -9)],
)
def test_negative_exit_codes_are_error_only(field: str, code: int) -> None:
    value = generic_value()
    value["checks"][0]["exit_classes"] = {
        "pass": [0],
        "fail": [1],
        "error": [],
    }
    value["checks"][0]["exit_classes"][field].append(code)
    with pytest.raises(ConfigError, match="negative exit"):
        load_config_bytes(encode(value))


def test_exit_classes_must_be_disjoint() -> None:
    value = generic_value()
    value["checks"][0]["exit_classes"] = {
        "pass": [0],
        "fail": [0],
        "error": [],
    }
    with pytest.raises(ConfigError, match="overlap"):
        load_config_bytes(encode(value))


def test_assertions_require_declared_reports_and_compatible_modes() -> None:
    value = generic_value()
    value["checks"][0]["assertions"][0]["report"] = "absent"
    with pytest.raises(ConfigError, match="undeclared report"):
        load_config_bytes(encode(value))

    value = generic_value()
    value["checks"][0]["mode"] = "candidate"
    value["checks"][0]["assertions"][1]["comparison"] = "baseline"
    with pytest.raises(ConfigError, match="differential"):
        load_config_bytes(encode(value))


def test_report_limit_cannot_exceed_effective_global_limit() -> None:
    value = generic_value()
    value["limits"]["report_bytes"] = 100
    value["checks"][0]["reports"][0]["max_bytes"] = 101
    with pytest.raises(ConfigError, match="report_bytes"):
        load_config_bytes(encode(value))


def test_platform_override_replaces_fields_and_merges_literal_environment() -> None:
    config = load_config(GENERIC_PATH)
    command = config.checks[0].resolve(PlatformName.WINDOWS)

    assert command.argv[0] == "tools/project-gate-check.exe"
    assert command.inherit_environment == ("PATH", "PATHEXT", "SYSTEMROOT")
    assert command.environment == {"CI": "true"}


def test_environment_names_are_reserved_and_windows_case_insensitive() -> None:
    value = generic_value()
    value["checks"][0]["environment"]["TMPDIR"] = "unsafe"
    with pytest.raises(ConfigError, match="reserved environment"):
        load_config_bytes(encode(value))

    value = generic_value()
    value["checks"][0]["platform"]["windows"]["environment"] = {
        "Path": "one",
        "PATH": "two",
    }
    with pytest.raises(ConfigError, match="case-colliding"):
        load_config_bytes(encode(value))


def test_repository_local_launcher_must_be_review_required() -> None:
    value = generic_value()
    value["scope"]["review_required_paths"] = ["/.release-gate.yaml"]
    with pytest.raises(ConfigError, match="launcher"):
        load_config_bytes(encode(value))


@pytest.mark.parametrize("token", ["&&", "||", "|", ";", ">", "$(bad)", "`bad`"])
def test_shell_syntax_is_rejected(token: str) -> None:
    value = generic_value()
    value["checks"][0]["argv"].append(token)
    with pytest.raises(ConfigError, match="shell syntax"):
        load_config_bytes(encode(value))


def test_diagnostics_do_not_echo_environment_values() -> None:
    value = generic_value()
    secret = "super-secret-value"
    value["checks"][0]["environment"] = {"HOME": secret}

    with pytest.raises(ConfigError) as caught:
        load_config_bytes(encode(value), source="policy.yaml")

    assert secret not in str(caught.value)


def test_candidate_only_policy_does_not_require_base_workspace() -> None:
    value = generic_value()
    value["checks"][0]["mode"] = "candidate"
    value["checks"][0]["assertions"] = [
        item
        for item in value["checks"][0]["assertions"]
        if item["comparison"] == "candidate"
    ]
    config = load_config_bytes(encode(value))

    assert config.requires_base_workspace is False


def test_missing_file_reports_a_safe_source_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(ConfigError) as caught:
        load_config(missing)
    assert str(missing) in str(caught.value)
