from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "release-gate" / "SKILL.md"


def test_portable_skill_has_discoverable_minimal_contract() -> None:
    text = SKILL.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    metadata = yaml.safe_load(frontmatter)
    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == "release-gate"
    assert metadata["description"].startswith("Use only when explicitly invoked")
    assert "Do not invoke implicitly" in metadata["description"]
    assert len(text.splitlines()) < 180


def test_skill_dispatches_only_three_explicit_operations() -> None:
    text = SKILL.read_text(encoding="utf-8")
    required = [
        "Explicit invocation guard",
        "init | validate | run",
        "Missing or unknown subcommand",
        "no operational tool call",
        "release-gate --version",
        "release-gate 0.2.2",
        "release-gate init --repo <repo> --from-config <temporary-approved-config>",
        "release-gate validate --repo <repo>",
        "release-gate run",
        ".release-gate.yaml",
        "result.json",
        "PASS",
        "FAIL",
        "NEEDS_HUMAN",
        "Do not edit",
        "Do not retry",
        "Do not reinterpret",
        "does not merge or deploy",
    ]
    for phrase in required:
        assert phrase in text


def test_guided_init_contract_is_approval_based_and_treats_repo_as_untrusted() -> None:
    text = SKILL.read_text(encoding="utf-8")
    required = [
        "manifests, lockfiles, CI configuration, and declared scripts",
        "check only whether `.release-gate.yaml` exists",
        "read `.gitignore`",
        "untrusted data",
        "Never execute repository code",
        "Never read environment values",
        "source file and key",
        "each command's inclusion",
        "candidate or differential mode",
        "severity",
        "preparation and network behavior",
        "scope",
        "inherited environment variable names",
        "combined final diff",
        ".gitignore",
        "/.release-gate/runs/",
        "explicit approval",
        "secure temporary",
        "Refuse to overwrite",
        "references/initialization.md",
        "references/config-v1.schema.json",
        "Every field",
    ]
    for phrase in required:
        assert phrase in text


def test_run_contract_preserves_verdicts_and_error_exit_semantics() -> None:
    text = SKILL.read_text(encoding="utf-8")
    required = [
        "explicit base ref",
        "exactly once",
        "exits 0, 1, or 2",
        "exit 3 or 4",
        "no verdict",
        "Never edit policy or evidence",
        "Never retry, merge, or deploy",
    ]
    for phrase in required:
        assert phrase in text


def test_compatibility_reference_pins_source_version() -> None:
    compatibility = json.loads(
        (SKILL.parent / "references" / "compatibility.json").read_text(encoding="utf-8")
    )
    assert compatibility == {"cli": {"name": "release-gate", "version": "0.2.2"}}


def test_bundled_config_schema_is_the_exact_cli_schema() -> None:
    bundled = SKILL.parent / "references" / "config-v1.schema.json"
    canonical = ROOT / "src" / "release_gate" / "schemas" / "config-v1.schema.json"
    assert bundled.read_bytes() == canonical.read_bytes()


def test_initialization_reference_is_self_contained_and_has_no_network_field() -> None:
    text = (SKILL.parent / "references" / "initialization.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "version: 1",
        "allowed_paths",
        "checks:",
        "argv:",
        "candidate",
        "differential",
        "blocking",
        "advisory",
        "informational",
        "inherit_environment",
        "no `network` field",
        "without a shell",
        "Do not guess",
    ):
        assert phrase in text


def test_skill_ui_metadata_is_host_neutral() -> None:
    metadata = yaml.safe_load(
        (SKILL.parent / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )
    assert set(metadata) == {"interface", "policy"}
    assert "$release-gate" in metadata["interface"]["default_prompt"]
    assert "explicit" in metadata["interface"]["default_prompt"].lower()
    assert metadata["policy"] == {"allow_implicit_invocation": False}
    assert "dependencies" not in metadata
