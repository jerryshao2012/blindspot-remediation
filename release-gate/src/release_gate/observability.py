"""Deterministic, standalone decision-observability reports for Release Gate."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from release_gate.timestamps import parse_timestamp

MAX_SOURCE_RUNS = 199
MAX_SERIES_POINTS = 100
MAX_SCAN_DIRECTORIES = 1000
MAX_AGGREGATE_READ_BYTES = 64 * 1024 * 1024
RESULT_READ_LIMIT = 2 * 1024 * 1024
MANIFEST_READ_LIMIT = 4 * 1024 * 1024
_RUN_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VERDICTS = frozenset(("PASS", "FAIL", "NEEDS_HUMAN"))


class WarningCategory(StrEnum):
    """Closed, content-free reasons why historical input was not used."""

    CACHE_INVALID = "CACHE_INVALID"
    CONFLICTING_RUN = "CONFLICTING_RUN"
    INCOMPLETE_RUN = "INCOMPLETE_RUN"
    INVALID_SUMMARY = "INVALID_SUMMARY"
    MALFORMED_RUN = "MALFORMED_RUN"
    RUN_DIGEST_MISMATCH = "RUN_DIGEST_MISMATCH"
    RUN_DIRECTORY_UNSAFE = "RUN_DIRECTORY_UNSAFE"
    RUN_ID_MISMATCH = "RUN_ID_MISMATCH"
    RUN_SCHEMA_INVALID = "RUN_SCHEMA_INVALID"
    RUN_TOO_LARGE = "RUN_TOO_LARGE"
    SCAN_LIMIT_REACHED = "SCAN_LIMIT_REACHED"


@dataclass(frozen=True, slots=True)
class DecisionSummary:
    """The small, stable public identity of one completed decision."""

    run_id: str
    finished_at: str
    verdict: str
    config_sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "finished_at": self.finished_at,
            "verdict": self.verdict,
            "config_sha256": self.config_sha256,
        }


@dataclass(frozen=True, slots=True)
class HistoryCollection:
    """Validated summaries and aggregate, non-sensitive collection diagnostics."""

    source_runs: tuple[DecisionSummary, ...]
    skipped_runs: int
    warnings: tuple[WarningCategory, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class _Normalized:
    summaries: tuple[DecisionSummary, ...]
    skipped_runs: int
    warnings: tuple[WarningCategory, ...]


def build_report(
    evidence_root: Path,
    pending_result: Mapping[str, Any] | None = None,
    *,
    cache: Mapping[str, Any] | Path | None = None,
) -> dict[str, Any]:
    """Build a report from an evidence root and an optional not-yet-persisted result."""

    collected = collect_history(evidence_root, cache=cache)
    inputs: list[DecisionSummary | Mapping[str, Any]] = list(collected.source_runs)
    if pending_result is not None:
        inputs.append(pending_result)
    return build_report_from_summaries(
        inputs,
        skipped_runs=collected.skipped_runs,
        warnings=collected.warnings,
        truncated=collected.truncated,
    )


def build_report_from_summaries(
    summaries: Iterable[DecisionSummary | Mapping[str, Any]],
    *,
    skipped_runs: int = 0,
    warnings: Iterable[WarningCategory] = (),
    truncated: bool = False,
) -> dict[str, Any]:
    """Aggregate untrusted summary mappings into the v1 JSON contract."""

    normalized = _normalize(summaries)
    retained = normalized.summaries[-MAX_SOURCE_RUNS:]
    is_truncated = truncated or len(normalized.summaries) > MAX_SOURCE_RUNS
    merged_warnings = set(warnings) | set(normalized.warnings)
    points = _series(retained)
    return {
        "version": 1,
        "generation_id": _generation_id(retained),
        "generated_at": retained[-1].finished_at if retained else None,
        "scope": "evidence_root",
        "window_sizes": [10, 100],
        "source_runs": [summary.as_dict() for summary in retained],
        "series": points[-MAX_SERIES_POINTS:],
        "diagnostics": {
            "skipped_runs": max(0, skipped_runs) + normalized.skipped_runs,
            "truncated": is_truncated,
            "warnings": sorted(category.value for category in merged_warnings),
        },
    }


def collect_history(
    evidence_root: Path,
    *,
    cache: Mapping[str, Any] | Path | None = None,
) -> HistoryCollection:
    """Read cache and evidence directories without following unsafe filesystem links."""

    candidates: list[DecisionSummary | Mapping[str, Any]] = []
    skipped = 0
    warnings: set[WarningCategory] = set()
    cache_values, cache_warning = _cache_summaries(cache)
    if cache_warning is not None:
        skipped += 1
        warnings.add(cache_warning)
    candidates.extend(cache_values)

    try:
        entries = list(evidence_root.iterdir())
    except OSError:
        return _collected(
            candidates, skipped + 1, warnings | {WarningCategory.MALFORMED_RUN}, False
        )
    safe_directories: list[tuple[float, Path]] = []
    for entry in entries:
        if entry.name == "_observability":
            continue
        try:
            metadata = os.lstat(entry)
        except OSError:
            skipped += 1
            warnings.add(WarningCategory.RUN_DIRECTORY_UNSAFE)
            continue
        if not _is_safe_directory(metadata):
            if entry.is_dir() or stat.S_ISLNK(metadata.st_mode):
                skipped += 1
                warnings.add(WarningCategory.RUN_DIRECTORY_UNSAFE)
            continue
        safe_directories.append((metadata.st_mtime, entry))
    safe_directories.sort(key=lambda item: (-item[0], item[1].name))
    scan_truncated = len(safe_directories) > MAX_SCAN_DIRECTORIES
    if scan_truncated:
        warnings.add(WarningCategory.SCAN_LIMIT_REACHED)
    budget = _ReadBudget(MAX_AGGREGATE_READ_BYTES)
    for _, directory in safe_directories[:MAX_SCAN_DIRECTORIES]:
        parsed, reason = _read_completed_run(directory, budget)
        if parsed is None:
            skipped += 1
            warnings.add(reason)
        else:
            candidates.append(parsed)
    return _collected(candidates, skipped, warnings, scan_truncated)


def render_json(report: Mapping[str, Any]) -> bytes:
    """Serialize a report as canonical UTF-8 JSON."""

    return _canonical_json(report)


def render_html(report: Mapping[str, Any]) -> bytes:
    """Render a self-contained, deterministic HTML report with accessible SVG charts."""

    generation_id = _text(report.get("generation_id"))
    source_runs = _mapping_list(report.get("source_runs"))
    series = _mapping_list(report.get("series"))
    diagnostics = report.get("diagnostics")
    diagnostics_map = diagnostics if isinstance(diagnostics, Mapping) else {}
    cards = (
        _card("Source runs", str(len(source_runs)))
        + _card("Visible runs", str(len(series)))
        + _card("Skipped runs", str(diagnostics_map.get("skipped_runs", 0)))
    )
    table_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td><code>{}</code></td></tr>".format(
            html.escape(_text(point.get("run_id")), quote=True),
            html.escape(_text(point.get("finished_at")), quote=True),
            html.escape(_text(point.get("verdict")), quote=True),
            html.escape(_text(point.get("config_sha256"))[:12], quote=True),
        )
        for point in reversed(series[-10:])
    )
    data = _safe_json_text(report)
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Release Gate decision observability</title><style>"
        "body{font:16px/1.5 system-ui,sans-serif;margin:2rem;max-width:1100px;"
        "color:#17202a}h1,h2{line-height:1.2}.meta{color:#53616d}"
        ".cards{display:flex;gap:1rem;flex-wrap:wrap}.card{border:1px solid #b7c3cc;"
        "border-radius:.5rem;padding:1rem;min-width:9rem}.card b{display:block;"
        "font-size:1.8rem}svg{width:100%;height:auto;border:1px solid #b7c3cc;"
        "background:#fff}.pass{fill:#217346}.fail{fill:#bb2626}.human{fill:#af7000}"
        ".transition{stroke:#263238;stroke-width:1.5}table{border-collapse:collapse;"
        "width:100%}th,td{text-align:left;border-bottom:1px solid #d5dde2;"
        "padding:.45rem}code{font-size:.85em}.legend{display:flex;gap:1rem;"
        "flex-wrap:wrap}.key{display:inline-block;width:.8rem;height:.8rem;"
        "margin-right:.3rem}.sr-only{position:absolute;width:1px;height:1px;padding:0;"
        "margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}"
        "</style></head><body><main><h1>Release Gate decision observability</h1>"
        '<p class="meta">Generation <code>__GENERATION__</code> · '
        "evidence root scope</p>"
        '<section class="cards" aria-label="Decision summary">__CARDS__</section>'
        '<section><h2>Rolling trends</h2><p class="legend">'
        '<span><i class="key pass"></i>Releasing</span>'
        '<span><i class="key fail"></i>Failing</span>'
        '<span><i class="key human"></i>Human review</span>'
        "<span>Vertical marker: configuration transition</span></p>__CHARTS__</section>"
        '<section><h2>Recent runs</h2><table><caption class="sr-only">'
        "The ten most recent visible Release Gate decisions</caption><thead><tr>"
        "<th>Run</th><th>Finished</th><th>Verdict</th><th>Config</th>"
        "</tr></thead><tbody>__ROWS__</tbody></table></section>"
        '<script id="gate-decisions-data" type="application/json">__DATA__</script>'
        "</main></body></html>"
    )
    output = (
        document.replace("__GENERATION__", html.escape(generation_id, quote=True))
        .replace("__CARDS__", cards)
        .replace("__CHARTS__", _chart(series, "10") + _chart(series, "100"))
        .replace("__ROWS__", table_rows)
        .replace("__DATA__", data)
    ).encode("utf-8")
    if len(output) > 512 * 1024:
        raise ValueError("rendered observability HTML exceeds 512 KiB")
    return output


@dataclass(slots=True)
class _ReadBudget:
    remaining: int

    def read(self, path: Path, limit: int) -> bytes | None:
        try:
            metadata = os.lstat(path)
        except OSError:
            return None
        if (
            not _is_safe_file(metadata)
            or metadata.st_size > limit
            or metadata.st_size > self.remaining
        ):
            return None
        try:
            content = path.read_bytes()
        except OSError:
            return None
        if len(content) != metadata.st_size:
            return None
        self.remaining -= len(content)
        return content


def _read_completed_run(
    directory: Path, budget: _ReadBudget
) -> tuple[DecisionSummary | None, WarningCategory]:
    try:
        if os.path.lexists(directory / ".incomplete"):
            return None, WarningCategory.INCOMPLETE_RUN
    except OSError:
        return None, WarningCategory.RUN_DIRECTORY_UNSAFE
    for filename in ("result.json", "manifest.json"):
        try:
            metadata = os.lstat(directory / filename)
        except OSError:
            return None, WarningCategory.MALFORMED_RUN
        if not _is_safe_file(metadata):
            return None, WarningCategory.RUN_DIRECTORY_UNSAFE
    result_bytes = budget.read(directory / "result.json", RESULT_READ_LIMIT)
    manifest_bytes = budget.read(directory / "manifest.json", MANIFEST_READ_LIMIT)
    if result_bytes is None or manifest_bytes is None:
        return None, WarningCategory.RUN_TOO_LARGE
    try:
        result = json.loads(result_bytes)
        manifest = json.loads(manifest_bytes)
    except (TypeError, json.JSONDecodeError):
        return None, WarningCategory.MALFORMED_RUN
    if not isinstance(result, Mapping) or not isinstance(manifest, Mapping):
        return None, WarningCategory.MALFORMED_RUN
    if not _valid_result_document(result):
        return None, WarningCategory.RUN_SCHEMA_INVALID
    if (
        result.get("run_id") != directory.name
        or manifest.get("run_id") != directory.name
    ):
        return None, WarningCategory.RUN_ID_MISMATCH
    record = _result_artifact(manifest)
    if record is None:
        return None, WarningCategory.MALFORMED_RUN
    if record["size_bytes"] != len(result_bytes) or record["sha256"] != _digest(
        result_bytes
    ):
        return None, WarningCategory.RUN_DIGEST_MISMATCH
    try:
        return _coerce_summary(result), WarningCategory.MALFORMED_RUN
    except ValueError:
        return None, WarningCategory.RUN_SCHEMA_INVALID


def _cache_summaries(
    cache: Mapping[str, Any] | Path | None,
) -> tuple[list[Mapping[str, Any]], WarningCategory | None]:
    if cache is None:
        return [], None
    value: Any = cache
    if isinstance(cache, Path):
        try:
            metadata = os.lstat(cache)
            if not _is_safe_file(metadata) or metadata.st_size > RESULT_READ_LIMIT:
                return [], WarningCategory.CACHE_INVALID
            value = json.loads(cache.read_bytes())
        except (OSError, json.JSONDecodeError):
            return [], WarningCategory.CACHE_INVALID
    if not isinstance(value, Mapping) or not isinstance(value.get("source_runs"), list):
        return [], WarningCategory.CACHE_INVALID
    runs = value["source_runs"]
    if not all(isinstance(item, Mapping) for item in runs):
        return [], WarningCategory.CACHE_INVALID
    return list(runs), None


def _collected(
    candidates: Iterable[DecisionSummary | Mapping[str, Any]],
    skipped: int,
    warnings: set[WarningCategory],
    truncated: bool,
) -> HistoryCollection:
    normalized = _normalize(candidates)
    summaries = normalized.summaries[-MAX_SOURCE_RUNS:]
    return HistoryCollection(
        source_runs=summaries,
        skipped_runs=skipped + normalized.skipped_runs,
        warnings=tuple(
            sorted(warnings | set(normalized.warnings), key=lambda item: item.value)
        ),
        truncated=truncated or len(normalized.summaries) > MAX_SOURCE_RUNS,
    )


def _normalize(values: Iterable[DecisionSummary | Mapping[str, Any]]) -> _Normalized:
    by_id: dict[str, DecisionSummary] = {}
    skipped = 0
    warnings: set[WarningCategory] = set()
    for value in values:
        try:
            summary = (
                value if isinstance(value, DecisionSummary) else _coerce_summary(value)
            )
        except (TypeError, ValueError):
            skipped += 1
            warnings.add(WarningCategory.INVALID_SUMMARY)
            continue
        previous = by_id.get(summary.run_id)
        if previous is None:
            by_id[summary.run_id] = summary
        elif previous != summary:
            skipped += 1
            warnings.add(WarningCategory.CONFLICTING_RUN)
            if _summary_identity(summary) < _summary_identity(previous):
                by_id[summary.run_id] = summary
    ordered = tuple(
        sorted(
            by_id.values(),
            key=lambda item: (_timestamp_key(item.finished_at), item.run_id),
        )
    )
    return _Normalized(
        ordered, skipped, tuple(sorted(warnings, key=lambda item: item.value))
    )


def _coerce_summary(value: Mapping[str, Any]) -> DecisionSummary:
    fields = ("run_id", "finished_at", "verdict", "config_sha256")
    if any(not isinstance(value.get(field), str) for field in fields):
        raise ValueError("summary fields must be strings")
    summary = DecisionSummary(*(value[field] for field in fields))
    if not _RUN_ID.fullmatch(summary.run_id) or not _SHA256.fullmatch(
        summary.config_sha256
    ):
        raise ValueError("summary identity is invalid")
    if summary.verdict not in _VERDICTS:
        raise ValueError("summary verdict is invalid")
    parse_timestamp(summary.finished_at)
    return summary


def _series(summaries: tuple[DecisionSummary, ...]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for index, summary in enumerate(summaries):
        prior = summaries[index - 1] if index else None
        points.append(
            summary.as_dict()
            | {
                "config_changed": prior is not None
                and prior.config_sha256 != summary.config_sha256,
                "windows": {
                    str(size): _window(summaries[max(0, index - size + 1) : index + 1])
                    for size in (10, 100)
                },
            }
        )
    return points


def _window(summaries: tuple[DecisionSummary, ...]) -> dict[str, Any]:
    counts = {"releasing": 0, "failing": 0, "human_review": 0}
    keys = {"PASS": "releasing", "FAIL": "failing", "NEEDS_HUMAN": "human_review"}
    for summary in summaries:
        counts[keys[summary.verdict]] += 1
    size = len(summaries)
    return {
        "sample_size": size,
        "counts": counts,
        "rates": {key: value / size for key, value in counts.items()},
    }


def _generation_id(summaries: tuple[DecisionSummary, ...]) -> str:
    return _digest(_canonical_json([summary.as_dict() for summary in summaries]))


def _valid_result_document(result: Mapping[str, Any]) -> bool:
    try:
        schema = json.loads(
            files("release_gate.schemas")
            .joinpath("result-v1.schema.json")
            .read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        return not any(validator.iter_errors(dict(result)))
    except (OSError, json.JSONDecodeError):
        return False


def _result_artifact(manifest: Mapping[str, Any]) -> dict[str, Any] | None:
    records = manifest.get("artifacts")
    if not isinstance(records, list):
        return None
    found = [
        item
        for item in records
        if isinstance(item, Mapping) and item.get("path") == "result.json"
    ]
    if len(found) != 1:
        return None
    record = found[0]
    if not isinstance(record.get("size_bytes"), int) or not isinstance(
        record.get("sha256"), str
    ):
        return None
    return {"size_bytes": record["size_bytes"], "sha256": record["sha256"]}


def _is_safe_directory(metadata: os.stat_result) -> bool:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return (
        stat.S_ISDIR(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and not (getattr(metadata, "st_file_attributes", 0) & reparse)
    )


def _is_safe_file(metadata: os.stat_result) -> bool:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and not (getattr(metadata, "st_file_attributes", 0) & reparse)
    )


def _timestamp_key(value: str) -> tuple[float, str]:
    return (parse_timestamp(value).timestamp(), value)


def _summary_identity(value: DecisionSummary) -> tuple[str, str, str, str]:
    return (value.run_id, value.finished_at, value.verdict, value.config_sha256)


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _card(label: str, value: str) -> str:
    return (
        f'<div class="card"><span>{html.escape(label)}</span>'
        f"<b>{html.escape(value)}</b></div>"
    )


def _chart(points: list[Mapping[str, Any]], window: str) -> str:
    title = f"Rolling {window}-run trend"
    width, height = 1000, 180
    count = max(len(points), 1)
    bar_width = width / count
    bars: list[str] = []
    colors = (("releasing", "pass"), ("failing", "fail"), ("human_review", "human"))
    for index, point in enumerate(points):
        windows = point.get("windows")
        values = (
            windows.get(window, {}).get("rates", {})
            if isinstance(windows, Mapping)
            else {}
        )
        y = 0.0
        x = index * bar_width
        for name, css in colors:
            rate = values.get(name, 0.0) if isinstance(values, Mapping) else 0.0
            rate = rate if isinstance(rate, (float, int)) else 0.0
            h = max(0.0, min(1.0, float(rate))) * height
            bars.append(
                f'<rect class="{css}" x="{x:.3f}" y="{y:.3f}" '
                f'width="{bar_width + 0.1:.3f}" height="{h:.3f}"/>'
            )
            y += h
        if point.get("config_changed") is True:
            bars.append(
                f'<line class="transition" x1="{x:.3f}" y1="0" '
                f'x2="{x:.3f}" y2="{height}"/>'
            )
    return (
        f"<figure><figcaption>{title}: 100%-stacked outcome rates with "
        f'configuration transitions marked.</figcaption><svg role="img" '
        f'aria-label="{title}" viewBox="0 0 {width} {height}">'
        f"<title>{title}</title><desc>Each bar is one completed run and stacks "
        f"releasing, failing, and human-review rates to one hundred percent.</desc>"
        f"{''.join(bars)}</svg></figure>"
    )


def _safe_json_text(value: Mapping[str, Any]) -> str:
    return (
        _canonical_json(value)
        .decode("utf-8")
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    return (
        [item for item in value if isinstance(item, Mapping)]
        if isinstance(value, list)
        else []
    )


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""
