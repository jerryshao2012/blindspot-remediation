"""Demo-only task scorecard: aggregate repeated gate runs from campaign CSVs.

Usage::

    python task_scorecard.py RUNS.csv [MORE.csv ...] [--group-by model,task_ref]

Reads the ``verdict``, ``reason_codes``, ``diff_sha12``, ``cost_usd`` and
``executor_wall_s`` columns. An optional ``oracle`` column (``correct`` or
``wrong``) adds the false-release line; without it the line says
"not labelled".
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from campaign_report import wilson_interval

MINIMUM_RUNS = 20
GREEN_LOWER_BOUND = 0.90
AMBER_LOWER_BOUND = 0.60


def read_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as stream:
            rows.extend(csv.DictReader(stream))
    return rows


def group_rows(
    rows: list[dict[str, str]], keys: tuple[str, ...]
) -> dict[tuple[str, ...], list[dict[str, str]]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(key) or "(none)" for key in keys)].append(row)
    return dict(groups)


def rating(runs: int, lower_bound: float | None) -> str:
    if runs < MINIMUM_RUNS or lower_bound is None:
        return "RED"
    if lower_bound >= GREEN_LOWER_BOUND:
        return "GREEN"
    if lower_bound >= AMBER_LOWER_BOUND:
        return "AMBER"
    return "RED"


def score_task(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Return sections 1-5 of the task scorecard for one group of runs."""

    runs = len(rows)
    passes = [row for row in rows if row["verdict"] == "PASS"]
    interval = wilson_interval(events=len(passes), trials=runs)
    rate = interval["estimate"]
    reasons = Counter(
        code
        for row in rows
        if row["verdict"] != "PASS"
        for code in set(row.get("reason_codes", "").split(";"))
        if code and code != "-"
    )
    distinct = {row["diff_sha12"] for row in rows}
    distinct_passing = {row["diff_sha12"] for row in passes}
    false_release: dict[str, Any] | None = None
    if rows and all(row.get("oracle") in {"correct", "wrong"} for row in rows):
        wrong = sum(row["oracle"] == "wrong" for row in passes)
        false_release = wilson_interval(events=wrong, trials=len(passes))
    return {
        "runs": runs,
        "passes": len(passes),
        "pass_rate": interval,
        "three_in_a_row": rate**3 if rate is not None else None,
        "five_in_a_row": rate**5 if rate is not None else None,
        "reasons": dict(reasons.most_common()),
        "distinct_changes": len(distinct),
        "distinct_passing": len(distinct_passing),
        "median_cost_usd": _median(rows, "cost_usd"),
        "median_wall_s": _median(rows, "executor_wall_s"),
        "false_release_given_pass": false_release,
        "rating": rating(runs, interval["lower_bound"]),
    }


def render(label: str, card: dict[str, Any]) -> str:
    interval = card["pass_rate"]
    rule = "-" * 57
    lines = [
        f" {label} · {card['runs']} runs ({card['distinct_changes']} distinct "
        f"changes, {card['distinct_passing']} passing)",
        f" {rule}",
    ]
    if interval["estimate"] is None:
        lines.append(" Pass rate        no runs")
    else:
        lines += [
            f" Pass rate        {_percent(interval['estimate'])}   (likely "
            f"{_percent(interval['lower_bound'])} - "
            f"{_percent(interval['upper_bound'])})",
            f" 3-in-a-row       {_percent(card['three_in_a_row'])}",
            f" 5-in-a-row       {_percent(card['five_in_a_row'])}",
        ]
    reasons = " · ".join(f"{count} {code}" for code, count in card["reasons"].items())
    lines.append(f" Why not PASS     {reasons or 'none'}")
    if card["median_cost_usd"] is not None or card["median_wall_s"] is not None:
        cost = card["median_cost_usd"]
        wall = card["median_wall_s"]
        lines.append(
            " Median run       "
            + (f"${cost:.2f}" if cost is not None else "cost n/a")
            + " · "
            + (f"{wall:.0f} s" if wall is not None else "time n/a")
        )
    false_release = card["false_release_given_pass"]
    if false_release is None:
        lines.append(" False releases   not labelled (no oracle column)")
    else:
        lines.append(
            f" False releases   {false_release['numerator']} of "
            f"{false_release['denominator']} PASS runs"
        )
    lines += [f" {rule}", f" Rating           {card['rating']}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", nargs="+", type=Path)
    parser.add_argument("--group-by", default="model")
    arguments = parser.parse_args(argv)
    keys = tuple(key.strip() for key in arguments.group_by.split(",") if key.strip())
    groups = group_rows(read_rows(arguments.csv), keys)
    for index, (values, rows) in enumerate(sorted(groups.items())):
        if index:
            print()
        print(render(" · ".join(values), score_task(rows)))
    return 0


def _median(rows: list[dict[str, str]], column: str) -> float | None:
    values = []
    for row in rows:
        try:
            values.append(float(row.get(column) or ""))
        except ValueError:
            continue
    return median(values) if values else None


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


if __name__ == "__main__":
    sys.exit(main())
