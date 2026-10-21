"""Data models, enums, and digest helpers for Release Gate repair sessions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from pydantic import TypeAdapter


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


class _RepairModel:
    def to_dict(self) -> dict[str, Any]:
        return TypeAdapter(type(self)).dump_python(self, mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return TypeAdapter(cls).validate_python(data)


@dataclass(frozen=True, slots=True)
class RepairAttempt(_RepairModel):
    """Record of a single gate execution within a repair lineage."""

    candidate_label: str
    gate_run_id: str
    base_commit: str
    candidate_tree: str
    patch_digest: str
    result_digest: str
    manifest_digest: str
    verdict: str
    reason_codes: tuple[str, ...] = ()
    failed_check_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ApprovalRequest(_RepairModel):
    """Document presented to the user before starting repair attempts."""

    session_id: str
    base_ref: str
    base_commit: str
    failed_check_ids: tuple[str, ...] = ()
    approved_paths: tuple[str, ...] = ()
    attempt_cap: int = 2
    explanation: str = ""


@dataclass(frozen=True, slots=True)
class FinalApproval(_RepairModel):
    """Document required before applying the final repaired patch to the source."""

    session_id: str
    final_candidate_tree: str
    final_patch_digest: str
    approved_at: str


@dataclass(frozen=True, slots=True)
class RepairSession(_RepairModel):
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
