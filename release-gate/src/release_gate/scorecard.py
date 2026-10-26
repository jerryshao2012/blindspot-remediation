"""Read-only, flat scorecard row derived from verified gate evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from release_gate.config import load_config_bytes
from release_gate.evidence import EvidenceError, verify_run
from release_gate.models import CheckMode, GateConfig, ReportParser
from release_gate.reports import ReportError, parse_report

JUNIT_FIELDS = ("tests", "failures", "errors", "skipped")
FLAG_CODES = frozenset(
    {
        "ASSERTION_OPERAND_ERROR",
        "COMMAND_TIMED_OUT",
        "EVIDENCE_BUDGET_EXHAUSTED",
        "OPTIONAL_REPORT_MISSING",
        "PREPARATION_FAILED",
        "REPORT_PARSE_FAILED",
        "REPORT_PATH_UNSAFE",
        "REPORT_TOO_LARGE",
        "REQUIRED_CONTROL_SKIPPED",
        "REQUIRED_REPORT_MISSING",
        "STREAM_TRUNCATED",
    }
)

Metrics = dict[str, Any] | None


def build_scorecard(run_dir: Path) -> dict[str, Any]:
    """Return one flat row of signals for a completed gate run.

    Values the run cannot support are ``None``; the row never claims a delta
    without both base and candidate reports.
    """

    verify_run(run_dir)
    result_bytes = (run_dir / "result.json").read_bytes()
    result = json.loads(result_bytes)
    manifest = json.loads((run_dir / "manifest.json").read_bytes())
    config = load_config_bytes(
        (run_dir / "effective-config.json").read_bytes(),
        source="effective-config.json",
    )
    scope = result["scope"]
    junit_base, junit = _first_report(run_dir, config, ReportParser.JUNIT_XML)
    coverage_base, coverage = _first_report(run_dir, config, ReportParser.COVERAGE_JSON)
    topics_met, topics_total = _topics(run_dir, result, result_bytes)
    codes = {
        *result["reason_codes"],
        *(code for check in result["checks"] for code in check["reason_codes"]),
        *(code for item in manifest["executions"] for code in item["reason_codes"]),
    }
    row: dict[str, Any] = {
        "run_id": result["run_id"],
        "verdict": result["verdict"],
        "changed_paths": len(scope["changed_paths"]),
        "outside_allowed": len(scope["outside_allowed_paths"]),
        "forbidden": len(scope["forbidden_paths"]),
        "review_required": len(scope["review_required_paths"]),
    }
    for field in JUNIT_FIELDS:
        row[f"d_{field}"] = _delta(junit_base, junit, field)
    row["coverage"] = (
        round(coverage["percent_covered"], 2) if coverage is not None else None
    )
    d_coverage = _delta(coverage_base, coverage, "percent_covered")
    row["d_coverage"] = round(d_coverage, 2) if d_coverage is not None else None
    row["topics_met"] = topics_met
    row["topics_total"] = topics_total
    row["flags"] = ";".join(sorted(codes & FLAG_CODES))
    return row


def _first_report(
    run_dir: Path, config: GateConfig, parser: ReportParser
) -> tuple[Metrics, Metrics]:
    extension = ".xml" if parser is ReportParser.JUNIT_XML else ".json"
    for check in config.checks:
        for report in check.reports:
            if report.parser is not parser:
                continue
            values: list[Metrics] = []
            for side in ("base", "candidate"):
                if side == "base" and check.mode is not CheckMode.DIFFERENTIAL:
                    values.append(None)
                    continue
                path = (
                    run_dir
                    / "controls"
                    / check.id
                    / side
                    / "reports"
                    / f"{report.id}{extension}"
                )
                values.append(_parse(parser, path, config.limits.report_bytes))
            return values[0], values[1]
    return None, None


def _parse(parser: ReportParser, path: Path, limit: int) -> Metrics:
    if not path.is_file():
        return None
    try:
        value = parse_report(parser, path, limit)
    except ReportError:
        return None
    return value if isinstance(value, dict) else None


def _delta(base: Metrics, candidate: Metrics, field: str) -> int | float | None:
    if base is None or candidate is None:
        return None
    result: int | float = candidate[field] - base[field]
    return result


def _topics(
    run_dir: Path, result: dict[str, Any], result_bytes: bytes
) -> tuple[int | None, int | None]:
    package = run_dir.parent / "_assurance" / result["run_id"]
    if not package.is_dir():
        return None, None
    from release_gate.assurance.policy import load_policy
    from release_gate.assurance.service import verify_assurance

    verify_assurance(package)
    assurance = json.loads((package / "result.json").read_bytes())
    if (
        assurance["run_id"] != result["run_id"]
        or assurance["gate_result_sha256"] != hashlib.sha256(result_bytes).hexdigest()
    ):
        raise EvidenceError("assurance package does not belong to this run")
    if assurance["assessment_status"] != "COMPLETE":
        return None, None
    total = len(load_policy((package / "policy.yaml").read_bytes()).required_regions)
    return total - len(assurance["unmet_requirements"]), total
