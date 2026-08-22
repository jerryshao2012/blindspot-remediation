"""Deterministic repair controller for the Release Gate repair workflow."""

from __future__ import annotations

import json
import secrets
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from release_gate.engine import run_gate
from release_gate.evidence import EvidenceError, verify_run
from release_gate.git import _base_git_environment, _git_binary, capture_candidate
from release_gate.policy import Verdict
from release_gate.repair.evidence import (
    APPROVAL_REQUEST_FILENAME,
    SUMMARY_FILENAME,
    RepairEvidence,
)
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
from release_gate.repair.playbooks import (
    has_harness_changes,
    load_playbooks_from_base,
)
from release_gate.repair.workspace import (
    RepairWorkspace,
    RepairWorkspaceError,
    apply_candidate_to_source,
    compute_approved_paths,
)
from release_gate.timestamps import utc_timestamp

_ALLOWED_FAIL_REASONS = frozenset(
    {
        "COMMAND_FAILED",
        "ASSERTION_FAILED",
    }
)


@dataclass(frozen=True, slots=True)
class AttemptAssessment:
    """Evaluation of a single gate run's eligibility for automatic repair."""

    eligible: bool
    stop_reason: RepairStopReason | None
    verdict: str
    reason_codes: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    explanation: str
    result_data: dict[str, Any]
    manifest_data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RepairSessionOutcome:
    """Standard outcome returned by repair controller commands."""

    session_id: str
    state: RepairState
    next_action: str
    session_dir: Path
    session: RepairSession
    approval_request_path: Path | None = None
    summary_path: Path | None = None
    workspace_path: Path | None = None


def _default_session_id(now: datetime) -> str:
    timestamp = now.strftime("%Y%m%d%H%M%S")
    token = secrets.token_hex(4)
    return f"rep-{timestamp}-{token}"


def assess_attempt(gate_run_dir: Path) -> AttemptAssessment:
    """Verify gate evidence and determine whether the attempt is eligible for repair."""

    try:
        verify_run(gate_run_dir)
        result_bytes = (gate_run_dir / "result.json").read_bytes()
        manifest_bytes = (gate_run_dir / "manifest.json").read_bytes()
        result = json.loads(result_bytes)
        manifest = json.loads(manifest_bytes)
    except (EvidenceError, OSError, json.JSONDecodeError) as error:
        return AttemptAssessment(
            eligible=False,
            stop_reason=RepairStopReason.INVALID_EVIDENCE,
            verdict="ERROR",
            reason_codes=("INVALID_EVIDENCE",),
            failed_check_ids=(),
            explanation=f"Gate run evidence verification failed: {error}",
            result_data={},
            manifest_data={},
        )

    verdict = result.get("verdict", "")
    reason_codes = tuple(str(code) for code in result.get("reason_codes", ()))
    scope = result.get("scope", {})
    scope_reasons = set(scope.get("reason_codes", ()))

    if "POLICY_FILE_CHANGED" in reason_codes or "POLICY_FILE_CHANGED" in scope_reasons:
        return AttemptAssessment(
            eligible=False,
            stop_reason=RepairStopReason.POLICY_CHANGED,
            verdict=verdict,
            reason_codes=reason_codes,
            failed_check_ids=(),
            explanation=(
                "Policy file (.release-gate.yaml) was modified, "
                "which requires manual review."
            ),
            result_data=result,
            manifest_data=manifest,
        )

    if "CONTROL_LAUNCHER_REVIEW" in reason_codes:
        return AttemptAssessment(
            eligible=False,
            stop_reason=RepairStopReason.LAUNCHER_CHANGED,
            verdict=verdict,
            reason_codes=reason_codes,
            failed_check_ids=(),
            explanation=(
                "Control launcher script modified, which requires manual review."
            ),
            result_data=result,
            manifest_data=manifest,
        )

    if verdict == "PASS":
        return AttemptAssessment(
            eligible=False,
            stop_reason=RepairStopReason.ALREADY_PASS,
            verdict=verdict,
            reason_codes=reason_codes,
            failed_check_ids=(),
            explanation="Candidate already passed the release gate.",
            result_data=result,
            manifest_data=manifest,
        )

    if verdict == "NEEDS_HUMAN":
        return AttemptAssessment(
            eligible=False,
            stop_reason=RepairStopReason.INELIGIBLE_VERDICT,
            verdict=verdict,
            reason_codes=reason_codes,
            failed_check_ids=(),
            explanation=(
                "Gate verdict is NEEDS_HUMAN, which cannot be repaired automatically."
            ),
            result_data=result,
            manifest_data=manifest,
        )

    if verdict != "FAIL":
        return AttemptAssessment(
            eligible=False,
            stop_reason=RepairStopReason.INELIGIBLE_VERDICT,
            verdict=verdict,
            reason_codes=reason_codes,
            failed_check_ids=(),
            explanation=f"Unsupported gate verdict: {verdict!r}.",
            result_data=result,
            manifest_data=manifest,
        )

    # Verdict is FAIL: verify scope is clean
    scope_status = scope.get("status", scope.get("verdict", ""))
    if scope_status != "PASS" or any(
        code in {"PATH_FORBIDDEN", "PATH_OUTSIDE_ALLOWED", "PATH_REVIEW_REQUIRED"}
        for code in reason_codes
    ):
        return AttemptAssessment(
            eligible=False,
            stop_reason=RepairStopReason.INELIGIBLE_REASON_CODES,
            verdict=verdict,
            reason_codes=reason_codes,
            failed_check_ids=(),
            explanation=(
                "Candidate contains scope violations or forbidden path changes."
            ),
            result_data=result,
            manifest_data=manifest,
        )

    # Inspect check outcomes
    failed_check_ids: list[str] = []
    for check in result.get("checks", []):
        status = check.get("status")
        check_id = check.get("id", "")
        if status in ("ERROR", "SKIPPED"):
            return AttemptAssessment(
                eligible=False,
                stop_reason=RepairStopReason.INELIGIBLE_REASON_CODES,
                verdict=verdict,
                reason_codes=reason_codes,
                failed_check_ids=(),
                explanation=(
                    f"Check {check_id!r} has status {status}, "
                    "which is not eligible for auto-repair."
                ),
                result_data=result,
                manifest_data=manifest,
            )
        if status == "FAIL":
            if check.get("severity") != "blocking":
                return AttemptAssessment(
                    eligible=False,
                    stop_reason=RepairStopReason.INELIGIBLE_REASON_CODES,
                    verdict=verdict,
                    reason_codes=reason_codes,
                    failed_check_ids=(),
                    explanation=f"Check {check_id!r} is advisory, not blocking.",
                    result_data=result,
                    manifest_data=manifest,
                )
            check_reasons = check.get("reason_codes", [])
            if not check_reasons or any(
                r not in _ALLOWED_FAIL_REASONS for r in check_reasons
            ):
                return AttemptAssessment(
                    eligible=False,
                    stop_reason=RepairStopReason.INELIGIBLE_REASON_CODES,
                    verdict=verdict,
                    reason_codes=reason_codes,
                    failed_check_ids=(),
                    explanation=(
                        f"Check {check_id!r} failed with ineligible "
                        f"reason codes: {check_reasons}."
                    ),
                    result_data=result,
                    manifest_data=manifest,
                )
            failed_check_ids.append(check_id)

    if not failed_check_ids:
        return AttemptAssessment(
            eligible=False,
            stop_reason=RepairStopReason.INELIGIBLE_REASON_CODES,
            verdict=verdict,
            reason_codes=reason_codes,
            failed_check_ids=(),
            explanation="No failed checks identified for repair.",
            result_data=result,
            manifest_data=manifest,
        )

    return AttemptAssessment(
        eligible=True,
        stop_reason=None,
        verdict=verdict,
        reason_codes=reason_codes,
        failed_check_ids=tuple(failed_check_ids),
        explanation="Eligible deterministic test or assertion failure.",
        result_data=result,
        manifest_data=manifest,
    )


def _generate_summary_md(session: RepairSession) -> str:
    stop_str = session.stop_reason.value if session.stop_reason else "none"
    lines = [
        f"# Release Gate Repair Summary: {session.session_id}",
        "",
        f"- **Status**: `{session.state.value}`",
        f"- **Base Ref**: `{session.base_ref}` (`{session.base_commit[:8]}`)",
        f"- **Attempts**: {len(session.attempts)}",
        f"- **Stop Reason**: `{stop_str}`",
        "",
        "## Lineage",
        "",
    ]
    for attempt in session.attempts:
        checks_str = ", ".join(attempt.failed_check_ids) or "none"
        lines.append(
            f"- **{attempt.candidate_label}** (Run `{attempt.gate_run_id}`): "
            f"verdict **`{attempt.verdict}`**, failed checks: `{checks_str}`"
        )
    lines.append("")
    return "\n".join(lines)


def _evidence_matches_candidate(
    assessment: AttemptAssessment,
    *,
    base_commit: str,
    candidate_tree: str,
    patch_digest: str,
) -> bool:
    result = assessment.result_data
    return (
        result.get("base_commit") == base_commit
        and result.get("candidate_tree") == candidate_tree
        and result.get("patch_sha256") == patch_digest
    )


def _generate_lesson_md(session: RepairSession) -> str:
    lines = [
        f"# Repair Lesson Proposal: {session.session_id}",
        "",
        "The following repair attempt succeeded and passed the gate:",
        "",
    ]
    for attempt in session.attempts:
        if attempt.verdict == "PASS":
            lines.append(
                f"- Candidate `{attempt.candidate_label}` resolved previous failures."
            )
    lines.append("")
    lines.append("Consider updating local tests or playbooks to document this pattern.")
    lines.append("")
    return "\n".join(lines)


def start_repair(
    repository: Path,
    *,
    base: str = "HEAD",
    output: Path | None = None,
    session_id: str | None = None,
) -> RepairSessionOutcome:
    """Initialize a repair session, evaluate C0, and prepare approval request."""

    now = datetime.now(UTC)
    resolved_repo = repository.resolve(strict=True)
    # Run the normal gate first so its evidence-root preflight is the sole authority.
    gate_outcome = run_gate(resolved_repo, base=base, output=output)
    gate_run_dir = gate_outcome.result_path.parent
    assessment = assess_attempt(gate_run_dir)
    c0_capture = capture_candidate(resolved_repo, base=base)
    evidence_root = gate_run_dir.parent
    session_ident = session_id or _default_session_id(now)
    repair_ev = RepairEvidence.create(evidence_root, session_ident)

    if not _evidence_matches_candidate(
        assessment,
        base_commit=c0_capture.base_commit,
        candidate_tree=c0_capture.candidate_tree,
        patch_digest=c0_capture.patch_sha256,
    ):
        assessment = AttemptAssessment(
            eligible=False,
            stop_reason=RepairStopReason.SOURCE_CHANGED,
            verdict=gate_outcome.verdict.value,
            reason_codes=("SOURCE_CHANGED",),
            failed_check_ids=(),
            explanation="Source changed while the gate was evaluating C0.",
            result_data=assessment.result_data,
            manifest_data=assessment.manifest_data,
        )

    result_path = gate_run_dir / "result.json"
    manifest_path = gate_run_dir / "manifest.json"
    result_digest = sha256_file(result_path) if result_path.exists() else "0" * 64
    manifest_digest = sha256_file(manifest_path) if manifest_path.exists() else "0" * 64

    # Save original C0 patch in session dir
    (repair_ev.session_dir / "C0.patch").write_bytes(c0_capture.patch)

    c0_attempt = RepairAttempt(
        candidate_label="C0",
        gate_run_id=gate_run_dir.name,
        base_commit=c0_capture.base_commit,
        candidate_tree=c0_capture.candidate_tree,
        patch_digest=c0_capture.patch_sha256,
        result_digest=result_digest,
        manifest_digest=manifest_digest,
        verdict=gate_outcome.verdict.value,
        reason_codes=tuple(assessment.reason_codes),
        failed_check_ids=tuple(assessment.failed_check_ids),
    )

    # Check harness changes
    if has_harness_changes(c0_capture.changed_paths):
        session = RepairSession(
            version=1,
            session_id=session_ident,
            repo_path=str(resolved_repo),
            base_ref=base,
            base_commit=c0_capture.base_commit,
            approved_paths=c0_capture.changed_paths,
            attempt_cap=2,
            attempts=(c0_attempt,),
            state=RepairState.STOPPED,
            next_action="none",
            created_at=utc_timestamp(now),
            updated_at=utc_timestamp(now),
            stop_reason=RepairStopReason.HARNESS_CHANGED,
        )
        repair_ev.write_session(session)
        repair_ev.write_summary(_generate_summary_md(session))
        repair_ev.write_manifest()
        return RepairSessionOutcome(
            session_id=session_ident,
            state=session.state,
            next_action=session.next_action,
            session_dir=repair_ev.session_dir,
            session=session,
            summary_path=repair_ev.session_dir / SUMMARY_FILENAME,
        )

    if not assessment.eligible:
        session = RepairSession(
            version=1,
            session_id=session_ident,
            repo_path=str(resolved_repo),
            base_ref=base,
            base_commit=c0_capture.base_commit,
            approved_paths=c0_capture.changed_paths,
            attempt_cap=2,
            attempts=(c0_attempt,),
            state=RepairState.STOPPED,
            next_action="none",
            created_at=utc_timestamp(now),
            updated_at=utc_timestamp(now),
            stop_reason=assessment.stop_reason,
        )
        repair_ev.write_session(session)
        repair_ev.write_summary(_generate_summary_md(session))
        repair_ev.write_manifest()
        return RepairSessionOutcome(
            session_id=session_ident,
            state=session.state,
            next_action=session.next_action,
            session_dir=repair_ev.session_dir,
            session=session,
            summary_path=repair_ev.session_dir / SUMMARY_FILENAME,
        )

    # Eligible: compute playbooks and approved paths
    playbooks = load_playbooks_from_base(
        resolved_repo,
        c0_capture.base_commit,
        failed_check_ids=assessment.failed_check_ids,
    )
    approved_paths = compute_approved_paths(
        c0_capture.changed_paths,
        c0_capture.config.scope,
        extra_paths=playbooks.extra_approved_paths,
    )

    request = ApprovalRequest(
        session_id=session_ident,
        base_ref=base,
        base_commit=c0_capture.base_commit,
        failed_check_ids=assessment.failed_check_ids,
        approved_paths=approved_paths,
        attempt_cap=2,
        explanation=assessment.explanation,
    )
    repair_ev.write_approval_request(request)

    # Prepare repair workspace outside evidence root
    ws = RepairWorkspace.create(
        resolved_repo,
        base_commit=c0_capture.base_commit,
        initial_patch=c0_capture.patch,
        approved_paths=approved_paths,
        parent=None,
    )

    session = RepairSession(
        version=1,
        session_id=session_ident,
        repo_path=str(resolved_repo),
        base_ref=base,
        base_commit=c0_capture.base_commit,
        approved_paths=approved_paths,
        attempt_cap=2,
        attempts=(c0_attempt,),
        state=RepairState.AWAITING_APPROVAL,
        next_action="approve_or_cancel",
        created_at=utc_timestamp(now),
        updated_at=utc_timestamp(now),
        workspace_path=str(ws.workspace_path),
    )
    repair_ev.write_session(session)
    repair_ev.write_summary(_generate_summary_md(session))
    repair_ev.write_manifest()

    return RepairSessionOutcome(
        session_id=session_ident,
        state=session.state,
        next_action=session.next_action,
        session_dir=repair_ev.session_dir,
        session=session,
        approval_request_path=repair_ev.session_dir / APPROVAL_REQUEST_FILENAME,
        summary_path=repair_ev.session_dir / SUMMARY_FILENAME,
        workspace_path=ws.workspace_path,
    )


def approve_repair(session_dir: Path, approval_file: Path) -> RepairSessionOutcome:
    """Validate start approval and transition to repairing state."""

    resolved_session_dir = session_dir.resolve(strict=True)
    evidence_root = resolved_session_dir.parent.parent
    repair_ev = RepairEvidence.load(evidence_root, resolved_session_dir.name)
    session = repair_ev.read_session()

    if session.state is not RepairState.AWAITING_APPROVAL:
        raise ValueError(
            f"session is in state {session.state.value}, not awaiting_approval"
        )

    approval_data = json.loads(approval_file.read_text(encoding="utf-8"))
    if approval_data.get("session_id") != session.session_id:
        raise ValueError("approval session_id mismatch")

    now = datetime.now(UTC)
    updated_session = RepairSession(
        version=session.version,
        session_id=session.session_id,
        repo_path=session.repo_path,
        base_ref=session.base_ref,
        base_commit=session.base_commit,
        approved_paths=session.approved_paths,
        attempt_cap=session.attempt_cap,
        attempts=session.attempts,
        state=RepairState.REPAIRING,
        next_action="edit_workspace",
        created_at=session.created_at,
        updated_at=utc_timestamp(now),
        workspace_path=session.workspace_path,
    )
    repair_ev.write_session(updated_session)
    repair_ev.write_manifest()

    return RepairSessionOutcome(
        session_id=updated_session.session_id,
        state=updated_session.state,
        next_action=updated_session.next_action,
        session_dir=repair_ev.session_dir,
        session=updated_session,
    )


def _get_workspace_path(session: RepairSession, session_dir: Path) -> Path:
    if session.workspace_path:
        path = Path(session.workspace_path)
        if path.exists() and (path / ".git").exists():
            return path

    # Reconstruct workspace if missing
    latest_patch_path = session_dir / f"{session.attempts[-1].candidate_label}.patch"
    if not latest_patch_path.exists():
        latest_patch_path = session_dir / "C0.patch"
    patch_bytes = latest_patch_path.read_bytes()

    ws = RepairWorkspace.create(
        Path(session.repo_path),
        base_commit=session.base_commit,
        initial_patch=patch_bytes,
        approved_paths=session.approved_paths,
        parent=None,
    )
    return ws.workspace_path


def request_repair(session_dir: Path) -> dict[str, Any]:
    """Retrieve instructions, edit boundary, and workspace path for current attempt."""

    resolved_session_dir = session_dir.resolve(strict=True)
    evidence_root = resolved_session_dir.parent.parent
    repair_ev = RepairEvidence.load(evidence_root, resolved_session_dir.name)
    session = repair_ev.read_session()

    ws_path = _get_workspace_path(session, resolved_session_dir)
    last_attempt = session.attempts[-1]

    playbooks = load_playbooks_from_base(
        Path(session.repo_path),
        session.base_commit,
        failed_check_ids=last_attempt.failed_check_ids,
    )
    guidance = playbooks.guidance_for_checks(last_attempt.failed_check_ids)

    return {
        "session_id": session.session_id,
        "state": session.state.value,
        "next_action": session.next_action,
        "workspace_path": str(ws_path),
        "approved_paths": list(session.approved_paths),
        "failed_check_ids": list(last_attempt.failed_check_ids),
        "attempt_number": len(session.attempts),
        "attempt_cap": session.attempt_cap,
        "guidance": guidance,
    }


def evaluate_repair(session_dir: Path) -> RepairSessionOutcome:
    """Export candidate, execute release-gate run, and record lineage."""

    resolved_session_dir = session_dir.resolve(strict=True)
    evidence_root = resolved_session_dir.parent.parent
    repair_ev = RepairEvidence.load(evidence_root, resolved_session_dir.name)
    session = repair_ev.read_session()

    if session.state is not RepairState.REPAIRING:
        raise ValueError(f"session is in state {session.state.value}, not repairing")

    ws_path = _get_workspace_path(session, resolved_session_dir)
    ws_temp_root = ws_path.parent
    git_bin = _git_binary()
    env = _base_git_environment()
    base_tree = (
        subprocess.run(
            [
                git_bin,
                "-C",
                str(ws_path),
                "rev-parse",
                f"{session.base_commit}^{{tree}}",
            ],
            check=True,
            env=env,
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )
    ws = RepairWorkspace(
        repository_path=Path(session.repo_path),
        base_commit=session.base_commit,
        base_tree=base_tree,
        approved_paths=session.approved_paths,
        temp_root=ws_temp_root,
        workspace_path=ws_path,
    )
    for attempt in session.attempts:
        ws.record_attempt(attempt.candidate_tree, attempt.patch_digest)

    now = datetime.now(UTC)
    candidate_label = f"C{len(session.attempts)}"

    try:
        exported = ws.export_candidate()
    except RepairWorkspaceError as error:
        workspace_stop_reason = (
            RepairStopReason.REPEATED_CANDIDATE
            if "repeated" in str(error)
            else RepairStopReason.INELIGIBLE_REASON_CODES
        )
        stopped_session = RepairSession(
            version=session.version,
            session_id=session.session_id,
            repo_path=session.repo_path,
            base_ref=session.base_ref,
            base_commit=session.base_commit,
            approved_paths=session.approved_paths,
            attempt_cap=session.attempt_cap,
            attempts=session.attempts,
            state=RepairState.STOPPED,
            next_action="none",
            created_at=session.created_at,
            updated_at=utc_timestamp(now),
            stop_reason=workspace_stop_reason,
            workspace_path=session.workspace_path,
        )
        repair_ev.write_session(stopped_session)
        repair_ev.write_summary(_generate_summary_md(stopped_session))
        repair_ev.write_manifest()
        return RepairSessionOutcome(
            session_id=session.session_id,
            state=stopped_session.state,
            next_action=stopped_session.next_action,
            session_dir=repair_ev.session_dir,
            session=stopped_session,
            summary_path=repair_ev.session_dir / SUMMARY_FILENAME,
        )

    # Save candidate patch
    (repair_ev.session_dir / f"{candidate_label}.patch").write_bytes(exported.patch)

    # Run release-gate on the candidate workspace
    gate_outcome = run_gate(
        ws_path,
        base=session.base_commit,
        output=evidence_root,
        allow_empty_candidate=True,
    )
    gate_run_dir = gate_outcome.result_path.parent
    assessment = assess_attempt(gate_run_dir)
    evidence_matches = _evidence_matches_candidate(
        assessment,
        base_commit=session.base_commit,
        candidate_tree=exported.candidate_tree,
        patch_digest=exported.patch_sha256,
    )
    if not evidence_matches:
        assessment = AttemptAssessment(
            eligible=False,
            stop_reason=RepairStopReason.INELIGIBLE_REASON_CODES,
            verdict=gate_outcome.verdict.value,
            reason_codes=("WORKSPACE_CHANGED",),
            failed_check_ids=(),
            explanation=(
                "Workspace changed while the gate was evaluating the candidate."
            ),
            result_data=assessment.result_data,
            manifest_data=assessment.manifest_data,
        )

    result_path = gate_run_dir / "result.json"
    manifest_path = gate_run_dir / "manifest.json"
    result_digest = sha256_file(result_path) if result_path.exists() else "0" * 64
    manifest_digest = sha256_file(manifest_path) if manifest_path.exists() else "0" * 64

    new_attempt = RepairAttempt(
        candidate_label=candidate_label,
        gate_run_id=gate_run_dir.name,
        base_commit=session.base_commit,
        candidate_tree=exported.candidate_tree,
        patch_digest=exported.patch_sha256,
        result_digest=result_digest,
        manifest_digest=manifest_digest,
        verdict=gate_outcome.verdict.value,
        reason_codes=tuple(assessment.reason_codes),
        failed_check_ids=tuple(assessment.failed_check_ids),
    )

    all_attempts = (*session.attempts, new_attempt)
    repairs_performed = len(all_attempts) - 1
    eval_stop_reason: RepairStopReason | None = None

    if gate_outcome.verdict is Verdict.PASS and evidence_matches:
        new_state = RepairState.AWAITING_FINAL_APPROVAL
        next_action = "final_approval_and_apply"
        eval_stop_reason = None
        repair_ev.write_lesson_proposal(_generate_lesson_md(session))
    elif repairs_performed >= session.attempt_cap:
        new_state = RepairState.STOPPED
        eval_stop_reason = RepairStopReason.ATTEMPT_BUDGET_EXHAUSTED
        next_action = "none"
    elif assessment.eligible:
        new_state = RepairState.REPAIRING
        next_action = "edit_workspace"
        eval_stop_reason = None
    else:
        new_state = RepairState.STOPPED
        eval_stop_reason = assessment.stop_reason or RepairStopReason.INELIGIBLE_VERDICT
        next_action = "none"

    updated_session = RepairSession(
        version=session.version,
        session_id=session.session_id,
        repo_path=session.repo_path,
        base_ref=session.base_ref,
        base_commit=session.base_commit,
        approved_paths=session.approved_paths,
        attempt_cap=session.attempt_cap,
        attempts=all_attempts,
        state=new_state,
        next_action=next_action,
        stop_reason=eval_stop_reason,
        created_at=session.created_at,
        updated_at=utc_timestamp(now),
        workspace_path=session.workspace_path,
    )

    repair_ev.write_session(updated_session)
    repair_ev.write_summary(_generate_summary_md(updated_session))
    repair_ev.write_manifest()

    return RepairSessionOutcome(
        session_id=session.session_id,
        state=updated_session.state,
        next_action=updated_session.next_action,
        session_dir=repair_ev.session_dir,
        session=updated_session,
        summary_path=repair_ev.session_dir / SUMMARY_FILENAME,
    )


def finalize_repair(session_dir: Path) -> RepairSessionOutcome:
    """Refresh session summary and manifest."""

    resolved_session_dir = session_dir.resolve(strict=True)
    evidence_root = resolved_session_dir.parent.parent
    repair_ev = RepairEvidence.load(evidence_root, resolved_session_dir.name)
    session = repair_ev.read_session()

    repair_ev.write_summary(_generate_summary_md(session))
    repair_ev.write_manifest()

    return RepairSessionOutcome(
        session_id=session.session_id,
        state=session.state,
        next_action=session.next_action,
        session_dir=repair_ev.session_dir,
        session=session,
        summary_path=repair_ev.session_dir / SUMMARY_FILENAME,
    )


def apply_repair(session_dir: Path, approval_file: Path) -> RepairSessionOutcome:
    """Transactionally apply the passing repaired candidate to the source worktree."""

    resolved_session_dir = session_dir.resolve(strict=True)
    evidence_root = resolved_session_dir.parent.parent
    repair_ev = RepairEvidence.load(evidence_root, resolved_session_dir.name)
    session = repair_ev.read_session()

    if session.state is not RepairState.AWAITING_FINAL_APPROVAL:
        raise ValueError(
            f"session is in state {session.state.value}, not awaiting_final_approval"
        )

    approval_raw = json.loads(approval_file.read_text(encoding="utf-8"))
    final_approval = FinalApproval.from_dict(approval_raw)
    if final_approval.session_id != session.session_id:
        raise ValueError("final approval session_id mismatch")

    passing_attempt = session.attempts[-1]
    if passing_attempt.verdict != "PASS":
        raise ValueError("no passing candidate found in repair attempts")

    final_patch_path = (
        repair_ev.session_dir / f"{passing_attempt.candidate_label}.patch"
    )
    if not final_patch_path.exists():
        raise FileNotFoundError(f"patch not found: {final_patch_path}")
    final_patch = final_patch_path.read_bytes()
    if sha256_bytes(final_patch) != passing_attempt.patch_digest:
        raise ValueError("persisted final patch digest mismatch")
    original_patch = (repair_ev.session_dir / "C0.patch").read_bytes()

    repair_ev.write_final_approval(final_approval)

    apply_candidate_to_source(
        Path(session.repo_path),
        base_commit=session.base_commit,
        c0_attempt=session.attempts[0],
        passing_attempt=passing_attempt,
        original_patch=original_patch,
        final_patch=final_patch,
        final_approval=final_approval,
    )

    now = datetime.now(UTC)
    updated_session = RepairSession(
        version=session.version,
        session_id=session.session_id,
        repo_path=session.repo_path,
        base_ref=session.base_ref,
        base_commit=session.base_commit,
        approved_paths=session.approved_paths,
        attempt_cap=session.attempt_cap,
        attempts=session.attempts,
        state=RepairState.APPLIED,
        next_action="none",
        created_at=session.created_at,
        updated_at=utc_timestamp(now),
        workspace_path=session.workspace_path,
    )
    repair_ev.write_session(updated_session)
    repair_ev.write_summary(_generate_summary_md(updated_session))
    repair_ev.write_manifest()

    return RepairSessionOutcome(
        session_id=session.session_id,
        state=updated_session.state,
        next_action=updated_session.next_action,
        session_dir=repair_ev.session_dir,
        session=updated_session,
        summary_path=repair_ev.session_dir / SUMMARY_FILENAME,
    )


def cancel_repair(session_dir: Path) -> RepairSessionOutcome:
    """Cancel the active repair session."""

    resolved_session_dir = session_dir.resolve(strict=True)
    evidence_root = resolved_session_dir.parent.parent
    repair_ev = RepairEvidence.load(evidence_root, resolved_session_dir.name)
    session = repair_ev.read_session()
    if session.state not in {
        RepairState.AWAITING_APPROVAL,
        RepairState.REPAIRING,
        RepairState.AWAITING_FINAL_APPROVAL,
    }:
        raise ValueError(f"session is in terminal state {session.state.value}")

    now = datetime.now(UTC)
    stopped_session = RepairSession(
        version=session.version,
        session_id=session.session_id,
        repo_path=session.repo_path,
        base_ref=session.base_ref,
        base_commit=session.base_commit,
        approved_paths=session.approved_paths,
        attempt_cap=session.attempt_cap,
        attempts=session.attempts,
        state=RepairState.CANCELLED,
        next_action="none",
        stop_reason=RepairStopReason.CANCELLED_BY_USER,
        created_at=session.created_at,
        updated_at=utc_timestamp(now),
        workspace_path=session.workspace_path,
    )
    repair_ev.write_session(stopped_session)
    repair_ev.write_summary(_generate_summary_md(stopped_session))
    repair_ev.write_manifest()

    return RepairSessionOutcome(
        session_id=session.session_id,
        state=stopped_session.state,
        next_action=stopped_session.next_action,
        session_dir=repair_ev.session_dir,
        session=stopped_session,
        summary_path=repair_ev.session_dir / SUMMARY_FILENAME,
    )
