"""Closed-set, bounded report collection and parsing."""

from __future__ import annotations

import json
import math
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from xml.etree.ElementTree import Element, ParseError

from defusedxml import ElementTree as SafeElementTree
from defusedxml.common import DefusedXmlException

from release_gate.models import Report, ReportParser


class ReportError(ValueError):
    """A declared report cannot provide trustworthy evidence."""

    def __init__(
        self, message: str, *, reason_code: str = "REPORT_PARSE_FAILED"
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class ReportOutcome:
    report_id: str
    metrics: object | None
    reason_codes: tuple[str, ...]
    artifact_path: Path | None


def clear_report_paths(reports: tuple[Report, ...], workspace: Path) -> None:
    """Remove declared final report entries before a command starts."""

    root = workspace.resolve(strict=True)
    for report in reports:
        path = _report_path(root, report.path, allow_missing=True)
        if path is None:
            continue
        try:
            metadata = os.lstat(path)
        except FileNotFoundError:
            continue
        if stat.S_ISDIR(metadata.st_mode):
            raise ReportError(
                f"report path is unsafe: {report.path}",
                reason_code="REPORT_PATH_UNSAFE",
            )
        path.unlink()


def collect_report(
    report: Report,
    *,
    workspace: Path,
    artifact_dir: Path,
    global_limit: int,
) -> ReportOutcome:
    """Validate, parse, and retain one declared report whole."""

    root = workspace.resolve(strict=True)
    path = _report_path(root, report.path, allow_missing=True)
    if path is None or not path.exists():
        if not report.required:
            return ReportOutcome(
                report_id=report.id,
                metrics=None,
                reason_codes=("OPTIONAL_REPORT_MISSING",),
                artifact_path=None,
            )
        raise ReportError(
            f"required report is missing: {report.path}",
            reason_code="REQUIRED_REPORT_MISSING",
        )
    limit = min(global_limit, report.max_bytes or global_limit)
    content = _read_regular_file(path, limit)
    metrics = _parse_bytes(report.parser, content)
    artifact_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    extension = ".xml" if report.parser is ReportParser.JUNIT_XML else ".json"
    destination = artifact_dir / f"{report.id}{extension}"
    try:
        destination.unlink(missing_ok=True)
        with destination.open("xb") as output:
            output.write(content)
    except OSError as error:
        raise ReportError(
            f"unable to retain report: {report.id}",
            reason_code="EVIDENCE_BUDGET_EXHAUSTED",
        ) from error
    return ReportOutcome(
        report_id=report.id,
        metrics=metrics,
        reason_codes=(),
        artifact_path=destination,
    )


def parse_report(parser: ReportParser, path: Path, limit: int) -> object:
    """Parse one already-addressed regular report file."""

    return _parse_bytes(parser, _read_regular_file(path, limit))


def _report_path(root: Path, configured: str, *, allow_missing: bool) -> Path | None:
    relative = PurePosixPath(configured)
    current = root
    for index, component in enumerate(relative.parts):
        current /= component
        final = index == len(relative.parts) - 1
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if allow_missing:
                return current if final else None
            raise
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse):
            raise ReportError(
                f"report path is unsafe: {configured}",
                reason_code="REPORT_PATH_UNSAFE",
            )
        if not final and not stat.S_ISDIR(metadata.st_mode):
            raise ReportError(
                f"report path is unsafe: {configured}",
                reason_code="REPORT_PATH_UNSAFE",
            )
    try:
        current.resolve(strict=False).relative_to(root)
    except ValueError as error:
        raise ReportError(
            f"report path is unsafe: {configured}",
            reason_code="REPORT_PATH_UNSAFE",
        ) from error
    return current


def _read_regular_file(path: Path, limit: int) -> bytes:
    try:
        metadata = os.lstat(path)
    except OSError as error:
        raise ReportError(
            f"report path is unsafe: {path}", reason_code="REPORT_PATH_UNSAFE"
        ) from error
    if not stat.S_ISREG(metadata.st_mode):
        raise ReportError(
            f"report path is unsafe: {path}", reason_code="REPORT_PATH_UNSAFE"
        )
    if metadata.st_size > limit:
        raise ReportError("report is too large", reason_code="REPORT_TOO_LARGE")
    try:
        with path.open("rb") as stream:
            content = stream.read(limit + 1)
    except OSError as error:
        raise ReportError(
            f"report path is unsafe: {path}", reason_code="REPORT_PATH_UNSAFE"
        ) from error
    if len(content) > limit:
        raise ReportError("report is too large", reason_code="REPORT_TOO_LARGE")
    return content


def _parse_bytes(parser: ReportParser, content: bytes) -> object:
    try:
        if parser is ReportParser.JUNIT_XML:
            return _parse_junit(content)
        if parser is ReportParser.COVERAGE_JSON:
            return _parse_coverage(content)
        if parser is ReportParser.JSON_METRICS:
            return _parse_json(content)
    except (
        DefusedXmlException,
        ParseError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ) as error:
        raise ReportError("report parse failed") from error
    raise ReportError("report parse failed")


def _parse_json(content: bytes) -> object:
    value: object = json.loads(
        content.decode("utf-8"),
        parse_constant=lambda token: _raise_nonfinite(token),
    )
    _validate_json_value(value)
    return value


def _raise_nonfinite(token: str) -> None:
    raise ValueError(f"non-finite number: {token}")


def _validate_json_value(value: object) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        if abs(value) > 1.7976931348623157e308:
            raise ValueError("numeric metric is outside binary64")
        return
    if isinstance(value, float):
        if not math.isfinite(value) or abs(value) > 1.7976931348623157e308:
            raise ValueError("numeric metric is outside binary64")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        for item in value.values():
            _validate_json_value(item)
        return
    raise ValueError("report is not JSON data")


def _parse_coverage(content: bytes) -> dict[str, int | float]:
    value = _parse_json(content)
    if not isinstance(value, dict) or not isinstance(value.get("totals"), dict):
        raise ValueError("coverage totals are missing")
    totals = value["totals"]
    assert isinstance(totals, dict)
    fields = {
        "percent_covered": "percent_covered",
        "covered_lines": "covered_lines",
        "missing_lines": "missing_lines",
        "excluded_lines": "excluded_lines",
        "statements": "num_statements",
    }
    result: dict[str, int | float] = {}
    for output, source in fields.items():
        metric = totals.get(source)
        if isinstance(metric, bool) or not isinstance(metric, (int, float)):
            raise ValueError(f"coverage metric is missing: {source}")
        if not math.isfinite(float(metric)):
            raise ValueError(f"coverage metric is non-finite: {source}")
        result[output] = metric
    return result


def _parse_junit(content: bytes) -> dict[str, int | float]:
    root = SafeElementTree.fromstring(content)
    suites = [element for element in root.iter() if _local_name(element) == "testsuite"]
    leaves = [
        suite
        for suite in suites
        if not any(_local_name(child) == "testsuite" for child in list(suite))
    ]
    if _local_name(root) == "testsuite" and not suites:
        leaves = [root]
    if not leaves:
        raise ValueError("JUnit report contains no test suites")
    totals: dict[str, int | float] = {
        "tests": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "duration_seconds": 0.0,
    }
    for suite in leaves:
        for field in ("tests", "failures", "errors", "skipped"):
            totals[field] += _integer_attribute(suite, field)
        duration = float(suite.attrib.get("time", "0"))
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("invalid JUnit duration")
        totals["duration_seconds"] += duration
    return totals


def _integer_attribute(element: Element, name: str) -> int:
    value = int(element.attrib.get(name, "0"))
    if value < 0:
        raise ValueError(f"negative JUnit metric: {name}")
    return value


def _local_name(element: Element) -> str:
    return element.tag.rsplit("}", 1)[-1]
