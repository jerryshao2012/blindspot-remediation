"""
Command-line calculation of operational health from exported observations.

This is useful for:

    POC demonstrations
    local testing
    replay
    forensic analysis

Production ingestion should normally be continuous rather than CLI-driven.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .aggregation import OperationalMetricsCalculator
from .models import (
    OperationalSettings,
    RuntimeObservation,
)
from .policy import SLOEvaluator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Production operational evaluation."
    )

    parser.add_argument(
        "--observations",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--config",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--deployment-id",
        required=True,
    )

    parser.add_argument(
        "--service-name",
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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        raw = json.loads(
            args.observations.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(raw, list):
            raise ValueError(
                "Observation file must contain a JSON list."
            )

        observations = tuple(
            RuntimeObservation.model_validate(item)
            for item in raw
        )

        settings = OperationalSettings.from_yaml(
            str(args.config)
        )

        window = OperationalMetricsCalculator().calculate(
            deployment_id=args.deployment_id,
            service_name=args.service_name,
            observations=observations,
            window_start=datetime.fromisoformat(
                args.window_start
            ),
            window_end=datetime.fromisoformat(
                args.window_end
            ),
        )

        decision = SLOEvaluator().evaluate(
            window=window,
            policy=settings.policy,
        )

        print(window.model_dump_json(indent=2))
        print(decision.model_dump_json(indent=2))

        if decision.status.value == "healthy":
            return 0

        if decision.status.value == "insufficient_data":
            return 3

        if decision.status.value == "degraded":
            return 4

        return 5

    except Exception as exc:
        print(
            "Operational evaluation failure: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
