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
    assert len(text.splitlines()) < 200
    assert max(map(len, text.splitlines())) <= 130


def test_skill_dispatches_only_explicit_operations() -> None:
    text = SKILL.read_text(encoding="utf-8")
    required = [
        "Explicit invocation guard",
        "init | validate | run | repair",
        "Missing or unknown subcommand",
        "no operational tool call",
        "release-gate --version",
        f"release-gate {__version__}",
        "release-gate init --repo <repo> --from-config <temporary-approved-config>",
        "release-gate validate --repo <repo>",
        "release-gate run",
        "release-gate repair-start",
        "references/repair.md",
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


def test_guided_init_requires_an_explicit_assurance_map() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assurance = (SKILL.parent / "references" / "assurance.md").read_text(
        encoding="utf-8"
    )

    for phrase in (
        "references/assurance.md",
        "failure mode or assurance claim",
        "candidate or differential mode",
        "N-A",
        "UNAVAILABLE",
        "SUBSTITUTED",
        "expected-layer manifest",
        "negative controls",
        "fail closed",
        "byte-for-byte",
    ):
        assert phrase in text or phrase in assurance
    assert "user-approved assurance map" in text


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


def test_run_contract_reports_exact_check_status_and_aggregate_boundary() -> None:
    run = " ".join(
        SKILL.read_text(encoding="utf-8")
        .split("## run", 1)[1]
        .split("## Integrity rules", 1)[0]
        .split()
    )
    for phrase in (
        "each configured check's exact status",
        "`ERROR` and `SKIPPED`",
        "unverified",
        "cannot independently attest unreported layers inside an aggregate command",
        "configured policy",
    ):
        assert phrase in run


def test_run_contract_reports_non_gating_observability_before_graphify() -> None:
    text = SKILL.read_text(encoding="utf-8")
    run = " ".join(text.split("## run", 1)[1].split("## Integrity rules", 1)[0].split())
    required = [
        "Call the gate exactly once",
        "`RESULT:` path",
        "report `result.json` and its exact verdict first",
        "references/gate-decisions-v1.schema.json",
        "non-gating rolling 10 and rolling 100",
        "partial warm-up windows",
        "diagnostics",
        "`SNAPSHOT:`",
        "`DASHBOARD:`",
        "`OBSERVABILITY_DATA:`",
        "refresh warnings",
        "Do not retry",
        "do not change the verdict",
        "Graphify advisory last",
    ]
    for phrase in required:
        assert phrase in run
    assert run.index("report `result.json` and its exact verdict first") < run.index(
        "references/gate-decisions-v1.schema.json"
    )
    assert run.index("references/gate-decisions-v1.schema.json") < run.index(
        "Graphify advisory last"
    )
    assert run.index("For exit 3 or 4") < run.index("Graphify advisory last")
    assert run.index("tamper-evident") < run.index("Graphify advisory last")


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
    init = " ".join(text.split("## init", 1)[1].split("## validate", 1)[0].split())
    for phrase in (
        "likely manifests, lockfiles, CI configuration, and declared scripts",
        "existing allowed source categories",
        "direct source file and key citation",
        "never authorizes or supplies commands",
    ):
        assert phrase in init


def test_graphify_is_never_used_for_validate() -> None:
    text = SKILL.read_text(encoding="utf-8")
    validate = " ".join(text.split("## validate", 1)[1].split("## run", 1)[0].split())
    assert "Never invoke Graphify" in validate


def test_graphify_run_advisory_follows_exact_result_and_is_bounded() -> None:
    text = SKILL.read_text(encoding="utf-8")
    run = " ".join(text.split("## run", 1)[1].split("## Integrity rules", 1)[0].split())
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


def test_bundled_observability_schema_is_the_exact_cli_schema() -> None:
    bundled = SKILL.parent / "references" / "gate-decisions-v1.schema.json"
    canonical = (
        ROOT / "src" / "release_gate" / "schemas" / "gate-decisions-v1.schema.json"
    )
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


def test_repair_reference_is_present_and_well_formed() -> None:
    text = (SKILL.parent / "references" / "repair.md").read_text(encoding="utf-8")
    for phrase in (
        "release-gate repair-start",
        "release-gate repair-approve",
        "release-gate repair-request",
        "release-gate repair-evaluate",
        "release-gate repair-apply",
        "release-gate repair-cancel",
        "REPAIR_SESSION:",
        "REPAIR_STATE:",
        "NEXT_ACTION:",
    ):
        assert phrase in text


def test_repair_contract_explicitly_loops_and_bounds_graphify() -> None:
    text = " ".join(SKILL.read_text(encoding="utf-8").split())
    repair_reference = " ".join(
        (SKILL.parent / "references" / "repair.md")
        .read_text(encoding="utf-8")
        .split()
    )
    for phrase in (
        "`repairing` / `edit_workspace`",
        "call `release-gate repair-request` again",
        "return to this step",
        "The controller's attempt cap is authoritative",
        "one host-accessible, read-only",
        "eligible C0 only",
        "Bound the query to C0 failed checks and approved or changed paths",
        "verify cited source files directly",
        "Missing, stale, failing, malformed, or adversarial Graphify is non-blocking",
        "never use it to authorize commands",
        "bypass approval",
    ):
        assert phrase in text
    for phrase in (
        "after eligible C0 assessment",
        "`built_at_commit` matches the repair session's base commit",
        "one read-only `graphify query`",
        "failed checks and approved paths",
        "separate untrusted hints",
        "verify every cited source file directly",
        "must not retry Graphify",
        "must not change scope, budget, verdict, commands, or approvals",
    ):
        assert phrase in repair_reference
