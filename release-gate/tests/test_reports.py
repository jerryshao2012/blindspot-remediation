from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from release_gate.models import Report, ReportParser
from release_gate.reports import (
    ReportError,
    clear_report_paths,
    collect_report,
    parse_report,
)


def report(
    *,
    parser: ReportParser = ReportParser.JSON_METRICS,
    path: str = "report.json",
    required: bool = True,
    max_bytes: int | None = None,
) -> Report:
    return Report(
        id="metrics",
        parser=parser,
        path=path,
        required=required,
        max_bytes=max_bytes,
    )


def test_parses_nested_junit_coverage_and_json_metrics(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text(
        "<testsuites>"
        '<testsuite tests="2" failures="1" errors="0" skipped="0" time="1.25"/>'
        "<testsuite>"
        '<testsuite tests="3" failures="0" errors="1" skipped="1" time="2.5"/>'
        "</testsuite>"
        "</testsuites>",
        encoding="utf-8",
    )
    assert parse_report(ReportParser.JUNIT_XML, junit, 10_000) == {
        "tests": 5,
        "failures": 1,
        "errors": 1,
        "skipped": 1,
        "duration_seconds": 3.75,
    }

    coverage = tmp_path / "coverage.json"
    coverage.write_text(
        json.dumps(
            {
                "totals": {
                    "percent_covered": 87.5,
                    "covered_lines": 7,
                    "missing_lines": 1,
                    "excluded_lines": 2,
                    "num_statements": 8,
                }
            }
        ),
        encoding="utf-8",
    )
    assert parse_report(ReportParser.COVERAGE_JSON, coverage, 10_000) == {
        "percent_covered": 87.5,
        "covered_lines": 7,
        "missing_lines": 1,
        "excluded_lines": 2,
        "statements": 8,
    }

    metrics = tmp_path / "metrics.json"
    metrics.write_text('{"nested":{"value":3},"ok":true}', encoding="utf-8")
    assert parse_report(ReportParser.JSON_METRICS, metrics, 10_000) == {
        "nested": {"value": 3},
        "ok": True,
    }


@pytest.mark.parametrize(
    ("content", "parser"),
    [
        (b"{bad json", ReportParser.JSON_METRICS),
        (b'{"value": NaN}', ReportParser.JSON_METRICS),
        (b'{"totals": {}}', ReportParser.COVERAGE_JSON),
        (b"<testsuite><unclosed>", ReportParser.JUNIT_XML),
        (
            b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><testsuite>&e;</testsuite>',
            ReportParser.JUNIT_XML,
        ),
    ],
)
def test_rejects_malformed_or_unsafe_report_content(
    tmp_path: Path, content: bytes, parser: ReportParser
) -> None:
    path = tmp_path / "report"
    path.write_bytes(content)
    with pytest.raises(ReportError, match="parse"):
        parse_report(parser, path, 10_000)


def test_enforces_exact_report_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_bytes(b"1" * 101)
    with pytest.raises(ReportError, match="too large"):
        parse_report(ReportParser.JSON_METRICS, path, 100)


def test_collects_safe_report_under_stable_evidence_name(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    artifacts = tmp_path / "artifacts"
    workspace.mkdir()
    (workspace / "report.json").write_text('{"value": 4}', encoding="utf-8")

    outcome = collect_report(
        report(), workspace=workspace, artifact_dir=artifacts, global_limit=5_000
    )

    assert outcome.metrics == {"value": 4}
    assert outcome.reason_codes == ()
    assert outcome.artifact_path == artifacts / "metrics.json"
    assert outcome.artifact_path.read_text() == '{"value": 4}'


def test_optional_missing_is_diagnostic_but_required_missing_is_error(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    optional = collect_report(
        report(required=False),
        workspace=workspace,
        artifact_dir=tmp_path / "optional",
        global_limit=100,
    )
    assert optional.metrics is None
    assert optional.reason_codes == ("OPTIONAL_REPORT_MISSING",)

    with pytest.raises(ReportError, match="required report"):
        collect_report(
            report(required=True),
            workspace=workspace,
            artifact_dir=tmp_path / "required",
            global_limit=100,
        )


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_rejects_report_symlink_that_escapes_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    (workspace / "report.json").symlink_to(outside)

    with pytest.raises(ReportError, match="unsafe"):
        collect_report(
            report(),
            workspace=workspace,
            artifact_dir=tmp_path / "artifacts",
            global_limit=100,
        )


def test_clear_report_paths_removes_stale_files_before_execution(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    stale = workspace / "report.json"
    stale.write_text("stale")

    clear_report_paths((report(),), workspace)

    assert not stale.exists()


def test_present_optional_malformed_report_is_still_error(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report.json").write_text("invalid")
    with pytest.raises(ReportError, match="parse"):
        collect_report(
            report(required=False),
            workspace=workspace,
            artifact_dir=tmp_path / "artifacts",
            global_limit=100,
        )
