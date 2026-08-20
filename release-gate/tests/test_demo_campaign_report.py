from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
MODULE = ROOT / "demo" / "python-slugify" / "campaign_report.py"


def load_campaign() -> ModuleType:
    spec = importlib.util.spec_from_file_location("python_slugify_campaign", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def record(
    run_id: str,
    *,
    run_kind: str = "trial",
    verdict: str = "PASS",
    truth: bool | None = True,
    classification: str = "good_pass",
    wall_seconds: float | None = 10.0,
    usage_value: float | None = 2.0,
    usage_unit: str | None = "AIC",
    model: str | None = "model-a",
    human_step: str | None = "none",
) -> dict[str, Any]:
    digit = str((sum(map(ord, run_id)) % 9) + 1)
    return {
        "version": 1,
        "run_id": run_id,
        "run_kind": run_kind,
        "gate": {
            "verdict": verdict,
            "finished_at": "2026-08-20T12:00:00Z",
            "duration_ms": 1200,
            "base_commit": digit * 40,
            "candidate_tree": digit * 40,
            "patch_sha256": digit * 64,
            "config_sha256": digit * 64,
            "result_sha256": digit * 64,
        },
        "oracle": {
            "truth": truth,
            "classification": classification,
            "source_sha256": "a" * 64,
            "graded_at": "2026-08-20T12:05:00Z",
        },
        "ai": {
            "wall_seconds": wall_seconds,
            "usage_value": usage_value,
            "usage_unit": usage_unit,
            "model": model,
            "human_step": human_step,
        },
    }


@pytest.mark.parametrize(
    ("trials", "rounded_upper"),
    [(5, 43), (10, 28), (20, 16), (30, 11), (100, 4)],
)
def test_zero_event_wilson_bounds_match_documented_table(
    trials: int, rounded_upper: int
) -> None:
    campaign = load_campaign()

    metric = campaign.wilson_interval(events=0, trials=trials)

    assert metric["numerator"] == 0
    assert metric["denominator"] == trials
    assert round(metric["upper_bound"] * 100) == rounded_upper
    assert metric["confidence_level"] == 0.95
    assert metric["method"] == "wilson"


def test_wilson_zero_denominator_is_unknown_and_invalid_counts_are_rejected() -> None:
    campaign = load_campaign()

    assert campaign.wilson_interval(events=0, trials=0) == {
        "numerator": 0,
        "denominator": 0,
        "estimate": None,
        "lower_bound": None,
        "upper_bound": None,
        "confidence_level": 0.95,
        "method": "wilson",
    }
    with pytest.raises(ValueError, match="events"):
        campaign.wilson_interval(events=2, trials=1)


def test_campaign_uses_only_primary_oracle_valid_trials_for_safety_metrics() -> None:
    campaign = load_campaign()
    records = [
        record("trial-good"),
        record(
            "trial-false-release", truth=False, classification="FALSE_RELEASE"
        ),
        record(
            "trial-oracle-error",
            truth=None,
            classification="oracle_error",
            wall_seconds=None,
            usage_value=None,
            usage_unit=None,
        ),
        record("assisted", run_kind="re-gate", human_step="fixed dependency"),
        record(
            "control",
            run_kind="control",
            verdict="FAIL",
            truth=False,
            classification="good_catch",
        ),
    ]

    data = campaign.build_campaign_data(records)

    assert data["record_count"] == 5
    assert data["run_kind_counts"] == {"trial": 3, "re-gate": 1, "control": 1}
    primary = data["primary"]
    assert primary["attempts"] == 3
    assert primary["oracle_valid"] == 2
    assert primary["oracle_errors"] == 1
    assert primary["classification_counts"]["FALSE_RELEASE"] == 1
    assert primary["metrics"]["false_release_per_total"]["numerator"] == 1
    assert primary["metrics"]["false_release_per_total"]["denominator"] == 2
    assert primary["metrics"]["false_release_given_pass"]["denominator"] == 2
    assert primary["wall_time"]["known_count"] == 2
    assert primary["wall_time"]["unknown_count"] == 1
    assert primary["usage_by_unit"]["AIC"]["known_count"] == 2
    assert [item["run_id"] for item in data["records"]] == [
        "assisted",
        "control",
        "trial-false-release",
        "trial-good",
        "trial-oracle-error",
    ]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("version",), 2),
        (("run_kind",), "unknown"),
        (("gate", "verdict"), "ALLOW"),
        (("oracle", "classification"), "great"),
        (("gate", "patch_sha256"), "not-a-digest"),
        (("ai", "wall_seconds"), -1.0),
        (("ai", "usage_value"), float("nan")),
    ],
)
def test_record_validation_rejects_invalid_fields(
    path: tuple[str, ...], value: object
) -> None:
    campaign = load_campaign()
    candidate = record("invalid")
    target: dict[str, Any] = candidate
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value

    with pytest.raises(campaign.CampaignError):
        campaign.validate_record(candidate)


def test_record_validation_enforces_oracle_classification_matrix() -> None:
    campaign = load_campaign()
    candidate = record("mismatch", truth=False, classification="good_pass")

    with pytest.raises(campaign.CampaignError, match="classification"):
        campaign.validate_record(candidate)

    error = record("oracle-error", truth=None, classification="oracle_error")
    assert campaign.validate_record(error)["oracle"]["truth"] is None


def test_human_step_text_never_changes_structured_primary_cohort() -> None:
    campaign = load_campaign()
    assisted_words = record("words", human_step="re-gate after human fix")
    actual_re_gate = deepcopy(assisted_words)
    actual_re_gate["run_id"] = "structured"
    actual_re_gate["run_kind"] = "re-gate"

    data = campaign.build_campaign_data([assisted_words, actual_re_gate])

    assert data["run_kind_counts"] == {"trial": 1, "re-gate": 1, "control": 0}
    assert data["primary"]["attempts"] == 1


def test_html_is_deterministic_escaped_self_contained_and_honest() -> None:
    campaign = load_campaign()
    value = record(
        "html",
        model="<script>alert(1)</script>",
        human_step="review & fix",
    )
    data = campaign.build_campaign_data([value])

    first = campaign.render_campaign_html(data)
    second = campaign.render_campaign_html(data)

    assert first == second
    assert "<script>alert(1)</script>" not in first
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in first
    assert "review &amp; fix" in first
    assert data["generation_id"] in first
    assert "False releases given PASS" in first
    assert "Repeated X1 trials measure X1 repeatability" in first
    assert "https://" not in first and "http://" not in first


def test_html_displays_false_release_counts_and_wilson_denominators() -> None:
    campaign = load_campaign()
    false_release = record(
        "false-release",
        truth=False,
        classification="FALSE_RELEASE",
    )
    data = campaign.build_campaign_data([false_release])

    rendered = campaign.render_campaign_html(data)

    assert "FALSE_RELEASE" in rendered
    assert "1 / 1" in rendered
    assert "95% Wilson interval" in rendered
