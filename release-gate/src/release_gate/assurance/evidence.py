"""Normalize retained execution evidence, never candidate-supplied concept labels."""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from defusedxml import ElementTree

from release_gate.evidence import EvidenceError, verify_run
from release_gate.git import CandidateCapture, _source_git
from release_gate.models import ReportParser
from release_gate.reports import _read_regular_file

from .policy import AssurancePolicy, Selector


class AssessmentUnavailable(ValueError):
    """No complete assessment can be made within the evidence contract."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def base_blob(capture: CandidateCapture, path: str, limit: int = 1048576) -> bytes:
    entries = _source_git(
        capture.repository, "ls-tree", "-z", capture.base_commit, "--", path
    )
    if not entries.startswith((b"100644 blob ", b"100755 blob ")):
        raise ValueError("base source is missing or not a regular file")
    spec = f"{capture.base_commit}:{path}"
    size = int(_source_git(capture.repository, "cat-file", "-s", spec))
    if size > limit:
        raise ValueError("base source exceeds size limit")
    return _source_git(capture.repository, "cat-file", "blob", spec)


def normalize(
    capture: CandidateCapture,
    run: Path,
    policy: AssurancePolicy,
    started: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    verify_run(run)
    result = json.loads(_read_regular_file(run / "result.json", 2097152))
    manifest = json.loads(_read_regular_file(run / "manifest.json", 4194304))
    expected = {
        "base_commit": capture.base_commit,
        "candidate_tree": capture.candidate_tree,
        "patch_sha256": capture.patch_sha256,
    }
    if any(
        document.get(k) != v
        for document in (result, manifest)
        for k, v in expected.items()
    ):
        raise EvidenceError("gate candidate identity mismatch")
    if (
        result["run_id"] != manifest["run_id"]
        or result["config_sha256"] != manifest["config_sha256"]
    ):
        raise EvidenceError("gate result/manifest identity mismatch")
    inventory = {a["path"]: a for a in manifest["artifacts"]}
    executions = {
        (e["control_id"], e["side"]): e
        for e in manifest["executions"]
        if e["phase"] == "check"
    }
    checks = {c["id"]: c for c in result["checks"]}
    artifacts: list[dict[str, Any]] = []
    total_bytes = 0
    source_validity: dict[str, bool] = {}
    for mapping in policy.mappings:
        for source, expected_digest in mapping.sources.items():
            key = source + expected_digest
            if key not in source_validity:
                try:
                    source_validity[key] = (
                        source not in capture.changed_paths
                        and digest(base_blob(capture, source, 4194304))
                        == expected_digest
                    )
                except (ValueError, OSError):
                    source_validity[key] = False
    mappings = {m.selector.model_dump_json(): m for m in policy.mappings}

    def add(
        selector: Selector,
        status: str,
        observation: dict[str, Any],
        record: dict[str, Any],
        report_path: str | None = None,
    ) -> None:
        if len(artifacts) >= policy.limits.max_artifacts:
            raise AssessmentUnavailable("artifact limit exceeded")
        if time.monotonic() - started > policy.limits.max_elapsed_seconds:
            raise AssessmentUnavailable("assessment deadline exceeded")
        mapping = mappings.get(selector.model_dump_json())
        trusted = mapping is not None and all(
            source_validity[p + h] for p, h in mapping.sources.items()
        )
        eligible = (
            status == "PASS"
            and record["classification"] == "pass"
            and checks[selector.check_id]["status"] == "PASS"
        )
        concepts = mapping.concepts if mapping and trusted and eligible else {}
        artifact_id = digest(
            json.dumps(
                [capture.candidate_tree, selector.model_dump(), len(artifacts)],
                sort_keys=True,
            ).encode()
        )
        # Duplicate observations within a check cannot create new independent support.
        content_hash = digest(json.dumps(observation, sort_keys=True).encode())
        artifacts.append(
            {
                "evidence_id": artifact_id,
                "selector": selector.model_dump(),
                "status": status,
                "eligible": eligible,
                "mapping_trusted": trusted,
                "concepts": concepts,
                "independence_group": (mapping.independence_group if mapping else None)
                or f"check:{selector.check_id}",
                "reviewed_sources": mapping.sources if mapping else {},
                "candidate_tree": capture.candidate_tree,
                "patch_sha256": capture.patch_sha256,
                "execution": record,
                "observation": observation,
                "report_path": report_path,
                "report_sha256": inventory[report_path]["sha256"]
                if report_path
                else None,
                "content_sha256": content_hash,
            }
        )

    for check in capture.config.checks:
        record = executions[(check.id, "candidate")]
        junit = [r for r in check.reports if r.parser is ReportParser.JUNIT_XML]
        if not junit:
            add(
                Selector(check_id=check.id),
                checks[check.id]["status"],
                {
                    "check_id": check.id,
                    "classification": record["classification"],
                    "metrics": record["metrics"],
                },
                record,
            )
            continue
        for report in junit:
            path = f"controls/{check.id}/candidate/reports/{report.id}.xml"
            if path not in inventory:
                add(
                    Selector(
                        check_id=check.id,
                        report_id=report.id,
                        suite="",
                        classname="",
                        name="",
                    ),
                    "UNAVAILABLE",
                    {"reason": "report missing"},
                    record,
                )
                continue
            data = _read_regular_file(run / path, policy.limits.max_report_bytes)
            total_bytes += len(data)
            if total_bytes > policy.limits.max_total_report_bytes:
                raise AssessmentUnavailable("total report limit exceeded")
            if digest(data) != inventory[path]["sha256"]:
                raise EvidenceError("report hash mismatch")
            root = ElementTree.fromstring(data)
            if root.tag not in ("testsuite", "testsuites"):
                raise AssessmentUnavailable("invalid JUnit root")
            cases: list[tuple[Selector, str, dict[str, Any]]] = []
            stack = [(root, "")]
            while stack:
                element, suite = stack.pop()
                if element.tag == "testsuite":
                    suite = (
                        f"{suite}/{element.get('name', '')}"
                        if suite
                        else element.get("name", "")
                    )
                if element.tag == "testcase":
                    declared_status = (
                        element.get("status") or element.get("result") or ""
                    ).casefold()
                    passed_values = {"", "pass", "passed", "success", "successful"}
                    skipped_values = {"notrun", "disabled", "skip", "skipped"}
                    failed_values = {"fail", "failed", "failure"}
                    error_values = {"error", "errored"}
                    if declared_status in passed_values:
                        status = "PASS"
                    elif declared_status in skipped_values:
                        status = "SKIPPED"
                    elif declared_status in failed_values:
                        status = "FAIL"
                    elif declared_status in error_values:
                        status = "ERROR"
                    else:
                        status = "UNKNOWN"
                    if element.find("error") is not None:
                        status = "ERROR"
                    elif element.find("failure") is not None:
                        status = "FAIL"
                    elif element.find("skipped") is not None:
                        status = "SKIPPED"
                    selector = Selector(
                        check_id=check.id,
                        report_id=report.id,
                        suite=suite,
                        classname=element.get("classname", ""),
                        name=element.get("name", ""),
                    )
                    cases.append(
                        (
                            selector,
                            status,
                            {
                                "suite": suite,
                                "classname": selector.classname,
                                "name": selector.name,
                                "status": status,
                            },
                        )
                    )
                    if len(cases) + len(artifacts) > policy.limits.max_artifacts:
                        raise AssessmentUnavailable("artifact limit exceeded")
                stack.extend((child, suite) for child in reversed(list(element)))
            counts = Counter(s.model_dump_json() for s, _, _ in cases)
            if not cases:
                add(
                    Selector(
                        check_id=check.id,
                        report_id=report.id,
                        suite="",
                        classname="",
                        name="",
                    ),
                    "UNAVAILABLE",
                    {"reason": "empty report"},
                    record,
                    path,
                )
            for selector, status, observation in cases:
                if counts[selector.model_dump_json()] != 1:
                    status = "AMBIGUOUS"
                add(selector, status, observation, record, path)
    return result, artifacts
