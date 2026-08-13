"""
Export public contracts as JSON Schema Draft 2020-12 documents.

Usage
-----
    export-contract-schemas --output-directory generated-schemas

or:

    python -m ai_engineering_contracts.schema_export \
        --output-directory generated-schemas

The generated files can be used by Python, TypeScript, C#, pipeline validation,
or external services that do not import this package directly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import type

from .base import ContractModel
from .constants import JSON_SCHEMA_DIALECT
from .models import (
    BenchmarkCase,
    CampaignRequest,
    CampaignResult,
    ExecutionResult,
    GateRequest,
    GateResult,
    HumanReviewResult,
    TaskRunRequest,
)

PUBLIC_CONTRACTS: tuple[type[ContractModel], ...] = (
    TaskRunRequest,
    ExecutionResult,
    GateRequest,
    GateResult,
    HumanReviewResult,
    BenchmarkCase,
    CampaignRequest,
    CampaignResult,
)


def export_schemas(output_directory: Path) -> list[Path]:
    """
    Export one schema file per public contract.

    Returns the paths that were written. Existing files with the same names are
    replaced because generated schemas are derived artifacts.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    for contract_type in PUBLIC_CONTRACTS:
        schema = contract_type.model_json_schema(
            mode="validation",
            ref_template="#/$defs/{model}",
        )
        schema["$schema"] = JSON_SCHEMA_DIALECT
        schema["$id"] = f"urn:bmo-ai-engineering-contract:{contract_type.__name__}:0.1.0"
        output_path = output_directory / f"{contract_type.__name__}.schema.json"
        output_path.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written_paths.append(output_path)
    return written_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export AI engineering shared contracts as JSON Schema."
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("generated-schemas"),
        help="Directory in which schema files will be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    written_paths = export_schemas(args.output_directory)
    for path in written_paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
