from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

DEMO = Path(__file__).parents[1] / "demo" / "python-slugify"


@pytest.fixture
def task(monkeypatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(DEMO))
    spec = importlib.util.spec_from_file_location(
        "python_slugify_task_scorecard", DEMO / "task_scorecard.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def row(verdict="PASS", diff="a", reasons="-", **extra):
    return {
        "verdict": verdict,
        "diff_sha12": diff,
        "reason_codes": reasons,
        "cost_usd": "0.10",
        "executor_wall_s": "60",
        **extra,
    }


def test_task_card_counts_rates_reasons_and_distinct_changes(task):
    rows = [row(diff=str(index % 10)) for index in range(15)]
    rows += [row("NEEDS_HUMAN", "x", "PATH_OUTSIDE_ALLOWED;PATH_REVIEW_REQUIRED")] * 3
    rows += [row("FAIL", "y", "ASSERTION_FAILED")] * 2
    card = task.score_task(rows)
    assert (card["runs"], card["passes"]) == (20, 15)
    assert card["pass_rate"]["estimate"] == pytest.approx(0.75)
    assert card["pass_rate"]["lower_bound"] == pytest.approx(0.5313, abs=1e-3)
    assert card["three_in_a_row"] == pytest.approx(0.75**3)
    assert card["reasons"] == {
        "PATH_OUTSIDE_ALLOWED": 3,
        "PATH_REVIEW_REQUIRED": 3,
        "ASSERTION_FAILED": 2,
    }
    assert (card["distinct_changes"], card["distinct_passing"]) == (12, 10)
    assert card["median_cost_usd"] == pytest.approx(0.10)
    assert card["false_release_given_pass"] is None
    assert card["rating"] == "RED"
    assert "not labelled" in task.render("X1", card)


@pytest.mark.parametrize(
    ("runs", "lower", "expected"),
    [(19, 0.95, "RED"), (20, 0.95, "GREEN"), (50, 0.7, "AMBER"), (50, 0.5, "RED")],
)
def test_rating_uses_lower_bound_and_minimum_runs(task, runs, lower, expected):
    assert task.rating(runs, lower) == expected


def test_oracle_column_adds_false_release_line(task):
    rows = [row(oracle="correct")] * 3 + [row(oracle="wrong")]
    card = task.score_task(rows)
    assert card["false_release_given_pass"]["numerator"] == 1
    assert card["false_release_given_pass"]["denominator"] == 4
    assert "1 of 4 PASS runs" in task.render("X1", card)
