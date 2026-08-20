"""Private, demo-only campaign records and aggregate reporting."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from math import isfinite, sqrt
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
