#!/usr/bin/env python3
"""Validate qualification evidence before v0.2.3 promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

SURFACES = {
    "Copilot CLI": "copilot",
    "Codex CLI": "codex",
    "Codex IDE": "codex",
    "Claude Code": "claude-code",
    "Antigravity IDE": "antigravity",
    "Antigravity CLI": "antigravity",
}
VERSION_RE = re.compile(r"^release-gate-v([0-9]+\.[0-9]+\.[0-9]+)-rc\.1$")
SENTINEL_RE = re.compile(
    r"(?:^|[^a-z0-9])(pending|todo|tbd|placeholder|replace(?: me)?|"
    r"not[ -]?run|fake|example)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)
CORPUS = {
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
EXPECTED_OUTCOMES = {
    **{case: "EXPECTED_GUARD" for case in CORPUS},
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


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?([0-9]+)\.([0-9]+)\.([0-9]+)", value)
    if match is None:
        raise ValueError("Node version is not a semantic version")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _asset_map(evidence: dict[str, Any]) -> dict[str, str]:
    assets: dict[str, str] = {}
    for item in evidence["assets"]:
        name = item["name"]
        if name in assets:
            raise ValueError(f"duplicate asset evidence: {name}")
        assets[name] = item["sha256"]
    return assets


def _reject_sentinels(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, str):
        if not value.strip() or SENTINEL_RE.search(value):
            location = ".".join(path) or "document"
            raise ValueError(f"placeholder or empty value at {location}")
    elif isinstance(value, dict):
        for key, child in value.items():
            _reject_sentinels(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_sentinels(child, (*path, str(index)))


def _validate_timestamp(value: str, surface: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.astimezone(UTC).year < 2020:
        raise ValueError(f"surface timestamp is an epoch or lacks timezone: {surface}")


def _record_reference(reference: dict[str, str], seen: set[str], location: str) -> None:
    uri = reference["uri"]
    digest = reference["sha256"]
    if f"uri:{uri}" in seen or f"sha256:{digest}" in seen:
        raise ValueError(f"evidence reference is not globally unique: {location}")
    if digest == "0" * 64:
        raise ValueError(f"evidence reference uses zero hash: {location}")
    seen.update((f"uri:{uri}", f"sha256:{digest}"))


def validate_evidence(
    evidence: dict[str, Any],
    *,
    expected_tag: str,
    expected_commit: str | None = None,
    assets_dir: Path | None = None,
) -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "schemas/qualification-v1.schema.json").read_text(encoding="utf-8")
    )
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(evidence)
    except ValidationError as error:
        location = ".".join(str(part) for part in error.absolute_path) or "document"
        raise ValueError(
            f"qualification schema validation failed at {location}: {error.message}"
        ) from error
    if evidence["qualification_status"] != "complete":
        raise ValueError("qualification is not complete")
    _reject_sentinels(evidence)
    release = evidence["release"]
    if release["tag"] != expected_tag:
        raise ValueError("qualification tag does not match the requested RC tag")
    match = VERSION_RE.fullmatch(expected_tag)
    if match is None:
        raise ValueError("qualification tag must be an rc.1 tag")
    version = match.group(1)
    if expected_commit is not None and release["commit"] != expected_commit:
        raise ValueError("qualification commit does not match the RC commit")
    if release["commit"] == "0" * 40:
        raise ValueError("qualification commit cannot be the zero sentinel")
    installer = evidence["installer"]
    if installer["skills_cli_version"] != "1.5.23":
        raise ValueError("skills CLI version must be exactly 1.5.23")
    if _version_tuple(installer["node_version"]) < (22, 20, 0):
        raise ValueError("Node version must be 22.20.0 or newer")

    assets = _asset_map(evidence)
    if any(digest == "0" * 64 for digest in assets.values()):
        raise ValueError("qualification asset hashes cannot use the zero sentinel")
    wheel = f"release_gate-{version}-py3-none-any.whl"
    expected_assets = {
        wheel,
        f"release_gate-{version}.tar.gz",
        *(
            f"release-gate-skill-{host}-{version}.tar.gz"
            for host in set(SURFACES.values())
        ),
        "SHA256SUMS",
    }
    if set(assets) != expected_assets:
        raise ValueError("qualification does not record every exact release asset")
    if assets_dir is not None:
        actual = {path.name for path in assets_dir.iterdir()}
        if actual != expected_assets:
            raise ValueError("downloaded assets do not match qualification asset names")
        for name, expected_hash in assets.items():
            digest = hashlib.sha256((assets_dir / name).read_bytes()).hexdigest()
            if digest != expected_hash:
                raise ValueError(f"downloaded asset hash mismatch: {name}")

    surfaces = evidence["surfaces"]
    surface_names = [item["surface"] for item in surfaces]
    if len(surface_names) != 6 or set(surface_names) != set(SURFACES):
        raise ValueError(
            "qualification must contain exactly the six advertised surfaces"
        )
    if len(surface_names) != len(set(surface_names)):
        raise ValueError(
            "qualification must contain exactly the six advertised surfaces"
        )
    evidence_references: set[str] = set()
    for item in surfaces:
        name = item["surface"]
        _validate_timestamp(item["timestamp"], name)
        if _version_tuple(item["node_version"]) < (22, 20, 0):
            raise ValueError(f"surface Node version must be 22.20.0 or newer: {name}")
        _record_reference(item["evidence_reference"], evidence_references, name)
        if item["result"]["status"] != "pass":
            raise ValueError(f"surface did not pass: {name}")
        if item["result"]["failure_details"] not in (None, ""):
            raise ValueError(f"passing surface records failure details: {name}")
        if item["explicit_selection"] is not True:
            raise ValueError(f"surface was not explicitly selected: {name}")
        wheel_record = item["cli_wheel"]
        if wheel_record != {"name": wheel, "sha256": assets[wheel]}:
            raise ValueError(f"surface wheel hash does not match assets: {name}")
        archive = f"release-gate-skill-{SURFACES[name]}-{version}.tar.gz"
        if item["skill_archive"] != {
            "name": archive,
            "sha256": assets[archive],
        }:
            raise ValueError(f"surface archive hash does not match assets: {name}")
        cases = item["case_results"]
        case_names = [case["case"] for case in cases]
        if len(case_names) != len(CORPUS) or set(case_names) != CORPUS:
            raise ValueError(f"surface corpus is incomplete or duplicated: {name}")
        if len(case_names) != len(set(case_names)):
            raise ValueError(f"surface corpus is incomplete or duplicated: {name}")
        for case in cases:
            expected_outcome = EXPECTED_OUTCOMES[case["case"]]
            if case["observed_outcome"] != expected_outcome:
                raise ValueError(
                    f"surface case outcome mismatch: {name}/{case['case']}"
                )
            if case["result"]["status"] != "pass":
                raise ValueError(f"surface case did not pass: {name}/{case['case']}")
            if case["result"]["failure_details"] not in (None, ""):
                raise ValueError(
                    f"passing case records failure details: {name}/{case['case']}"
                )
            for marker in GRAPHIFY_OBSERVATIONS.get(case["case"], ()):
                if marker not in case["observed_effects"]:
                    raise ValueError(
                        "required Graphify observation is absent: "
                        f"{name}/{case['case']}/{marker}"
                    )
            _record_reference(
                case["evidence_reference"],
                evidence_references,
                f"{name}/{case['case']}",
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--expected-tag", required=True)
    parser.add_argument("--expected-commit")
    parser.add_argument("--assets-dir", type=Path)
    parser.add_argument(
        "--allow-pending-schema-only",
        action="store_true",
        help="validate document shape but never authorize promotion",
    )
    arguments = parser.parse_args()
    evidence = json.loads(arguments.evidence.read_text(encoding="utf-8"))
    if arguments.allow_pending_schema_only:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "schemas/qualification-v1.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(evidence)
        print("schema valid; pending evidence is not promotable")
        return 0
    validate_evidence(
        evidence,
        expected_tag=arguments.expected_tag,
        expected_commit=arguments.expected_commit,
        assets_dir=arguments.assets_dir,
    )
    print("qualification evidence is complete and promotable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
