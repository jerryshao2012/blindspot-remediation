"""Data models, enums, and digest helpers for Release Gate repair sessions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class RepairState(StrEnum):
    """Lifecycle states of a deterministic repair session."""

    AWAITING_APPROVAL = "awaiting_approval"
    REPAIRING = "repairing"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"
    STOPPED = "stopped"
    CANCELLED = "cancelled"
    APPLIED = "applied"


class RepairStopReason(StrEnum):
    """Reason why automatic repair stopped without applying changes."""

    ALREADY_PASS = "already_pass"
    INELIGIBLE_VERDICT = "ineligible_verdict"
    INELIGIBLE_REASON_CODES = "ineligible_reason_codes"
    POLICY_CHANGED = "policy_changed"
    LAUNCHER_CHANGED = "launcher_changed"
    HARNESS_CHANGED = "harness_changed"
    INVALID_EVIDENCE = "invalid_evidence"
    ATTEMPT_BUDGET_EXHAUSTED = "attempt_budget_exhausted"
    REPEATED_CANDIDATE = "repeated_candidate"
    SOURCE_CHANGED = "source_changed"
    ROLLBACK_FAILED = "rollback_failed"
    CANCELLED_BY_USER = "cancelled_by_user"


def sha256_bytes(data: bytes) -> str:
    """Compute hex SHA-256 digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Compute hex SHA-256 digest of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class RepairAttempt:
    """Record of a single gate execution within a repair lineage."""

    candidate_label: str
    gate_run_id: str
    base_commit: str
    candidate_tree: str
    patch_digest: str
    result_digest: str
    manifest_digest: str
    verdict: str
    reason_codes: tuple[str, ...]
    failed_check_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_label": self.candidate_label,
            "gate_run_id": self.gate_run_id,
            "base_commit": self.base_commit,
            "candidate_tree": self.candidate_tree,
            "patch_digest": self.patch_digest,
            "result_digest": self.result_digest,
            "manifest_digest": self.manifest_digest,
            "verdict": self.verdict,
            "reason_codes": list(self.reason_codes),
            "failed_check_ids": list(self.failed_check_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepairAttempt:
        return cls(
            candidate_label=str(data["candidate_label"]),
            gate_run_id=str(data["gate_run_id"]),
            base_commit=str(data["base_commit"]),
            candidate_tree=str(data["candidate_tree"]),
            patch_digest=str(data["patch_digest"]),
            result_digest=str(data["result_digest"]),
            manifest_digest=str(data["manifest_digest"]),
            verdict=str(data["verdict"]),
            reason_codes=tuple(str(item) for item in data.get("reason_codes", ())),
            failed_check_ids=tuple(
                str(item) for item in data.get("failed_check_ids", ())
            ),
        )


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """Document presented to the user before starting repair attempts."""

    session_id: str
    base_ref: str
    base_commit: str
    failed_check_ids: tuple[str, ...]
    approved_paths: tuple[str, ...]
    attempt_cap: int
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "base_ref": self.base_ref,
            "base_commit": self.base_commit,
            "failed_check_ids": list(self.failed_check_ids),
            "approved_paths": list(self.approved_paths),
            "attempt_cap": self.attempt_cap,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRequest:
        return cls(
            session_id=str(data["session_id"]),
            base_ref=str(data["base_ref"]),
            base_commit=str(data["base_commit"]),
            failed_check_ids=tuple(
                str(item) for item in data.get("failed_check_ids", ())
            ),
            approved_paths=tuple(str(item) for item in data.get("approved_paths", ())),
            attempt_cap=int(data["attempt_cap"]),
            explanation=str(data.get("explanation", "")),
        )


@dataclass(frozen=True, slots=True)
class FinalApproval:
    """Document required before applying the final repaired patch to the source."""

    session_id: str
    final_candidate_tree: str
    final_patch_digest: str
    approved_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "final_candidate_tree": self.final_candidate_tree,
            "final_patch_digest": self.final_patch_digest,
            "approved_at": self.approved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FinalApproval:
        return cls(
            session_id=str(data["session_id"]),
            final_candidate_tree=str(data["final_candidate_tree"]),
            final_patch_digest=str(data["final_patch_digest"]),
            approved_at=str(data["approved_at"]),
        )


@dataclass(frozen=True, slots=True)
class RepairSession:
    """Chained state and lineage of a repair session."""

    version: int
    session_id: str
    repo_path: str
    base_ref: str
    base_commit: str
    approved_paths: tuple[str, ...]
    attempt_cap: int
    attempts: tuple[RepairAttempt, ...]
    state: RepairState
    next_action: str
    created_at: str
    updated_at: str
    stop_reason: RepairStopReason | None = None
    workspace_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "session_id": self.session_id,
            "repo_path": self.repo_path,
            "base_ref": self.base_ref,
            "base_commit": self.base_commit,
            "approved_paths": list(self.approved_paths),
            "attempt_cap": self.attempt_cap,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "state": self.state.value,
            "next_action": self.next_action,
            "stop_reason": self.stop_reason.value if self.stop_reason else None,
            "workspace_path": self.workspace_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepairSession:
        stop_reason_raw = data.get("stop_reason")
        stop_reason = (
            RepairStopReason(stop_reason_raw) if stop_reason_raw is not None else None
        )
        return cls(
            version=int(data["version"]),
            session_id=str(data["session_id"]),
            repo_path=str(data["repo_path"]),
            base_ref=str(data["base_ref"]),
            base_commit=str(data["base_commit"]),
            approved_paths=tuple(str(item) for item in data.get("approved_paths", ())),
            attempt_cap=int(data["attempt_cap"]),
            attempts=tuple(
                RepairAttempt.from_dict(attempt) for attempt in data.get("attempts", ())
            ),
            state=RepairState(data["state"]),
            next_action=str(data["next_action"]),
            stop_reason=stop_reason,
            workspace_path=str(data["workspace_path"])
            if data.get("workspace_path") is not None
            else None,
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
        )
