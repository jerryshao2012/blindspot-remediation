"""Private, demo-only campaign records and aggregate reporting."""

# ruff: noqa: E501 - readable embedded HTML is intentionally kept on whole lines.

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import secrets
import stat
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from math import isfinite, sqrt
from pathlib import Path
from statistics import NormalDist
from typing import Any

CONFIDENCE_LEVEL = 0.95
RUN_KINDS = ("trial", "re-gate", "control")
CLASSIFICATIONS = (
    "good_pass",
    "FALSE_RELEASE",
    "FALSE_BLOCK",
    "good_catch",
    "escalated",
    "oracle_error",
)
_RUN_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?$")
_HEX_40_OR_64 = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_EXPECTED_CLASSIFICATION = {
    ("PASS", True): "good_pass",
    ("PASS", False): "FALSE_RELEASE",
    ("FAIL", True): "FALSE_BLOCK",
    ("FAIL", False): "good_catch",
    ("NEEDS_HUMAN", True): "escalated",
    ("NEEDS_HUMAN", False): "escalated",
}


class CampaignError(RuntimeError):
    """An expected private-campaign validation or publication error."""


@dataclass(frozen=True, slots=True)
class CampaignPaths:
    """Absolute paths published by a campaign operation."""

    record: Path | None
    data: Path
    report: Path


def record_and_refresh(root: Path, record: dict[str, Any]) -> CampaignPaths:
    """Append one immutable record and regenerate both private aggregates."""

    validated = validate_record(record)
    campaign_root = _prepare_root(root)
    with _campaign_lock(campaign_root):
        records_dir, data_path, report_path = _prepare_layout(campaign_root)
        records = _load_records(records_dir)
        matching = [
            item
            for item in records
            if item["run_id"].casefold() == validated["run_id"].casefold()
        ]
        record_path = records_dir / f"{validated['run_id']}.json"
        if matching:
            existing = matching[0]
            if existing["run_id"] != validated["run_id"] or not _same_attempt(
                existing, validated
            ):
                raise CampaignError(
                    f"run_id {validated['run_id']!r} already exists with different data"
                )
            validated = existing
            record_path = records_dir / f"{existing['run_id']}.json"
        else:
            _atomic_write(record_path, _json_bytes(validated))
            records.append(validated)

        _publish_aggregates(records, data_path, report_path)
        return CampaignPaths(
            record=record_path.absolute(),
            data=data_path.absolute(),
            report=report_path.absolute(),
        )


def refresh(root: Path) -> CampaignPaths:
    """Regenerate aggregates from every validated immutable record."""

    campaign_root = _prepare_root(root)
    with _campaign_lock(campaign_root):
        records_dir, data_path, report_path = _prepare_layout(campaign_root)
        records = _load_records(records_dir)
        _publish_aggregates(records, data_path, report_path)
        return CampaignPaths(
            record=None,
            data=data_path.absolute(),
            report=report_path.absolute(),
        )


def wilson_interval(
    *, events: int, trials: int, confidence_level: float = CONFIDENCE_LEVEL
) -> dict[str, Any]:
    """Return a two-sided Wilson score interval for an event proportion."""

    if trials < 0:
        raise ValueError("trials cannot be negative")
    if events < 0 or events > trials:
        raise ValueError("events must be between zero and trials")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence level must be between zero and one")
    result: dict[str, Any] = {
        "numerator": events,
        "denominator": trials,
        "estimate": None,
        "lower_bound": None,
        "upper_bound": None,
        "confidence_level": confidence_level,
        "method": "wilson",
    }
    if trials == 0:
        return result

    proportion = events / trials
    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence_level) / 2.0)
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    center = (proportion + z_squared / (2.0 * trials)) / denominator
    margin = (
        z
        * sqrt(
            proportion * (1.0 - proportion) / trials
            + z_squared / (4.0 * trials * trials)
        )
        / denominator
    )
    result.update(
        estimate=proportion,
        lower_bound=max(0.0, center - margin),
        upper_bound=min(1.0, center + margin),
    )
    return result


def validate_record(value: object) -> dict[str, Any]:
    """Validate and detach one private campaign record."""

    record = _mapping(
        value,
        "record",
        {"version", "run_id", "run_kind", "gate", "oracle", "ai"},
    )
    if record["version"] != 1:
        raise CampaignError("record version must be 1")
    run_id = _text(record["run_id"], "run_id", 128)
    if not _RUN_ID.fullmatch(run_id) or run_id.endswith("."):
        raise CampaignError("run_id is not portable")
    if record["run_kind"] not in RUN_KINDS:
        raise CampaignError("run_kind is unsupported")

    gate = _mapping(
        record["gate"],
        "gate",
        {
            "verdict",
            "finished_at",
            "duration_ms",
            "base_commit",
            "candidate_tree",
            "patch_sha256",
            "config_sha256",
            "result_sha256",
        },
    )
    if gate["verdict"] not in {"PASS", "FAIL", "NEEDS_HUMAN"}:
        raise CampaignError("gate verdict is unsupported")
    _timestamp(gate["finished_at"], "gate finished_at")
    _non_negative_number(gate["duration_ms"], "gate duration_ms", integer=True)
    for key in ("base_commit", "candidate_tree"):
        if not isinstance(gate[key], str) or not _HEX_40_OR_64.fullmatch(gate[key]):
            raise CampaignError(f"gate {key} is invalid")
    for key in ("patch_sha256", "config_sha256", "result_sha256"):
        if not isinstance(gate[key], str) or not _SHA256.fullmatch(gate[key]):
            raise CampaignError(f"gate {key} is invalid")

    oracle = _mapping(
        record["oracle"],
        "oracle",
        {"truth", "classification", "source_sha256", "graded_at"},
    )
    classification = oracle["classification"]
    if classification not in CLASSIFICATIONS:
        raise CampaignError("oracle classification is unsupported")
    truth = oracle["truth"]
    if classification == "oracle_error":
        if truth is not None:
            raise CampaignError("oracle_error classification requires null truth")
    elif not isinstance(truth, bool):
        raise CampaignError("oracle truth must be boolean")
    elif _EXPECTED_CLASSIFICATION[(gate["verdict"], truth)] != classification:
        raise CampaignError("oracle classification does not match verdict and truth")
    if not isinstance(oracle["source_sha256"], str) or not _SHA256.fullmatch(
        oracle["source_sha256"]
    ):
        raise CampaignError("oracle source_sha256 is invalid")
    _timestamp(oracle["graded_at"], "oracle graded_at")

    ai = _mapping(
        record["ai"],
        "ai",
        {"wall_seconds", "usage_value", "usage_unit", "model", "human_step"},
    )
    if ai["wall_seconds"] is not None:
        _non_negative_number(ai["wall_seconds"], "ai wall_seconds")
    if ai["usage_value"] is None:
        if ai["usage_unit"] is not None:
            raise CampaignError("ai usage value and unit must be supplied together")
    else:
        _non_negative_number(ai["usage_value"], "ai usage_value")
        _text(ai["usage_unit"], "ai usage_unit", 32)
    for key in ("model", "human_step"):
        if ai[key] is not None:
            _text(ai[key], f"ai {key}", 256)

    return json.loads(json.dumps(record, ensure_ascii=False, allow_nan=False))


def build_campaign_data(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a deterministic aggregate from validated campaign records."""

    validated = [validate_record(item) for item in records]
    validated.sort(key=lambda item: (item["gate"]["finished_at"], item["run_id"]))
    primary = [item for item in validated if item["run_kind"] == "trial"]
    oracle_valid = [
        item for item in primary if item["oracle"]["classification"] != "oracle_error"
    ]
    classifications = Counter(item["oracle"]["classification"] for item in primary)
    automated = [
        item
        for item in oracle_valid
        if item["gate"]["verdict"] in {"PASS", "FAIL"}
    ]
    passes = [item for item in oracle_valid if item["gate"]["verdict"] == "PASS"]
    false_releases = classifications["FALSE_RELEASE"]
    false_blocks = classifications["FALSE_BLOCK"]
    escalations = classifications["escalated"]
    canonical = json.dumps(
        validated,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return {
        "version": 1,
        "generation_id": hashlib.sha256(canonical).hexdigest(),
        "generated_at": (
            max(item["oracle"]["graded_at"] for item in validated)
            if validated
            else None
        ),
        "record_count": len(validated),
        "run_kind_counts": {
            kind: sum(item["run_kind"] == kind for item in validated)
            for kind in RUN_KINDS
        },
        "primary": {
            "attempts": len(primary),
            "oracle_valid": len(oracle_valid),
            "oracle_errors": classifications["oracle_error"],
            "classification_counts": {
                name: classifications[name]
                for name in CLASSIFICATIONS
                if name != "oracle_error"
            },
            "metrics": {
                "automation_coverage": wilson_interval(
                    events=len(automated), trials=len(oracle_valid)
                ),
                "false_release_per_total": wilson_interval(
                    events=false_releases, trials=len(oracle_valid)
                ),
                "false_release_given_pass": wilson_interval(
                    events=false_releases, trials=len(passes)
                ),
                "false_block_per_total": wilson_interval(
                    events=false_blocks, trials=len(oracle_valid)
                ),
                "escalation_rate": wilson_interval(
                    events=escalations, trials=len(oracle_valid)
                ),
            },
            "wall_time": _summary(
                [item["ai"]["wall_seconds"] for item in primary]
            ),
            "usage_by_unit": _usage_summaries(primary),
            "model_counts": _categorical(primary, "model"),
            "human_step_counts": _categorical(primary, "human_step"),
        },
        "records": validated,
    }


def render_campaign_html(data: dict[str, Any]) -> str:
    """Render a self-contained, escaped view of campaign aggregate data."""

    primary = data["primary"]
    metric_labels = {
        "automation_coverage": "Automation coverage",
        "false_release_per_total": "False releases per oracle-valid trial",
        "false_release_given_pass": "False releases given PASS",
        "false_block_per_total": "False blocks per oracle-valid trial",
        "escalation_rate": "Escalations per oracle-valid trial",
    }
    run_kind_rows = "".join(
        _row(kind, value) for kind, value in data["run_kind_counts"].items()
    )
    classification_rows = "".join(
        _row(
            name,
            f"{count} / {primary['oracle_valid']}",
            alert=name == "FALSE_RELEASE",
        )
        for name, count in primary["classification_counts"].items()
    )
    metric_rows = "".join(
        _metric_row(metric_labels[name], metric)
        for name, metric in primary["metrics"].items()
    )
    record_rows = "".join(_record_row(item) for item in data["records"])
    usage_rows = "".join(
        _summary_row(unit, summary)
        for unit, summary in primary["usage_by_unit"].items()
    ) or '<tr><td colspan="6">No known usage values</td></tr>'
    model_rows = _categorical_rows(primary["model_counts"])
    human_rows = _categorical_rows(primary["human_step_counts"])
    generation = _escape(data["generation_id"])
    generated_at = _escape(data["generated_at"] or "no records")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Private Release Gate campaign report</title>
<style>
:root {{ color-scheme: light dark; font-family: ui-sans-serif, system-ui, sans-serif; }}
body {{ margin: 0 auto; max-width: 1100px; padding: 2rem; line-height: 1.45; }}
h1, h2 {{ line-height: 1.15; }}
.private {{ border-left: .4rem solid #8b5cf6; padding: .8rem 1rem; background: #8b5cf615; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(250px,1fr)); gap: 1rem; }}
.card {{ border: 1px solid #8886; border-radius: .4rem; padding: 1rem; overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #8885; padding: .5rem; text-align: left; vertical-align: top; }}
th {{ font-weight: 700; }}
.alert {{ color: #b91c1c; font-weight: 800; }}
code {{ overflow-wrap: anywhere; }}
.muted {{ opacity: .75; }}
</style>
</head>
<body>
<header>
<h1>Private Release Gate campaign report</h1>
<p class="private"><strong>Private demo evaluation.</strong> This local report combines gate decisions with hidden-oracle truth. It is not part of gate evidence or the public decision dashboard.</p>
<p class="muted">Generation <code>{generation}</code><br>Latest grade: {generated_at}</p>
</header>
<main>
<section class="grid" aria-label="Campaign summary">
<div class="card"><h2>Stored records</h2><p>{data['record_count']}</p><table><tbody>{run_kind_rows}</tbody></table></div>
<div class="card"><h2>Primary trials</h2><table><tbody>
{_row('Attempts', primary['attempts'])}
{_row('Oracle-valid', primary['oracle_valid'])}
{_row('Oracle errors', primary['oracle_errors'])}
</tbody></table></div>
</section>
<section class="card"><h2>Classifications</h2><table><thead><tr><th>Classification</th><th>Count / oracle-valid primary trials</th></tr></thead><tbody>{classification_rows}</tbody></table></section>
<section class="card"><h2>Rates and uncertainty</h2><table><thead><tr><th>Metric</th><th>Events / trials</th><th>Estimate</th><th>95% Wilson interval</th></tr></thead><tbody>{metric_rows}</tbody></table></section>
<section class="card"><h2>AI wall time</h2><table><tbody>{_summary_row('seconds', primary['wall_time'])}</tbody></table></section>
<section class="card"><h2>AI usage by unit</h2><table><thead><tr><th>Unit</th><th>Known</th><th>Unknown</th><th>Total</th><th>Mean</th><th>Range</th></tr></thead><tbody>{usage_rows}</tbody></table></section>
<section class="grid">
<div class="card"><h2>Models</h2><table><tbody>{model_rows}</tbody></table></div>
<div class="card"><h2>Human steps</h2><table><tbody>{human_rows}</tbody></table></div>
</section>
<section class="card"><h2>Run records</h2><table><thead><tr><th>Run</th><th>Kind</th><th>Gate</th><th>Oracle</th><th>Classification</th><th>Model</th><th>Human step</th></tr></thead><tbody>{record_rows}</tbody></table></section>
<section class="card"><h2>Interpretation limits</h2><ul>
<li>A gate PASS is not proof of correctness.</li>
<li>The private oracle supplies the truth label.</li>
<li>Small samples have wide uncertainty.</li>
<li>Repeated X1 trials measure X1 repeatability, not general Release Gate safety.</li>
<li>Correlated trials and benchmark or oracle quality limit interpretation.</li>
</ul></section>
</main>
</body>
</html>
"""


def _row(label: object, value: object, *, alert: bool = False) -> str:
    css = ' class="alert"' if alert else ""
    return f"<tr{css}><th>{_escape(label)}</th><td>{_escape(value)}</td></tr>"


def _metric_row(label: str, metric: dict[str, Any]) -> str:
    estimate = _percent(metric["estimate"])
    interval = (
        "unknown"
        if metric["lower_bound"] is None
        else f"{_percent(metric['lower_bound'])} - {_percent(metric['upper_bound'])}"
    )
    return (
        "<tr><th>"
        + _escape(label)
        + "</th><td>"
        + _escape(f"{metric['numerator']} / {metric['denominator']}")
        + "</td><td>"
        + _escape(estimate)
        + "</td><td>"
        + _escape(interval)
        + "</td></tr>"
    )


def _summary_row(label: str, summary: dict[str, Any]) -> str:
    range_text = (
        "unknown"
        if summary["minimum"] is None
        else f"{summary['minimum']:g} - {summary['maximum']:g}"
    )
    values = (
        label,
        summary["known_count"],
        summary["unknown_count"],
        _number(summary["total"]),
        _number(summary["mean"]),
        range_text,
    )
    return "<tr>" + "".join(f"<td>{_escape(value)}</td>" for value in values) + "</tr>"


def _categorical_rows(values: dict[str, int]) -> str:
    return "".join(_row(label, count) for label, count in values.items()) or _row(
        "unknown", 0
    )


def _record_row(item: dict[str, Any]) -> str:
    truth = item["oracle"]["truth"]
    values = (
        item["run_id"],
        item["run_kind"],
        item["gate"]["verdict"],
        "error" if truth is None else "correct" if truth else "wrong",
        item["oracle"]["classification"],
        item["ai"]["model"] or "unknown",
        item["ai"]["human_step"] or "unknown",
    )
    cells = "".join(f"<td>{_escape(value)}</td>" for value in values)
    css = (
        ' class="alert"'
        if item["oracle"]["classification"] == "FALSE_RELEASE"
        else ""
    )
    return f"<tr{css}>{cells}</tr>"


def _percent(value: float | None) -> str:
    return "unknown" if value is None else f"{value * 100:.1f}%"


def _number(value: float | None) -> str:
    return "unknown" if value is None else f"{value:g}"


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _mapping(value: object, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise CampaignError(f"{label} must contain exactly {sorted(keys)}")
    return value


def _text(value: object, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or _CONTROL.search(value)
    ):
        raise CampaignError(f"{label} is invalid")
    return value


def _timestamp(value: object, label: str) -> str:
    text = _text(value, label, 35)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise CampaignError(f"{label} is invalid") from error
    has_zone = text.endswith("Z") or "+" in text[10:] or "-" in text[10:]
    if "T" not in text or not has_zone:
        raise CampaignError(f"{label} is invalid")
    return text


def _non_negative_number(value: object, label: str, *, integer: bool = False) -> float:
    expected = int if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, expected):
        raise CampaignError(f"{label} must be numeric")
    numeric = float(value)
    if not isfinite(numeric) or numeric < 0:
        raise CampaignError(f"{label} must be finite and non-negative")
    return numeric


def _summary(values: list[float | None]) -> dict[str, Any]:
    known = [float(value) for value in values if value is not None]
    return {
        "known_count": len(known),
        "unknown_count": len(values) - len(known),
        "total": sum(known) if known else None,
        "mean": sum(known) / len(known) if known else None,
        "minimum": min(known) if known else None,
        "maximum": max(known) if known else None,
    }


def _usage_summaries(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_unit: defaultdict[str, list[float | None]] = defaultdict(list)
    unknown = 0
    for item in records:
        if item["ai"]["usage_value"] is None:
            unknown += 1
        else:
            by_unit[item["ai"]["usage_unit"]].append(item["ai"]["usage_value"])
    summaries = {unit: _summary(values) for unit, values in sorted(by_unit.items())}
    for summary in summaries.values():
        summary["unknown_count"] = unknown
    return summaries


def _categorical(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                item["ai"][key]
                for item in records
                if item["ai"][key] is not None
            ).items()
        )
    )


def _prepare_root(root: Path) -> Path:
    campaign_root = Path(os.path.abspath(root))
    if campaign_root.exists() or campaign_root.is_symlink():
        _refuse_link(campaign_root)
        if not campaign_root.is_dir():
            raise CampaignError(f"campaign root is not a directory: {campaign_root}")
    else:
        campaign_root.mkdir(parents=True, mode=0o700, exist_ok=True)
        _refuse_link(campaign_root)
        if not campaign_root.is_dir():
            raise CampaignError(f"campaign root is not a directory: {campaign_root}")
    return campaign_root


def _prepare_layout(root: Path) -> tuple[Path, Path, Path]:
    records_dir = root / "records"
    data_path = root / "campaign-v1.json"
    report_path = root / "index.html"
    for path in (records_dir, data_path, report_path):
        if path.exists() or path.is_symlink():
            _refuse_link(path)
    if records_dir.exists():
        if not records_dir.is_dir():
            raise CampaignError(f"records path is not a directory: {records_dir}")
    else:
        records_dir.mkdir(mode=0o700)
    os.chmod(records_dir, 0o700)
    for path in (data_path, report_path):
        if path.exists() and not path.is_file():
            raise CampaignError(f"publication target is not a regular file: {path}")
    return records_dir, data_path, report_path


def _refuse_link(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if stat.S_ISLNK(metadata.st_mode) or (reparse and attributes & reparse):
        raise CampaignError(f"refusing symlink or reparse-point path: {path}")


@contextmanager
def _campaign_lock(root: Path) -> Iterator[None]:
    lock_path = root / ".campaign.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise CampaignError(
            f"campaign is locked; inspect and remove stale lock manually: {lock_path}"
        ) from error
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _load_records(records_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(records_dir.glob("*.json"), key=lambda item: item.name):
        try:
            _refuse_link(path)
            if not path.is_file():
                raise CampaignError("record is not a regular file")
            decoded = json.loads(path.read_text(encoding="utf-8"))
            record = validate_record(decoded)
            if path.name != f"{record['run_id']}.json":
                raise CampaignError("record filename does not match run_id")
            folded = record["run_id"].casefold()
            if folded in seen:
                raise CampaignError("case-insensitive run_id collision")
            seen.add(folded)
            records.append(record)
        except (CampaignError, OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CampaignError(f"invalid campaign record {path.name}: {error}") from error
    return records


def _same_attempt(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    stored = json.loads(json.dumps(existing))
    proposed = json.loads(json.dumps(incoming))
    stored["oracle"].pop("graded_at")
    proposed["oracle"].pop("graded_at")
    return stored == proposed


def _publish_aggregates(
    records: list[dict[str, Any]], data_path: Path, report_path: Path
) -> None:
    data = build_campaign_data(records)
    _atomic_write(data_path, _json_bytes(data))
    _atomic_write(report_path, render_campaign_html(data).encode("utf-8"))


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    _refuse_link(path)
    temporary = path.with_name(
        f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(8)}"
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
