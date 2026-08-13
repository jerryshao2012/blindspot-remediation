"""
CLI for recording and independently verifying evidence.

Commands:

    evidence-store record ...
    evidence-store verify ...

The record command requires the actual outputs of Components 2 and 3.

The verify command can be run later by a different process or operator.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_engineering_contracts import (
    ExecutionResult,
    GateRequest,
    GateResult,
)

from .models import EvidenceStorageSettings
from .recorder import EvidenceRecorder
from .store import LocalContentAddressedEvidenceStore
from .verifier import ManifestVerifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Immutable AI engineering evidence storage."
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    record = subparsers.add_parser(
        "record",
        help="Create and publish an immutable run manifest.",
    )
    record.add_argument("--gate-request", type=Path, required=True)
    record.add_argument("--execution-result", type=Path, required=True)
    record.add_argument("--gate-result", type=Path, required=True)
    record.add_argument("--config", type=Path, required=True)
    record.add_argument("--output", type=Path, required=True)

    verify = subparsers.add_parser(
        "verify",
        help="Verify a published manifest and all evidence objects.",
    )
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--config", type=Path, required=True)

    return parser


def load_json_model(path: Path, model_type):
    try:
        return model_type.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise RuntimeError(
            f"Unable to load {model_type.__name__} from {path}: {exc}"
        ) from exc


def build_store(
    settings: EvidenceStorageSettings,
) -> LocalContentAddressedEvidenceStore:
    return LocalContentAddressedEvidenceStore(
        settings.root,
        verify_after_write=settings.verify_after_write,
    )


def record_command(args: argparse.Namespace) -> int:
    settings = EvidenceStorageSettings.from_yaml(args.config)
    store = build_store(settings)

    gate_request = load_json_model(
        args.gate_request,
        GateRequest,
    )
    execution_result = load_json_model(
        args.execution_result,
        ExecutionResult,
    )
    gate_result = load_json_model(
        args.gate_result,
        GateResult,
    )

    manifest = EvidenceRecorder(store).record_run(
        gate_request=gate_request,
        execution_result=execution_result,
        gate_result=gate_result,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    print(manifest.model_dump_json(indent=2))
    return 0


def verify_command(args: argparse.Namespace) -> int:
    settings = EvidenceStorageSettings.from_yaml(args.config)
    store = build_store(settings)

    result = ManifestVerifier(store).verify_run(args.run_id)

    print(result.model_dump_json(indent=2))

    return 0 if result.valid else 4


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "record":
            return record_command(args)

        if args.command == "verify":
            return verify_command(args)

        parser.error(f"Unsupported command {args.command!r}.")
        return 1

    except Exception as exc:
        print(
            f"Evidence storage failure: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
