"""
Local POC command-line analysis.

The input file contains normalized WorkItemEconomicsRecord objects.

This keeps the demonstration executable without pretending that Jira, Azure
billing, deployment, and labour integrations have already been implemented.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .aggregation import EngineeringEconomicsCalculator
from .models import (
    BaselineMetrics,
    EconomicsSettings,
    WorkItemEconomicsRecord,
)
from .policy import ValueAssessmentService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate engineering productivity and automation unit economics."
        )
    )

    parser.add_argument(
        "--records",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--config",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--window-start",
        required=True,
    )

    parser.add_argument(
        "--window-end",
        required=True,
    )

    parser.add_argument(
        "--baseline",
        type=Path,
        required=False,
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        raw = json.loads(
            args.records.read_text(encoding="utf-8")
        )

        if not isinstance(raw, list):
            raise ValueError(
                "Records file must contain a JSON list."
            )

        records = tuple(
            WorkItemEconomicsRecord.model_validate(item)
            for item in raw
        )

        settings = EconomicsSettings.from_yaml(
            args.config
        )

        report = EngineeringEconomicsCalculator().calculate(
            records=records,
            window_start=datetime.fromisoformat(
                args.window_start
            ),
            window_end=datetime.fromisoformat(
                args.window_end
            ),
            currency=settings.currency,
            confidence_level=settings.policy.confidence_level,
        )

        print(report.model_dump_json(indent=2))

        if args.baseline is None:
            return 0

        baseline = BaselineMetrics.model_validate_json(
            args.baseline.read_text(encoding="utf-8")
        )

        assessment = ValueAssessmentService().evaluate(
            report=report,
            baseline=baseline,
            policy=settings.policy,
        )

        print(assessment.model_dump_json(indent=2))

        return (
            0
            if assessment.status.value == "value_demonstrated"
            else 4
        )

    except Exception as exc:
        print(
            "Engineering-economics evaluation failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
