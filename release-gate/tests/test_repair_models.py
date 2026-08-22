"""Tests for repair session models, states, attempts, and serialization."""

from __future__ import annotations

import json
from pathlib import Path

from release_gate.repair.models import (
    ApprovalRequest,
    FinalApproval,
    RepairAttempt,
    RepairSession,
    RepairState,
    RepairStopReason,
    sha256_bytes,
    sha256_file,
)


def test_repair_enums() -> None:
    assert RepairState.AWAITING_APPROVAL.value == "awaiting_approval"
    assert RepairState.REPAIRING.value == "repairing"
    assert RepairState.AWAITING_FINAL_APPROVAL.value == "awaiting_final_approval"
    assert RepairState.STOPPED.value == "stopped"
    assert RepairState.CANCELLED.value == "cancelled"
    assert RepairState.APPLIED.value == "applied"

    assert RepairStopReason.ALREADY_PASS.value == "already_pass"
    assert RepairStopReason.INELIGIBLE_VERDICT.value == "ineligible_verdict"
    assert RepairStopReason.INELIGIBLE_REASON_CODES.value == "ineligible_reason_codes"
    assert RepairStopReason.POLICY_CHANGED.value == "policy_changed"
    assert RepairStopReason.LAUNCHER_CHANGED.value == "launcher_changed"
    assert RepairStopReason.HARNESS_CHANGED.value == "harness_changed"
    assert RepairStopReason.INVALID_EVIDENCE.value == "invalid_evidence"
    assert RepairStopReason.ATTEMPT_BUDGET_EXHAUSTED.value == "attempt_budget_exhausted"
    assert RepairStopReason.REPEATED_CANDIDATE.value == "repeated_candidate"
    assert RepairStopReason.SOURCE_CHANGED.value == "source_changed"
    assert RepairStopReason.ROLLBACK_FAILED.value == "rollback_failed"
    assert RepairStopReason.CANCELLED_BY_USER.value == "cancelled_by_user"


def test_sha256_helpers(tmp_path: Path) -> None:
    data = b"hello release-gate repair"
    expected = "8e9d7216367b549185ca133c20bb46c70c353c67dd3eb4d7bdd92e85a504ee08"
    assert sha256_bytes(data) == expected

    file_path = tmp_path / "test.txt"
    file_path.write_bytes(data)
    assert sha256_file(file_path) == expected


def test_repair_attempt_roundtrip() -> None:
    attempt = RepairAttempt(
        candidate_label="C0",
        gate_run_id="run-123456",
        base_commit="a" * 40,
        candidate_tree="b" * 40,
        patch_digest="c" * 64,
        result_digest="d" * 64,
        manifest_digest="e" * 64,
        verdict="FAIL",
        reason_codes=("COMMAND_FAILED",),
        failed_check_ids=("unit-tests",),
    )
    data = attempt.to_dict()
    restored = RepairAttempt.from_dict(data)
    assert restored == attempt
    assert json.loads(json.dumps(data)) == data


def test_repair_session_roundtrip() -> None:
    attempt0 = RepairAttempt(
        candidate_label="C0",
        gate_run_id="run-c0",
        base_commit="1" * 40,
        candidate_tree="2" * 40,
        patch_digest="3" * 64,
        result_digest="4" * 64,
        manifest_digest="5" * 64,
        verdict="FAIL",
        reason_codes=("COMMAND_FAILED",),
        failed_check_ids=("check-1",),
    )
    session = RepairSession(
        version=1,
        session_id="rep-20260821-abc123",
        repo_path="/path/to/repo",
        base_ref="origin/main",
        base_commit="1" * 40,
        approved_paths=("src/foo.py", "tests/test_foo.py"),
        attempt_cap=2,
        attempts=(attempt0,),
        state=RepairState.REPAIRING,
        next_action="edit_workspace",
        created_at="2026-08-21T21:00:00Z",
        updated_at="2026-08-21T21:05:00Z",
        stop_reason=None,
    )
    data = session.to_dict()
    restored = RepairSession.from_dict(data)
    assert restored == session
    assert restored.state is RepairState.REPAIRING
    assert restored.stop_reason is None

    # Test stopped session
    stopped_session = RepairSession(
        version=1,
        session_id="rep-20260821-abc123",
        repo_path="/path/to/repo",
        base_ref="origin/main",
        base_commit="1" * 40,
        approved_paths=("src/foo.py",),
        attempt_cap=2,
        attempts=(attempt0,),
        state=RepairState.STOPPED,
        next_action="none",
        created_at="2026-08-21T21:00:00Z",
        updated_at="2026-08-21T21:05:00Z",
        stop_reason=RepairStopReason.ATTEMPT_BUDGET_EXHAUSTED,
    )
    stopped_data = stopped_session.to_dict()
    restored_stopped = RepairSession.from_dict(stopped_data)
    assert restored_stopped == stopped_session
    assert restored_stopped.stop_reason is RepairStopReason.ATTEMPT_BUDGET_EXHAUSTED


def test_approval_request_and_final_approval_roundtrips() -> None:
    req = ApprovalRequest(
        session_id="rep-123",
        base_ref="main",
        base_commit="a" * 40,
        failed_check_ids=("check-1",),
        approved_paths=("src/app.py",),
        attempt_cap=2,
        explanation="Deterministic test failure eligible for repair",
    )
    assert ApprovalRequest.from_dict(req.to_dict()) == req

    final_app = FinalApproval(
        session_id="rep-123",
        final_candidate_tree="b" * 40,
        final_patch_digest="c" * 64,
        approved_at="2026-08-21T21:10:00Z",
    )
    assert FinalApproval.from_dict(final_app.to_dict()) == final_app
