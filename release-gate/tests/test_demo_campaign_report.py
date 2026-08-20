from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

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
