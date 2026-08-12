"""
Command-line entry point for Component 3.

The CLI receives a GateRequest plus the candidate patch artifact returned by
Component 2.

Exit codes
----------
0: PASS
2: HUMAN_REVIEW_REQUIRED
3: MORE_EVIDENCE_REQUIRED
4: FAIL
1: Input, configuration, or unrecoverable gate failure
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from ai_engineering_contracts import (
    ArtifactKind,
    ArtifactReference,
    GateDecision,
    GateRequest,
)

from .artifacts import sha256_bytes
from .models import (
    DeterministicGateExecutionRequest,
    GateRuntimeSettings,
)
from .service import ReleaseGateService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate an immutable candidate patch with the deterministic "
            "ReleaseGateService."
        )
    )
    parser.add_argument(
        "--gate-request",
        type=Path,
        required=True,
        help="Path to a GateRequest JSON document.",
    )
    parser.add_argument(
        "--candidate-patch",
        type=Path,
        required=True,
        help="Path to the immutable candidate patch from Component 2.",
    )
    parser.add_argument(
        "--candidate-patch-metadata",
        type=Path,
        required=True,
        help=(
            "Path to the ExecutionResult JSON from Component 2. The CLI uses "
            "its patch metadata and digest to construct the patch reference."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to gate runtime YAML configuration.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path at which GateResult JSON will be written.",
    )
    return parser.parse_args()


def load_gate_request(path: Path) -> GateRequest:
    try:
        return GateRequest.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise RuntimeError(
            f"Unable to load GateRequest {path}: {exc}"
        ) from exc


def build_candidate_patch_reference(
    *,
    patch_path: Path,
    execution_result_path: Path,
) -> ArtifactReference:
    from ai_engineering_contracts import ExecutionResult

    try:
        execution_result = ExecutionResult.model_validate_json(
            execution_result_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise RuntimeError(
            f"Unable to load ExecutionResult {execution_result_path}: {exc}"
        ) from exc
    if execution_result.patch_artifact is None:
        raise RuntimeError(
            "ExecutionResult does not contain a candidate patch artifact."
        )
    resolved_patch = patch_path.expanduser().resolve()
    try:
        content = resolved_patch.read_bytes()
    except OSError as exc:
        raise RuntimeError(
            f"Unable to read candidate patch {resolved_patch}: {exc}"
        ) from exc
    digest = sha256_bytes(content)
    if digest != execution_result.patch_artifact.sha256:
        raise RuntimeError(
            "Candidate patch bytes do not match ExecutionResult.patch_artifact."
        )
    return ArtifactReference(
        artifact_id=execution_result.patch_artifact.artifact_id,
        kind=ArtifactKind.PATCH,
        uri=resolved_patch.as_uri(),
        sha256=digest,
        media_type=execution_result.patch_artifact.media_type,
        size_bytes=len(content),
        immutable=True,
        metadata=execution_result.patch_artifact.metadata,
    )


async def run(args: argparse.Namespace) -> int:
    gate_request = load_gate_request(args.gate_request)
    settings = GateRuntimeSettings.from_yaml(args.config)
    candidate_patch = build_candidate_patch_reference(
        patch_path=args.candidate_patch,
        execution_result_path=args.candidate_patch_metadata,
    )
    request = DeterministicGateExecutionRequest(
        gate_request=gate_request,
        candidate_patch=candidate_patch,
    )
    result = await ReleaseGateService(
        settings=settings
    ).evaluate(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        result.to_pretty_json() + "\n",
        encoding="utf-8",
    )
    print(result.to_pretty_json())
    return {
        GateDecision.PASS: 0,
        GateDecision.HUMAN_REVIEW_REQUIRED: 2,
        GateDecision.MORE_EVIDENCE_REQUIRED: 3,
        GateDecision.FAIL: 4,
    }[result.decision]


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        print(
            f"Release-gate input or execution failure: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
