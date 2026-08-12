"""
Deterministic control execution and evidence normalization.

This module is the factual authority for Component 3. It executes configured
commands, captures exit codes, parses structured reports, stores immutable
report artifacts, and creates ControlResult records.

An LLM is neither needed nor permitted to decide whether:

* a command ran;
* compilation succeeded;
* a test failed;
* a report existed;
* a numeric threshold was met;
* tracked source changed.

Those are mechanically decidable facts.
"""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_engineering_contracts import (
    ArtifactKind,
    ArtifactReference,
    CheckStatus,
    ControlResult,
)

from .artifacts import LocalArtifactStore
from .errors import (
    CommandExecutionError,
    CommandTimeoutError,
    EvidenceParsingError,
    WorkspaceContaminationError,
)
from .models import (
    DeterministicControlSpec,
    ReportParser,
    ReportSpec,
)
from .process import CommandRunner
from .tracing import GateTraceRecorder
from .workspace import GateWorkspace


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ParsedReport:
    """Internal mutable-free result of parsing one report."""

    def __init__(
        self,
        *,
        metrics: dict[str, float],
        summary: str,
    ) -> None:
        self.metrics = metrics
        self.summary = summary


class EvidenceReportParser:
    """Parse supported deterministic report formats."""

    def parse(
        self,
        *,
        specification: ReportSpec,
        content: bytes,
    ) -> ParsedReport:
        if specification.parser == ReportParser.NONE:
            return ParsedReport(metrics={}, summary="Report retained without parsing.")
        if specification.parser == ReportParser.JUNIT_XML:
            return self._parse_junit_xml(content)
        if specification.parser == ReportParser.COVERAGE_JSON:
            return self._parse_coverage_json(content)
        if specification.parser == ReportParser.JSON_METRICS:
            return self._parse_json_metrics(
                content=content,
                metric_paths=specification.metric_paths,
            )
        raise EvidenceParsingError(
            f"Unsupported report parser: {specification.parser.value}."
        )

    @staticmethod
    def _parse_junit_xml(content: bytes) -> ParsedReport:
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise EvidenceParsingError(
                f"JUnit XML is invalid: {exc}"
            ) from exc
        suites: list[ET.Element]
        if root.tag.endswith("testsuite"):
            suites = [root]
        elif root.tag.endswith("testsuites"):
            suites = [
                element
                for element in root
                if element.tag.endswith("testsuite")
            ]
        else:
            raise EvidenceParsingError(
                f"Unexpected JUnit root element {root.tag!r}."
            )
        totals = {
            "tests_total": 0.0,
            "tests_failures": 0.0,
            "tests_errors": 0.0,
            "tests_skipped": 0.0,
            "tests_time_seconds": 0.0,
        }
        for suite in suites:
            totals["tests_total"] += _float_attribute(suite, "tests")
            totals["tests_failures"] += _float_attribute(suite, "failures")
            totals["tests_errors"] += _float_attribute(suite, "errors")
            totals["tests_skipped"] += _float_attribute(
                suite,
                "skipped",
                fallback_attribute="disabled",
            )
            totals["tests_time_seconds"] += _float_attribute(suite, "time")
        passed = (
            totals["tests_total"]
            - totals["tests_failures"]
            - totals["tests_errors"]
            - totals["tests_skipped"]
        )
        totals["tests_passed"] = max(0.0, passed)
        summary = (
            f"JUnit report: {int(totals['tests_total'])} tests, "
            f"{int(totals['tests_failures'])} failures, "
            f"{int(totals['tests_errors'])} errors, "
            f"{int(totals['tests_skipped'])} skipped."
        )
        return ParsedReport(metrics=totals, summary=summary)

    @staticmethod
    def _parse_coverage_json(content: bytes) -> ParsedReport:
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvidenceParsingError(
                f"Coverage JSON is invalid: {exc}"
            ) from exc
        totals = payload.get("totals")
        if not isinstance(totals, dict):
            raise EvidenceParsingError(
                "Coverage JSON does not contain a totals object."
            )
        metric_mapping = {
            "coverage_percent": "percent_covered",
            "statements_total": "num_statements",
            "statements_covered": "covered_lines",
            "statements_missing": "missing_lines",
            "branches_total": "num_branches",
            "branches_covered": "covered_branches",
            "branches_missing": "missing_branches",
        }
        metrics: dict[str, float] = {}
        for normalized_name, source_name in metric_mapping.items():
            value = totals.get(source_name)
            if value is not None:
                metrics[normalized_name] = _require_finite_number(
                    value,
                    source_name,
                )
        if "coverage_percent" not in metrics:
            raise EvidenceParsingError(
                "Coverage JSON totals does not contain percent_covered."
            )
        summary = (
            f"Coverage report: {metrics['coverage_percent']:.2f}% statement "
            "coverage."
        )
        return ParsedReport(metrics=metrics, summary=summary)

    @staticmethod
    def _parse_json_metrics(
        *,
        content: bytes,
        metric_paths: dict[str, str],
    ) -> ParsedReport:
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvidenceParsingError(
                f"JSON metrics report is invalid: {exc}"
            ) from exc
        metrics: dict[str, float] = {}
        for metric_name, dotted_path in metric_paths.items():
            value = _resolve_dotted_path(payload, dotted_path)
            metrics[metric_name] = _require_finite_number(
                value,
                dotted_path,
            )
        return ParsedReport(
            metrics=metrics,
            summary=f"Extracted {len(metrics)} configured JSON metrics.",
        )


class DeterministicControlRunner:
    """Execute authoritative controls and normalize their evidence."""

    def __init__(
        self,
        *,
        command_runner: CommandRunner,
        artifact_store: LocalArtifactStore,
        report_parser: EvidenceReportParser,
        trace: GateTraceRecorder,
    ) -> None:
        self._command_runner = command_runner
        self._artifact_store = artifact_store
        self._report_parser = report_parser
        self._trace = trace

    def run_control(
        self,
        *,
        run_id: str,
        specification: DeterministicControlSpec,
        workspace: GateWorkspace,
    ) -> ControlResult:
        started_at = utc_now()
        repository_path = workspace.repository_path
        working_directory = (
            repository_path / specification.working_directory
        ).resolve()
        try:
            working_directory.relative_to(repository_path.resolve())
        except ValueError:
            return ControlResult(
                control_id=specification.control_id,
                name=specification.name,
                status=CheckStatus.ERROR,
                severity=specification.severity,
                strategy=specification.strategy,
                deterministic_authority=True,
                summary=(
                    "Configured working directory resolves outside the repository."
                ),
                started_at=started_at,
                completed_at=utc_now(),
                reasons=[
                    f"Invalid working directory: "
                    f"{specification.working_directory}"
                ],
            )
        if not working_directory.exists():
            return ControlResult(
                control_id=specification.control_id,
                name=specification.name,
                status=CheckStatus.ERROR,
                severity=specification.severity,
                strategy=specification.strategy,
                deterministic_authority=True,
                summary="Configured working directory does not exist.",
                started_at=started_at,
                completed_at=utc_now(),
                reasons=[str(working_directory)],
            )
        try:
            command_result = self._command_runner.run(
                specification.command,
                cwd=working_directory,
                timeout_seconds=specification.timeout_seconds,
                extra_environment=specification.environment,
            )
            self._trace.record_command(
                purpose=f"authoritative control {specification.control_id}",
                result=command_result,
            )
        except CommandTimeoutError as exc:
            return ControlResult(
                control_id=specification.control_id,
                name=specification.name,
                status=CheckStatus.ERROR,
                severity=specification.severity,
                strategy=specification.strategy,
                deterministic_authority=True,
                summary="Authoritative control timed out.",
                started_at=started_at,
                completed_at=utc_now(),
                metrics={"timed_out": 1.0},
                reasons=[str(exc)],
            )
        except CommandExecutionError as exc:
            return ControlResult(
                control_id=specification.control_id,
                name=specification.name,
                status=CheckStatus.ERROR,
                severity=specification.severity,
                strategy=specification.strategy,
                deterministic_authority=True,
                summary="Authoritative control could not be executed.",
                started_at=started_at,
                completed_at=utc_now(),
                reasons=[str(exc)],
            )
        evidence_artifacts: list[ArtifactReference] = []
        metrics: dict[str, float] = {
            "exit_code": float(command_result.exit_code),
            "duration_seconds": command_result.duration_seconds,
            "output_truncated": 1.0 if command_result.output_truncated else 0.0,
        }
        reasons: list[str] = []
        report_errors: list[str] = []
        report_summaries: list[str] = []
        for report in specification.reports:
            report_path = (repository_path / report.path).resolve()
            try:
                report_path.relative_to(repository_path.resolve())
            except ValueError:
                report_errors.append(
                    f"Report {report.report_id!r} resolves outside the repository."
                )
                continue
            if not report_path.exists():
                message = (
                    f"Expected report {report.report_id!r} was not produced at "
                    f"{report.path}."
                )
                if report.required:
                    report_errors.append(message)
                else:
                    reasons.append(message)
                continue
            try:
                content = report_path.read_bytes()
            except OSError as exc:
                report_errors.append(
                    f"Unable to read report {report.report_id!r}: {exc}"
                )
                continue
            artifact = self._artifact_store.store_bytes(
                run_id=run_id,
                filename=(
                    f"{specification.control_id}--{report.report_id}"
                    f"{report_path.suffix or '.bin'}"
                ),
                kind=report.artifact_kind,
                media_type=report.media_type,
                content=content,
                metadata={
                    "control_id": specification.control_id,
                    "report_id": report.report_id,
                    "parser": report.parser.value,
                },
            )
            evidence_artifacts.append(artifact)
            try:
                parsed = self._report_parser.parse(
                    specification=report,
                    content=content,
                )
            except EvidenceParsingError as exc:
                if report.required:
                    report_errors.append(
                        f"Required report {report.report_id!r} could not be "
                        f"parsed: {exc}"
                    )
                else:
                    reasons.append(
                        f"Optional report {report.report_id!r} could not be "
                        f"parsed: {exc}"
                    )
                continue
            for metric_name, value in parsed.metrics.items():
                if metric_name in metrics:
                    report_errors.append(
                        f"Duplicate metric name {metric_name!r} within control "
                        f"{specification.control_id!r}."
                    )
                else:
                    metrics[metric_name] = value
            report_summaries.append(parsed.summary)
        command_passed = (
            command_result.exit_code in specification.expected_exit_codes
        )
        if report_errors:
            status = CheckStatus.ERROR
            reasons.extend(report_errors)
        elif command_passed:
            status = CheckStatus.PASSED
        else:
            status = CheckStatus.FAILED
            reasons.append(
                f"Exit code {command_result.exit_code} was not in expected "
                f"codes {specification.expected_exit_codes}."
            )
        try:
            workspace.assert_candidate_not_contaminated()
        except WorkspaceContaminationError as exc:
            status = CheckStatus.ERROR
            reasons.append(str(exc))
            metrics["workspace_contaminated"] = 1.0
        diagnostic = (
            command_result.stderr.strip()
            or command_result.stdout.strip()
        )
        if len(diagnostic) > 2_000:
            diagnostic = diagnostic[:2_000] + "\n...[summary truncated]"
        summary_parts = [
            f"Control {specification.control_id!r} finished with "
            f"status {status.value!r} and exit code "
            f"{command_result.exit_code}."
        ]
        summary_parts.extend(report_summaries)
        if diagnostic:
            summary_parts.append(diagnostic)
        return ControlResult(
            control_id=specification.control_id,
            name=specification.name,
            status=status,
            severity=specification.severity,
            strategy=specification.strategy,
            deterministic_authority=True,
            summary="\n".join(summary_parts),
            started_at=started_at,
            completed_at=utc_now(),
            evidence_artifacts=evidence_artifacts,
            metrics=metrics,
            reasons=reasons,
        )


def namespace_metrics(
    controls: list[ControlResult],
) -> dict[str, float]:
    """
    Convert control metrics into a collision-resistant flat namespace.

    Example:

        control_id = "coverage"
        metric = "coverage_percent"

    becomes:

        coverage.coverage_percent
    """
    result: dict[str, float] = {}
    for control in controls:
        for metric_name, value in control.metrics.items():
            namespaced = f"{control.control_id}.{metric_name}"
            if namespaced in result:
                raise EvidenceParsingError(
                    f"Duplicate normalized metric {namespaced!r}."
                )
            if not math.isfinite(value):
                raise EvidenceParsingError(
                    f"Metric {namespaced!r} is not finite."
                )
            result[namespaced] = value
    return result


def _float_attribute(
    element: ET.Element,
    name: str,
    fallback_attribute: str | None = None,
) -> float:
    raw = element.attrib.get(name)
    if raw is None and fallback_attribute is not None:
        raw = element.attrib.get(fallback_attribute)
    if raw is None:
        return 0.0
    return _require_finite_number(raw, name)


def _require_finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise EvidenceParsingError(
            f"Metric {name!r} is Boolean rather than numeric."
        )
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceParsingError(
            f"Metric {name!r} is not numeric: {value!r}."
        ) from exc
    if not math.isfinite(result):
        raise EvidenceParsingError(
            f"Metric {name!r} must be finite."
        )
    return result


def _resolve_dotted_path(payload: Any, dotted_path: str) -> Any:
    current = payload
    for segment in dotted_path.split("."):
        if isinstance(current, dict):
            if segment not in current:
                raise EvidenceParsingError(
                    f"JSON metric path {dotted_path!r} does not exist."
                )
            current = current[segment]
            continue
        if isinstance(current, list):
            try:
                index = int(segment)
            except ValueError as exc:
                raise EvidenceParsingError(
                    f"Path segment {segment!r} must be a list index."
                ) from exc
            try:
                current = current[index]
            except IndexError as exc:
                raise EvidenceParsingError(
                    f"List index {index} is outside JSON metric path "
                    f"{dotted_path!r}."
                ) from exc
            continue
        raise EvidenceParsingError(
            f"Cannot traverse segment {segment!r} in path {dotted_path!r}."
        )
    return current
