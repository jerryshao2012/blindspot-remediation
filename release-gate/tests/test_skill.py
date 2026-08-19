from __future__ import annotations

import json
from pathlib import Path

import yaml

from release_gate import __version__

ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "release-gate" / "SKILL.md"


def test_portable_skill_has_discoverable_minimal_contract() -> None:
    text = SKILL.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    metadata = yaml.safe_load(frontmatter)
    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == "release-gate"
    assert metadata["description"].startswith("Use only when explicitly invoked")
    assert "report its version" in metadata["description"]
    assert "Do not invoke implicitly" in metadata["description"]
    assert len(text.splitlines()) < 180
    assert max(map(len, text.splitlines())) <= 130


def test_skill_dispatches_only_three_explicit_operations() -> None:
    text = SKILL.read_text(encoding="utf-8")
    required = [
        "Explicit invocation guard",
        "init | validate | run",
        "Missing or unknown subcommand",
        "no operational tool call",
        "release-gate --version",
        f"release-gate {__version__}",
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


def test_graphify_is_portable_optional_read_only_and_non_gating() -> None:
    text = " ".join(SKILL.read_text(encoding="utf-8").split())
    required = [
        "host-accessible read-only `graphify query` capability",
        "`graphify-out/graph.json` already exists",
        "explicitly marked stale",
        "untrusted hints",
        "Do not install Graphify",
        "build, update, reflect, save-result, or hook",
        "must not block or retry Release Gate",
        "must not change policy or verdict",
    ]
    for phrase in required:
        assert phrase in text


def test_graphify_init_hints_never_authorize_commands() -> None:
    text = SKILL.read_text(encoding="utf-8")
    init = " ".join(
        text.split("## init", 1)[1].split("## validate", 1)[0].split()
    )
    for phrase in (
        "likely manifests, lockfiles, CI configuration, and declared scripts",
        "existing allowed source categories",
        "direct source file and key citation",
        "never authorizes or supplies commands",
    ):
        assert phrase in init


def test_graphify_is_never_used_for_validate() -> None:
    text = SKILL.read_text(encoding="utf-8")
    validate = " ".join(
        text.split("## validate", 1)[1].split("## run", 1)[0].split()
    )
    assert "Never invoke Graphify" in validate


def test_graphify_run_advisory_follows_exact_result_and_is_bounded() -> None:
    text = SKILL.read_text(encoding="utf-8")
    run = " ".join(
        text.split("## run", 1)[1].split("## Integrity rules", 1)[0].split()
    )
    for phrase in (
        "parse and report the exact result first",
        "bounded query",
        "`result.json` `scope.changed_paths`",
        "clearly separate, non-gating Graphify advisory",
        "For exit 3 or 4, do not query Graphify",
        "Preserve the exact verdict, reason codes, configured check order, and "
        "evidence",
    ):
        assert phrase in run


def test_assistant_version_is_informational_and_has_no_operational_call() -> None:
    text = SKILL.read_text(encoding="utf-8")
    version = " ".join(
        text.split("## Informational `--version`", 1)[1]
        .split("## Compatibility preflight", 1)[0]
        .split()
    )

    for phrase in (
        "/release-gate --version",
        "$release-gate --version",
        "references/compatibility.json",
        f"Report exactly `release-gate {__version__}` and stop",
        "Do not call the CLI",
        "do not run compatibility preflight",
        "do not consider Graphify",
        "do not perform an `init`, `validate`, or `run` operation",
    ):
        assert phrase in version


def test_compatibility_reference_pins_source_version() -> None:
    compatibility = json.loads(
        (SKILL.parent / "references" / "compatibility.json").read_text(encoding="utf-8")
    )
    assert compatibility == {"cli": {"name": "release-gate", "version": __version__}}


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
