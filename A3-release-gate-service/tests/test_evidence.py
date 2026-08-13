from __future__ import annotations

import json

from ai_engineering_release_gate.evidence import EvidenceReportParser
from ai_engineering_release_gate.models import ReportParser, ReportSpec


def test_parse_junit_xml() -> None:
    content = b"""
<testsuite tests="10" failures="1" errors="2" skipped="1" time="3.5">
</testsuite>
"""
    result = EvidenceReportParser().parse(
        specification=ReportSpec(
            report_id="junit",
            path=".gate-reports/tests.xml",
            parser=ReportParser.JUNIT_XML,
            required=True,
            media_type="application/xml",
        ),
        content=content,
    )
    assert result.metrics["tests_total"] == 10
    assert result.metrics["tests_passed"] == 6
    assert result.metrics["tests_failures"] == 1
    assert result.metrics["tests_errors"] == 2
    assert result.metrics["tests_skipped"] == 1


def test_parse_coverage_json() -> None:
    content = json.dumps(
        {
            "totals": {
                "percent_covered": 87.5,
                "num_statements": 100,
                "covered_lines": 88,
                "missing_lines": 12,
                "num_branches": 20,
                "covered_branches": 15,
                "missing_branches": 5,
            }
        }
    ).encode("utf-8")
    result = EvidenceReportParser().parse(
        specification=ReportSpec(
            report_id="coverage",
            path=".gate-reports/coverage.json",
            parser=ReportParser.COVERAGE_JSON,
            required=True,
            media_type="application/json",
        ),
        content=content,
    )
    assert result.metrics["coverage_percent"] == 87.5
    assert result.metrics["branches_covered"] == 15


def test_parse_generic_json_metrics() -> None:
    content = json.dumps(
        {
            "metrics": {
                "mutation_score": 76.2,
                "survived": 12,
            }
        }
    ).encode("utf-8")
    result = EvidenceReportParser().parse(
        specification=ReportSpec(
            report_id="mutation",
            path=".gate-reports/mutation.json",
            parser=ReportParser.JSON_METRICS,
            required=True,
            media_type="application/json",
            metric_paths={
                "mutation_score": "metrics.mutation_score",
                "survived_mutants": "metrics.survived",
            },
        ),
        content=content,
    )
    assert result.metrics == {
        "mutation_score": 76.2,
        "survived_mutants": 12.0,
    }
