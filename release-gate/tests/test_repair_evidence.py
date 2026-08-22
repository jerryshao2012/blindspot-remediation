"""Tests for repair session evidence persistence and observability isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from release_gate.observability import build_report
from release_gate.repair.evidence import RepairEvidence
from release_gate.repair.models import (
    ApprovalRequest,
    RepairAttempt,
    RepairSession,
    RepairState,
)


def test_repair_evidence_lifecycle(tmp_path: Path) -> None:
    evidence_root = tmp_path / ".release-gate" / "runs"
    evidence_root.mkdir(parents=True)
    session_id = "rep-test-123"

    repair_ev = RepairEvidence.create(evidence_root, session_id)
    assert repair_ev.session_dir.exists()
    assert repair_ev.session_dir.name == session_id
    assert repair_ev.session_dir.parent.name == "_repairs"

    # Write approval request
    req = ApprovalRequest(
        session_id=session_id,
        base_ref="origin/main",
        base_commit="a" * 40,
        failed_check_ids=("pytest",),
        approved_paths=("src/app.py",),
        attempt_cap=2,
        explanation="Deterministic test failure",
    )
    repair_ev.write_approval_request(req)
    assert repair_ev.read_approval_request() == req

    # Write session
    attempt0 = RepairAttempt(
        candidate_label="C0",
        gate_run_id="run-c0",
        base_commit="a" * 40,
        candidate_tree="b" * 40,
        patch_digest="c" * 64,
        result_digest="d" * 64,
        manifest_digest="e" * 64,
        verdict="FAIL",
        reason_codes=("COMMAND_FAILED",),
        failed_check_ids=("pytest",),
    )
    session = RepairSession(
        version=1,
        session_id=session_id,
        repo_path=str(tmp_path),
        base_ref="origin/main",
        base_commit="a" * 40,
        approved_paths=("src/app.py",),
        attempt_cap=2,
        attempts=(attempt0,),
        state=RepairState.REPAIRING,
        next_action="edit_workspace",
        created_at="2026-08-21T21:00:00Z",
        updated_at="2026-08-21T21:05:00Z",
    )
    repair_ev.write_session(session)
    assert repair_ev.read_session() == session

    # Write summary
    summary_text = "# Repair Summary\n\nAttempted 1 repair."
    repair_ev.write_summary(summary_text)
    assert (repair_ev.session_dir / "repair-summary.md").read_text() == summary_text

    # Write lesson proposal
    proposal_text = "# Lesson Proposal\n\nAdd type annotations."
    repair_ev.write_lesson_proposal(proposal_text)
    assert (repair_ev.session_dir / "lesson-proposal.md").read_text() == proposal_text

    # Write manifest
    manifest = repair_ev.write_manifest()
    assert manifest["session_id"] == session_id
    assert len(manifest["artifacts"]) >= 4
    assert (repair_ev.session_dir / "repair-manifest.json").exists()

    # Verify session load
    loaded_ev = RepairEvidence.load(evidence_root, session_id)
    assert loaded_ev.read_session() == session


def test_observability_ignores_repairs_directory(tmp_path: Path) -> None:
    evidence_root = tmp_path / "runs"
    evidence_root.mkdir()

    # Create normal run
    from test_observability import write_valid_run

    write_valid_run(evidence_root, "run-valid-1")

    # Create _repairs directory with dummy contents
    repairs_dir = evidence_root / "_repairs"
    repairs_dir.mkdir()
    (repairs_dir / "rep-123").mkdir()
    (repairs_dir / "rep-123" / "repair-session-v1.json").write_text("{}")

    report = build_report(evidence_root)
    assert len(report["source_runs"]) == 1
    assert report["source_runs"][0]["run_id"] == "run-valid-1"
    assert report["diagnostics"]["skipped_runs"] == 0
    assert report["diagnostics"]["warnings"] == []


def test_repair_evidence_rejects_path_escaping_session_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="session ID"):
        RepairEvidence.create(tmp_path, "../escape")
