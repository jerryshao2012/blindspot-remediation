"""Tests for repair attempt eligibility evaluation."""

from __future__ import annotations

import hashlib
from pathlib import Path

from release_gate import __version__
from release_gate.evidence import FINALIZATION_RESERVE, EvidenceRun
from release_gate.repair.controller import assess_attempt
from release_gate.repair.models import RepairStopReason
from release_gate.trace import TraceRecorder


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _create_fake_run(
    tmp_path: Path,
    run_id: str,
    *,
    verdict: str,
    reason_codes: list[str],
    checks: list[dict],
    scope: dict | None = None,
    corrupt: bool = False,
) -> Path:
    patch = b"diff --git a/foo.py b/foo.py\n"
    config = b'{"checks":[],"version":1}\n'
    started = "2026-08-21T21:00:00Z"
    finished = "2026-08-21T21:00:01Z"

    run = EvidenceRun.create(
        tmp_path,
        run_id,
        total_bytes=FINALIZATION_RESERVE + len(patch) + len(config) + 100,
        patch=patch,
        effective_config=config,
    )

    scope_obj = scope or {
        "status": "PASS",
        "changed_paths": ["foo.py"],
        "outside_allowed_paths": [],
        "forbidden_paths": [],
        "review_required_paths": [],
        "reason_codes": [],
    }

    exit_code_map = {"PASS": 0, "FAIL": 1, "NEEDS_HUMAN": 2}

    result = {
        "version": 1,
        "run_id": run_id,
        "verdict": verdict,
        "exit_code": exit_code_map[verdict],
        "reason_codes": reason_codes,
        "started_at": started,
        "finished_at": finished,
        "duration_ms": 1000,
        "base_commit": "0" * 40,
        "candidate_tree": "2" * 40,
        "patch_sha256": _sha(patch),
        "config_sha256": _sha(config),
        "scope": scope_obj,
        "checks": checks,
        "manifest_path": "manifest.json",
    }

    exec_classification = "fail" if verdict == "FAIL" else "pass"
    exec_reason_codes = ["COMMAND_FAILED"] if exec_classification == "fail" else []

    execution = {
        "control_id": checks[0]["id"] if checks else "check-1",
        "phase": "check",
        "side": "candidate",
        "argv": ["pytest"],
        "cwd": ".",
        "environment_keys": ["HOME", "PATH"],
        "started_at": started,
        "finished_at": finished,
        "duration_ms": 1000,
        "classification": exec_classification,
        "exit_code": 1 if exec_classification == "fail" else 0,
        "timed_out": False,
        "reason_codes": exec_reason_codes,
        "metrics": {},
    }

    manifest = {
        "version": 1,
        "run_id": run_id,
        "hash_algorithm": "sha256",
        "created_at": finished,
        "started_at": started,
        "finished_at": finished,
        "duration_ms": 1000,
        "base_commit": "0" * 40,
        "candidate_tree": "2" * 40,
        "patch_sha256": _sha(patch),
        "config_sha256": _sha(config),
        "engine_version": __version__,
        "platform": {
            "family": "linux",
            "system": "Linux",
            "release": "6.0.0",
            "machine": "x86_64",
        },
        "runtime": {
            "implementation": "CPython",
            "version": "3.12.0",
            "executable": "/usr/bin/python3",
            "executable_sha256": "4" * 64,
        },
        "reason_codes": reason_codes,
        "executions": [execution],
    }

    trace = TraceRecorder()
    trace.add("candidate_captured", changed_paths=1)
    trace_bytes = trace.finish(reason_codes=tuple(reason_codes))

    run.finalize(result, manifest, trace_bytes)

    if corrupt:
        (run.path / "result.json").write_bytes(b"corrupted")

    return run.path


def test_assess_pass_returns_already_pass(tmp_path: Path) -> None:
    run_dir = _create_fake_run(
        tmp_path,
        "run-pass",
        verdict="PASS",
        reason_codes=[],
        checks=[
            {
                "id": "unit-test",
                "mode": "candidate",
                "severity": "blocking",
                "status": "PASS",
                "reason_codes": [],
                "assertions": [],
            }
        ],
    )
    assessment = assess_attempt(run_dir)
    assert not assessment.eligible
    assert assessment.stop_reason is RepairStopReason.ALREADY_PASS
    assert assessment.verdict == "PASS"


def test_assess_needs_human_is_ineligible(tmp_path: Path) -> None:
    run_dir = _create_fake_run(
        tmp_path,
        "run-human",
        verdict="NEEDS_HUMAN",
        reason_codes=["PATH_REVIEW_REQUIRED"],
        checks=[
            {
                "id": "unit-test",
                "mode": "candidate",
                "severity": "blocking",
                "status": "PASS",
                "reason_codes": [],
                "assertions": [],
            }
        ],
        scope={
            "status": "NEEDS_HUMAN",
            "changed_paths": ["foo.py"],
            "outside_allowed_paths": [],
            "forbidden_paths": [],
            "review_required_paths": ["foo.py"],
            "reason_codes": ["PATH_REVIEW_REQUIRED"],
        },
    )
    assessment = assess_attempt(run_dir)
    assert not assessment.eligible
    assert assessment.stop_reason is RepairStopReason.INELIGIBLE_VERDICT
    assert assessment.verdict == "NEEDS_HUMAN"


def test_assess_policy_or_launcher_changed(tmp_path: Path) -> None:
    run_dir1 = _create_fake_run(
        tmp_path,
        "run-policy",
        verdict="NEEDS_HUMAN",
        reason_codes=["POLICY_FILE_CHANGED"],
        checks=[
            {
                "id": "unit-test",
                "mode": "candidate",
                "severity": "blocking",
                "status": "PASS",
                "reason_codes": [],
                "assertions": [],
            }
        ],
    )
    assessment1 = assess_attempt(run_dir1)
    assert not assessment1.eligible
    assert assessment1.stop_reason is RepairStopReason.POLICY_CHANGED

    run_dir2 = _create_fake_run(
        tmp_path,
        "run-launcher",
        verdict="NEEDS_HUMAN",
        reason_codes=["CONTROL_LAUNCHER_REVIEW"],
        checks=[
            {
                "id": "unit-test",
                "mode": "candidate",
                "severity": "blocking",
                "status": "PASS",
                "reason_codes": [],
                "assertions": [],
            }
        ],
    )
    assessment2 = assess_attempt(run_dir2)
    assert not assessment2.eligible
    assert assessment2.stop_reason is RepairStopReason.LAUNCHER_CHANGED


def test_assess_eligible_fail(tmp_path: Path) -> None:
    run_dir = _create_fake_run(
        tmp_path,
        "run-fail",
        verdict="FAIL",
        reason_codes=["COMMAND_FAILED"],
        checks=[
            {
                "id": "pytest",
                "mode": "candidate",
                "severity": "blocking",
                "status": "FAIL",
                "reason_codes": ["COMMAND_FAILED"],
                "assertions": [],
            }
        ],
    )
    assessment = assess_attempt(run_dir)
    assert assessment.eligible
    assert assessment.stop_reason is None
    assert assessment.failed_check_ids == ("pytest",)


def test_assess_fail_with_assertion_failure(tmp_path: Path) -> None:
    run_dir = _create_fake_run(
        tmp_path,
        "run-fail-assert",
        verdict="FAIL",
        reason_codes=["ASSERTION_FAILED"],
        checks=[
            {
                "id": "coverage",
                "mode": "candidate",
                "severity": "blocking",
                "status": "FAIL",
                "reason_codes": ["ASSERTION_FAILED"],
                "assertions": [
                    {
                        "report": "cov",
                        "metric": "/line_rate",
                        "comparison": "candidate",
                        "operator": "gte",
                        "expected": 0.9,
                        "actual": 0.85,
                        "passed": False,
                        "reason_codes": ["ASSERTION_FAILED"],
                    }
                ],
            }
        ],
    )
    assessment = assess_attempt(run_dir)
    assert assessment.eligible
    assert assessment.stop_reason is None
    assert assessment.failed_check_ids == ("coverage",)


def test_assess_fail_with_scope_or_error_is_ineligible(tmp_path: Path) -> None:
    # Scope failure
    run_dir1 = _create_fake_run(
        tmp_path,
        "run-scope-forbidden",
        verdict="FAIL",
        reason_codes=["PATH_FORBIDDEN"],
        checks=[
            {
                "id": "unit-test",
                "mode": "candidate",
                "severity": "blocking",
                "status": "PASS",
                "reason_codes": [],
                "assertions": [],
            }
        ],
        scope={
            "status": "FAIL",
            "changed_paths": ["secrets.key"],
            "outside_allowed_paths": [],
            "forbidden_paths": ["secrets.key"],
            "review_required_paths": [],
            "reason_codes": ["PATH_FORBIDDEN"],
        },
    )
    assessment1 = assess_attempt(run_dir1)
    assert not assessment1.eligible
    assert assessment1.stop_reason is RepairStopReason.INELIGIBLE_REASON_CODES

    # Check status ERROR
    run_dir2 = _create_fake_run(
        tmp_path,
        "run-error-check",
        verdict="NEEDS_HUMAN",
        reason_codes=["COMMAND_TIMED_OUT"],
        checks=[
            {
                "id": "build",
                "mode": "candidate",
                "severity": "blocking",
                "status": "ERROR",
                "reason_codes": ["COMMAND_TIMED_OUT"],
                "assertions": [],
            }
        ],
    )
    assessment2 = assess_attempt(run_dir2)
    assert not assessment2.eligible
    assert assessment2.stop_reason is RepairStopReason.INELIGIBLE_VERDICT


def test_assess_invalid_evidence(tmp_path: Path) -> None:
    run_dir = _create_fake_run(
        tmp_path,
        "run-corrupt",
        verdict="FAIL",
        reason_codes=["COMMAND_FAILED"],
        checks=[
            {
                "id": "pytest",
                "mode": "candidate",
                "severity": "blocking",
                "status": "FAIL",
                "reason_codes": ["COMMAND_FAILED"],
                "assertions": [],
            }
        ],
        corrupt=True,
    )
    assessment = assess_attempt(run_dir)
    assert not assessment.eligible
    assert assessment.stop_reason is RepairStopReason.INVALID_EVIDENCE
