"""
Simple deterministic CLI for the POC.

The CLI consumes structured process events and calculates a ProcessWindow.

Production systems should normally stream or ingest these events through the
approved enterprise event/telemetry architecture.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .aggregation import ProcessMetricsCalculator
from .models import ProcessEvent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate process outcomes for one deployment."
    )

    parser.add_argument(
        "--events",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--deployment-id",
        required=True,
    )

    parser.add_argument(
        "--process-name",
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
    args = build_parser().parse_args()

    try:
        raw = json.loads(
            args.events.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(raw, list):
            raise ValueError(
                "Process event file must contain a JSON list."
            )

        events = tuple(
            ProcessEvent.model_validate(item)
            for item in raw
        )

        window = ProcessMetricsCalculator().calculate(
            deployment_id=args.deployment_id,
            process_name=args.process_name,
            events=events,
            window_start=datetime.fromisoformat(
                args.window_start
            ),
            window_end=datetime.fromisoformat(
                args.window_end
            ),
        )

        print(
            window.model_dump_json(indent=2)
        )

        return 0

    except Exception as exc:
        print(
            "Process-outcome evaluation failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
