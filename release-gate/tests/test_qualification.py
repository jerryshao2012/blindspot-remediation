from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from release_gate import __version__

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "qualification-v1.schema.json"
VALIDATOR = ROOT / "scripts" / "validate_qualification.py"
TEMPLATE = (
    ROOT / "qualification" / f"release-gate-v{__version__}-rc.1.pending.json"
)
SURFACES = {
    "Copilot CLI",
    "Codex CLI",
    "Codex IDE",
    "Claude Code",
    "Antigravity IDE",
    "Antigravity CLI",
}
CASES = {
    "init-generic",
    "init-python",
    "init-node",
    "init-ambiguous-monorepo",
    "init-cancel",
    "init-existing-policy",
    "validate-invalid-config",
    "operation-missing-cli",
    "operation-mismatched-cli",
    "operation-permission-failure",
    "init-adversarial-repository",
    "run-pass",
    "run-fail",
    "run-needs-human",
    "run-exit-3",
    "run-exit-4",
}
OUTCOMES = {
    **{case: "EXPECTED_GUARD" for case in CASES},
    "run-pass": "PASS",
    "run-fail": "FAIL",
    "run-needs-human": "NEEDS_HUMAN",
    "run-exit-3": "EXIT_3_NO_VERDICT",
    "run-exit-4": "EXIT_4_NO_VERDICT",
}
GRAPHIFY_OBSERVATIONS = {
    "operation-mismatched-cli": ("RG-GRAPHIFY-PREFLIGHT-BEFORE-QUERY",),
    "init-python": (
        "RG-GRAPHIFY-PREFLIGHT-BEFORE-QUERY",
        "RG-GRAPHIFY-INIT-EXISTING-GRAPH-READONLY-QUERY",
        "RG-GRAPHIFY-INIT-DIRECT-SOURCE-VERIFICATION",
    ),
    "init-adversarial-repository": (
        "RG-GRAPHIFY-MISSING-NONBLOCKING",
        "RG-GRAPHIFY-STALE-NONBLOCKING",
        "RG-GRAPHIFY-QUERY-FAILURE-NONBLOCKING",
    ),
    "validate-invalid-config": ("RG-GRAPHIFY-VALIDATE-NO-QUERY",),
    **{
        case: (
            "RG-GRAPHIFY-PREFLIGHT-BEFORE-QUERY",
            "RG-GRAPHIFY-RUN-RESULT-FIRST",
            "RG-GRAPHIFY-RUN-QUERY-COUNT-0-OR-1",
            "RG-GRAPHIFY-RUN-SCOPE-CHANGED-PATHS-ONLY",
            "RG-GRAPHIFY-RUN-ADVISORY-SEPARATE-NON-GATING",
            "RG-GRAPHIFY-RUN-VERDICT-UNCHANGED",
        )
        for case in ("run-pass", "run-fail", "run-needs-human")
    },
    "run-exit-3": ("RG-GRAPHIFY-RUN-ERROR-NO-QUERY",),
    "run-exit-4": ("RG-GRAPHIFY-RUN-ERROR-NO-QUERY",),
}


def _load_validator() -> object:
    spec = importlib.util.spec_from_file_location("qualification_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _asset(name: str) -> dict[str, str]:
    return {"name": name, "sha256": hashlib.sha256(name.encode()).hexdigest()}


def _reference(uri: str) -> dict[str, str]:
    return {"uri": uri, "sha256": hashlib.sha256(uri.encode()).hexdigest()}


def _complete_evidence() -> dict[str, object]:
    wheel = f"release_gate-{__version__}-py3-none-any.whl"
    archives = {
        "Copilot CLI": f"release-gate-skill-copilot-{__version__}.tar.gz",
        "Codex CLI": f"release-gate-skill-codex-{__version__}.tar.gz",
        "Codex IDE": f"release-gate-skill-codex-{__version__}.tar.gz",
        "Claude Code": f"release-gate-skill-claude-code-{__version__}.tar.gz",
        "Antigravity IDE": f"release-gate-skill-antigravity-{__version__}.tar.gz",
        "Antigravity CLI": f"release-gate-skill-antigravity-{__version__}.tar.gz",
    }
    asset_names = {
        wheel,
        f"release_gate-{__version__}.tar.gz",
        *archives.values(),
        "SHA256SUMS",
    }
    assets = [_asset(name) for name in sorted(asset_names)]
    hashes = {item["name"]: item["sha256"] for item in assets}
    surfaces = []
    for name in sorted(SURFACES):
        slug = name.casefold().replace(" ", "-")
        surfaces.append(
            {
                "surface": name,
                "host_version": "1.2.3",
                "model_version": "gpt-5.4-2026-08-18",
                "os": "macOS 15.6 arm64",
                "node_version": "22.20.0",
                "cli_wheel": {"name": wheel, "sha256": hashes[wheel]},
                "skill_archive": {
                    "name": archives[name],
                    "sha256": hashes[archives[name]],
                },
                "exact_prompt": "/release-gate validate",
                "explicit_selection": True,
                "invocation": "explicit command",
                "permissions_tools": ["read repository", "run release-gate"],
                "baseline_without_skill": "command was not routed",
                "installed_rc_observation": "command routed after pinned install",
                "result": {
                    "status": "pass",
                    "details": "Observed expected routing and safety behavior.",
                    "failure_details": None,
                },
                "timestamp": "2026-08-18T00:00:00Z",
                "evidence_reference": _reference(f"evidence/{slug}/session.json"),
                "case_results": [
                    {
                        "case": case,
                        "exact_prompt": f"/release-gate validate # corpus {case}",
                        "permissions_tools": [
                            "read repository",
                            "run release-gate",
                        ],
                        "observed_effects": " ".join(
                            (
                                f"Observed expected effects for {case}.",
                                *GRAPHIFY_OBSERVATIONS.get(case, ()),
                            )
                        ),
                        "observed_outcome": OUTCOMES[case],
                        "result": {
                            "status": "pass",
                            "details": f"Expected behavior confirmed for {case}.",
                            "failure_details": None,
                        },
                        "evidence_reference": _reference(
                            f"evidence/{slug}/{case}.json"
                        ),
                    }
                    for case in sorted(CASES)
                ],
            }
        )
    return {
        "schema_version": 1,
        "qualification_status": "complete",
        "release": {
            "tag": f"release-gate-v{__version__}-rc.1",
            "commit": "a" * 40,
        },
        "installer": {"skills_cli_version": "1.5.23", "node_version": "22.20.0"},
        "assets": assets,
        "surfaces": surfaces,
    }


def test_pending_template_is_schema_valid_but_not_promotable() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    pending = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(pending)
    assert pending["qualification_status"] == "pending"
    assert all(item["result"]["status"] == "pending" for item in pending["surfaces"])
    validator = _load_validator()
    with pytest.raises(ValueError, match="not complete"):
        validator.validate_evidence(
            pending, expected_tag=f"release-gate-v{__version__}-rc.1"
        )


def test_complete_evidence_requires_exact_six_passing_surfaces_and_hashes() -> None:
    validator = _load_validator()
    validate = validator.validate_evidence
    evidence = _complete_evidence()
    validate(
        evidence,
        expected_tag=f"release-gate-v{__version__}-rc.1",
        expected_commit="a" * 40,
    )

    duplicate = json.loads(json.dumps(evidence))
    duplicate["surfaces"][1]["surface"] = duplicate["surfaces"][0]["surface"]
    with pytest.raises(ValueError, match="exactly the six"):
        validate(duplicate, expected_tag=f"release-gate-v{__version__}-rc.1")

    failing = json.loads(json.dumps(evidence))
    failing["surfaces"][0]["result"]["status"] = "fail"
    failing["surfaces"][0]["result"]["failure_details"] = "host mismatch"
    with pytest.raises(ValueError, match="did not pass"):
        validate(failing, expected_tag=f"release-gate-v{__version__}-rc.1")

    mismatched = json.loads(json.dumps(evidence))
    mismatched["surfaces"][0]["cli_wheel"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="wheel hash"):
        validate(mismatched, expected_tag=f"release-gate-v{__version__}-rc.1")


def test_complete_evidence_rejects_wrong_dependency_tag_and_commit() -> None:
    validator = _load_validator()
    validate = validator.validate_evidence
    evidence = _complete_evidence()
    for mutate, message in (
        (
            lambda item: item["installer"].update(skills_cli_version="latest"),
            "skills CLI",
        ),
        (lambda item: item["installer"].update(node_version="22.19.9"), "Node"),
        (lambda item: item["release"].update(tag="release-gate-v0.2.2"), "tag"),
        (lambda item: item["release"].update(commit="b" * 40), "commit"),
    ):
        candidate = json.loads(json.dumps(evidence))
        mutate(candidate)
        with pytest.raises(ValueError, match=message):
            validate(
                candidate,
                expected_tag=f"release-gate-v{__version__}-rc.1",
                expected_commit="a" * 40,
            )


def test_complete_evidence_rejects_placeholder_sentinels_and_zero_values() -> None:
    validator = _load_validator()
    validate = validator.validate_evidence
    evidence = _complete_evidence()
    mutations = (
        lambda item: item["surfaces"][0].update(host_version="PENDING: version"),
        lambda item: item["surfaces"][0].update(
            evidence_reference=_reference("evidence/example.json")
        ),
        lambda item: item["surfaces"][0].update(timestamp="1970-01-01T00:00:00Z"),
        lambda item: item["release"].update(commit="0" * 40),
        lambda item: item["assets"][0].update(sha256="0" * 64),
        lambda item: item["surfaces"][0]["case_results"][0].update(
            observed_effects="TODO"
        ),
        lambda item: item["surfaces"][0].update(node_version="22.19.9"),
        lambda item: item["surfaces"][0]["evidence_reference"].update(sha256="0" * 64),
    )
    for mutate in mutations:
        candidate = json.loads(json.dumps(evidence))
        mutate(candidate)
        with pytest.raises(ValueError):
            validate(candidate, expected_tag=f"release-gate-v{__version__}-rc.1")


def test_complete_evidence_requires_exact_passing_corpus_per_surface() -> None:
    validator = _load_validator()
    validate = validator.validate_evidence
    evidence = _complete_evidence()
    validate(evidence, expected_tag=f"release-gate-v{__version__}-rc.1")

    missing = json.loads(json.dumps(evidence))
    missing["surfaces"][0]["case_results"].pop()
    with pytest.raises(ValueError, match="corpus"):
        validate(missing, expected_tag=f"release-gate-v{__version__}-rc.1")

    duplicate = json.loads(json.dumps(evidence))
    duplicate["surfaces"][0]["case_results"][1]["case"] = duplicate["surfaces"][0][
        "case_results"
    ][0]["case"]
    with pytest.raises(ValueError, match="corpus"):
        validate(duplicate, expected_tag=f"release-gate-v{__version__}-rc.1")

    failing = json.loads(json.dumps(evidence))
    failing["surfaces"][0]["case_results"][0]["result"]["status"] = "fail"
    with pytest.raises(ValueError, match="case did not pass"):
        validate(failing, expected_tag=f"release-gate-v{__version__}-rc.1")

    wrong_outcome = json.loads(json.dumps(evidence))
    run_pass = next(
        case
        for case in wrong_outcome["surfaces"][0]["case_results"]
        if case["case"] == "run-pass"
    )
    run_pass["observed_outcome"] = "FAIL"
    with pytest.raises(ValueError, match="outcome"):
        validate(wrong_outcome, expected_tag=f"release-gate-v{__version__}-rc.1")

    reused_reference = json.loads(json.dumps(evidence))
    reused_reference["surfaces"][1]["case_results"][0]["evidence_reference"] = (
        reused_reference["surfaces"][0]["case_results"][0]["evidence_reference"]
    )
    with pytest.raises(ValueError, match="evidence reference"):
        validate(reused_reference, expected_tag=f"release-gate-v{__version__}-rc.1")

    reused_digest = json.loads(json.dumps(evidence))
    reused_digest["surfaces"][1]["case_results"][0]["evidence_reference"]["sha256"] = (
        reused_digest["surfaces"][0]["case_results"][0]["evidence_reference"]["sha256"]
    )
    with pytest.raises(ValueError, match="evidence reference"):
        validate(reused_digest, expected_tag=f"release-gate-v{__version__}-rc.1")


@pytest.mark.parametrize(
    ("case_name", "marker"),
    [
        (case_name, marker)
        for case_name, markers in GRAPHIFY_OBSERVATIONS.items()
        for marker in markers
    ],
)
def test_complete_evidence_requires_each_graphify_observation(
    case_name: str, marker: str
) -> None:
    validator = _load_validator()
    validate = validator.validate_evidence
    evidence = _complete_evidence()
    validate(evidence, expected_tag=f"release-gate-v{__version__}-rc.1")
    target = next(
        case
        for case in evidence["surfaces"][0]["case_results"]
        if case["case"] == case_name
    )
    target["observed_effects"] = target["observed_effects"].replace(marker, "")
    with pytest.raises(ValueError, match="Graphify observation"):
        validate(evidence, expected_tag=f"release-gate-v{__version__}-rc.1")


@pytest.mark.parametrize("surface_name", sorted(SURFACES))
def test_graphify_observations_are_required_for_every_surface(
    surface_name: str,
) -> None:
    validator = _load_validator()
    validate = validator.validate_evidence
    evidence = _complete_evidence()
    surface = next(
        item for item in evidence["surfaces"] if item["surface"] == surface_name
    )
    run_pass = next(
        case for case in surface["case_results"] if case["case"] == "run-pass"
    )
    run_pass["observed_effects"] = "Gate result recorded without tool-call detail."
    with pytest.raises(ValueError, match="Graphify observation"):
        validate(evidence, expected_tag=f"release-gate-v{__version__}-rc.1")


def test_pending_template_cannot_be_promoted_by_flipping_statuses() -> None:
    validator = _load_validator()
    pending = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    pending["qualification_status"] = "complete"
    for surface in pending["surfaces"]:
        surface["explicit_selection"] = True
        surface["result"]["status"] = "pass"
    with pytest.raises(ValueError):
        validator.validate_evidence(
            pending, expected_tag=f"release-gate-v{__version__}-rc.1"
        )


def test_node_version_is_strict_three_component_stable_semver() -> None:
    validator = _load_validator()
    parse = validator._version_tuple
    assert parse("22.20.0") == (22, 20, 0)
    assert parse("v22.20.0") == (22, 20, 0)
    for invalid in (
        "22.20.0-rc.1",
        "22.20.0+build.1",
        "22.20.0.1",
        "22.20",
        "node-22.20.0",
    ):
        with pytest.raises(ValueError, match="Node version"):
            parse(invalid)
