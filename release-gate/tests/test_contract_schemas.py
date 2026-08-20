from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
EXAMPLE_DIR = ROOT / "examples"


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def errors(schema: dict[str, Any], value: Any) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [error.message for error in validator.iter_errors(value)]


@pytest.mark.parametrize(
    "name",
    [
        "config-v1.schema.json",
        "result-v1.schema.json",
        "manifest-v1.schema.json",
        "gate-decisions-v1.schema.json",
    ],
)
def test_checked_in_schemas_are_valid_draft_2020_12(name: str) -> None:
    Draft202012Validator.check_schema(load_schema(name))


@pytest.mark.parametrize("example", ["generic", "python", "node"])
def test_examples_validate_against_configuration_contract(example: str) -> None:
    value = yaml.safe_load(
        (EXAMPLE_DIR / example / ".release-gate.yaml").read_text(encoding="utf-8")
    )
    assert errors(load_schema("config-v1.schema.json"), value) == []


def test_configuration_rejects_unknown_fields_and_versions() -> None:
    schema = load_schema("config-v1.schema.json")
    value = yaml.safe_load(
        (EXAMPLE_DIR / "generic" / ".release-gate.yaml").read_text(encoding="utf-8")
    )

    unknown = {**value, "unknown": True}
    assert errors(schema, unknown)

    wrong_version = {**value, "version": 2}
    assert errors(schema, wrong_version)


@pytest.mark.parametrize(
    "identifier",
    ["con", "NUL.txt", "bad.", "bad:name", "x" * 65],
)
def test_portable_control_identifier_rejects_unsafe_values(identifier: str) -> None:
    schema = load_schema("config-v1.schema.json")
    value = yaml.safe_load(
        (EXAMPLE_DIR / "generic" / ".release-gate.yaml").read_text(encoding="utf-8")
    )
    value["checks"][0]["id"] = identifier
    assert errors(schema, value)


def test_json_pointer_contract_accepts_root_pointer() -> None:
    schema = load_schema("config-v1.schema.json")
    value = yaml.safe_load(
        (EXAMPLE_DIR / "generic" / ".release-gate.yaml").read_text(encoding="utf-8")
    )
    value["checks"][0]["assertions"][0]["metric"] = ""
    assert errors(schema, value) == []


def test_format_checker_is_required_for_timestamp_rejection() -> None:
    schema = load_schema("result-v1.schema.json")
    timestamp_schema = schema["$defs"]["timestamp"]
    invalid = "2026-02-30T12:00:00Z"

    assert list(Draft202012Validator(timestamp_schema).iter_errors(invalid)) == []
    assert list(
        Draft202012Validator(
            timestamp_schema, format_checker=FormatChecker()
        ).iter_errors(invalid)
    )


def test_reason_code_registry_is_closed_and_shared() -> None:
    result_schema = load_schema("result-v1.schema.json")
    manifest_schema = load_schema("manifest-v1.schema.json")
    result_codes = set(result_schema["$defs"]["runReasonCodes"]["items"]["enum"])
    manifest_codes = set(manifest_schema["$defs"]["runReasonCodes"]["items"]["enum"])

    assert result_codes == manifest_codes
    assert "POLICY_FILE_CHANGED" in result_codes
    assert "CONTROL_LAUNCHER_REVIEW" in result_codes
    assert "UNKNOWN_VENDOR_REASON" not in result_codes
