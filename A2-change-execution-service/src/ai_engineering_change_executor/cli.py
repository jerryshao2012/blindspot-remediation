"""
Command-line entry point.

Example:

    change-executor \
        --task-request examples/task-request.json \
        --patch examples/change.patch \
        --config config/executor.local.yaml \
        --output artifacts/execution-result.json

The process exits:

* 0 when a candidate was successfully produced;
* 2 when execution completed with a structured non-success status;
* 1 when CLI input itself could not be loaded or validated.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from ai_engineering_contracts import (
    ArtifactKind,
    ArtifactReference,
    ExecutionStatus,
    TaskRunRequest,
)
from pydantic import ValidationError

from .artifacts import sha256_bytes
from .models import ExecutorSettings, ManualPatchExecutionRequest
from .service import ChangeExecutionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply a manually supplied patch through the deterministic "
            "ChangeExecutionService."
        )
    )
    parser.add_argument(
        "--task-request",
        type=Path,
        required=True,
        help="Path to a TaskRunRequest JSON document.",
    )
    parser.add_argument(
        "--patch",
        type=Path,
        required=True,
        help="Path to a Git-compatible unified patch.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to executor YAML configuration.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path at which ExecutionResult JSON will be written.",
    )
    parser.add_argument(
        "--commit-message",
        default=None,
        help=(
            "Candidate commit message. Defaults to a message derived from the "
            "task type and run ID."
        ),
    )
    return parser.parse_args()


def load_task_request(path: Path) -> TaskRunRequest:
    try:
        return TaskRunRequest.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except OSError as exc:
        raise RuntimeError(
            f"Unable to read TaskRunRequest {path}: {exc}"
        ) from exc
    except ValidationError as exc:
        raise RuntimeError(
            f"TaskRunRequest {path} failed validation: {exc}"
        ) from exc


def build_patch_reference(path: Path, run_id: str) -> ArtifactReference:
    resolved = path.expanduser().resolve()
    try:
        content = resolved.read_bytes()
    except OSError as exc:
        raise RuntimeError(
            f"Unable to read patch {resolved}: {exc}"
        ) from exc
    return ArtifactReference(
        artifact_id=f"{run_id}:manual-input.patch",
        kind=ArtifactKind.PATCH,
        uri=resolved.as_uri(),
        sha256=sha256_bytes(content),
        media_type="text/x-diff",
        size_bytes=len(content),
        immutable=True,
        metadata={
            "source": "manual_cli_input",
        },
    )


async def run(args: argparse.Namespace) -> int:
    task = load_task_request(args.task_request)
    settings = ExecutorSettings.from_yaml(args.config)
    patch_reference = build_patch_reference(args.patch, task.run_id)
    commit_message = args.commit_message or (
        f"{task.task_type}: candidate change for {task.run_id}"
    )
    request = ManualPatchExecutionRequest(
        task=task,
        patch_artifact=patch_reference,
        commit_message=commit_message,
    )
    service = ChangeExecutionService(settings=settings)
    result = await service.execute(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        result.to_pretty_json() + "\n",
        encoding="utf-8",
    )
    print(result.to_pretty_json())
    return 0 if result.status == ExecutionStatus.COMPLETED else 2


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        print(
            f"CLI input or configuration failure: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
