"""
Command-line utilities for benchmark validation and statistical qualification.

The CLI deliberately supports benchmark validation and report analysis without
pretending that a production PipelineAdapter exists.

Running the full campaign requires deployment-specific integration with
Components 2–4.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .benchmark import BenchmarkFactory
from .metrics import CampaignMetricsCalculator
from .models import (
    CaseEvaluationResult,
    QualificationSettings,
)
from .readiness import ReadinessEvaluator
from .statistics import StatisticalAnalyzer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline-level AI engineering qualification."
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    validate = commands.add_parser(
        "validate-benchmark",
        help="Validate benchmark definitions and hidden-oracle integrity.",
    )
    validate.add_argument("--cases", type=Path, required=True)
    validate.add_argument("--benchmark-id", required=True)
    validate.add_argument("--benchmark-version", required=True)
    validate.add_argument("--output", type=Path, required=True)

    analyze = commands.add_parser(
        "analyze-results",
        help="Calculate campaign statistics from case-level results.",
    )
    analyze.add_argument("--results", type=Path, required=True)
    analyze.add_argument("--config", type=Path, required=True)

    return parser


def validate_benchmark(args: argparse.Namespace) -> int:
    benchmark = BenchmarkFactory().load_and_validate(
        benchmark_id=args.benchmark_id,
        benchmark_version=args.benchmark_version,
        cases_path=args.cases,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)

    args.output.write_text(
        benchmark.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    print(benchmark.model_dump_json(indent=2))

    return 0


def analyze_results(args: argparse.Namespace) -> int:
    try:
        raw = CaseEvaluationResult.__pydantic_validator__
    except AttributeError:
        raw = None

    import json

    data = json.loads(
        args.results.read_text(encoding="utf-8")
    )

    if not isinstance(data, list):
        raise ValueError(
            "Results file must contain a JSON list."
        )

    results = tuple(
        CaseEvaluationResult.model_validate(item)
        for item in data
    )

    settings = QualificationSettings.from_yaml(args.config)

    statistics = StatisticalAnalyzer()

    metrics = CampaignMetricsCalculator(
        statistics
    ).calculate(
        results,
        confidence_level=settings.confidence_level,
    )

    readiness = ReadinessEvaluator().evaluate(
        metrics=metrics,
        policy=settings.policy,
    )

    print(
        metrics.model_dump_json(indent=2)
    )

    print(
        readiness.model_dump_json(indent=2)
    )

    return 0 if readiness.status.value == "qualified" else 4


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "validate-benchmark":
            return validate_benchmark(args)

        if args.command == "analyze-results":
            return analyze_results(args)

        parser.error(
            f"Unsupported command {args.command!r}."
        )
        return 1

    except Exception as exc:
        print(
            f"Pipeline evaluation failure: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
