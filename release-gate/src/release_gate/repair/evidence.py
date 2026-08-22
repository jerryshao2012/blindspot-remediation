"""Atomic evidence persistence for repair sessions under _repairs/<session-id>/."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from release_gate import __version__
from release_gate.repair.models import (
    ApprovalRequest,
    FinalApproval,
    RepairSession,
    sha256_bytes,
)
from release_gate.timestamps import utc_timestamp

REPAIRS_NAMESPACE = "_repairs"
SESSION_FILENAME = "repair-session-v1.json"
APPROVAL_REQUEST_FILENAME = "approval-request.json"
FINAL_APPROVAL_FILENAME = "final-approval.json"
SUMMARY_FILENAME = "repair-summary.md"
LESSON_PROPOSAL_FILENAME = "lesson-proposal.md"
MANIFEST_FILENAME = "repair-manifest.json"
_SESSION_ID = re.compile(r"^rep-[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?$")


def _validate_session_id(session_id: str) -> None:
    if not _SESSION_ID.fullmatch(session_id):
        raise ValueError("repair session ID must be a portable rep- identifier")


class RepairEvidence:
    """Manager for session artifacts in `<evidence-root>/_repairs/<session-id>/`."""

    def __init__(self, session_dir: Path, session_id: str) -> None:
        self.session_dir = session_dir
        self.session_id = session_id

    @classmethod
    def create(cls, evidence_root: Path, session_id: str) -> RepairEvidence:
        _validate_session_id(session_id)
        repairs_dir = evidence_root / REPAIRS_NAMESPACE
        session_dir = (repairs_dir / session_id).resolve()
        if session_dir.parent != repairs_dir.resolve():
            raise ValueError("repair session path escapes the repairs namespace")
        session_dir.mkdir(parents=True, exist_ok=True)
        return cls(session_dir=session_dir, session_id=session_id)

    @classmethod
    def load(cls, evidence_root: Path, session_id: str) -> RepairEvidence:
        _validate_session_id(session_id)
        repairs_dir = evidence_root / REPAIRS_NAMESPACE
        session_dir = (repairs_dir / session_id).resolve()
        if session_dir.parent != repairs_dir.resolve():
            raise ValueError("repair session path escapes the repairs namespace")
        if not session_dir.exists():
            raise FileNotFoundError(
                f"repair session directory not found: {session_dir}"
            )
        return cls(session_dir=session_dir, session_id=session_id)

    def _atomic_write(self, filename: str, data: bytes) -> Path:
        target = self.session_dir / filename
        temp_fd, temp_path = tempfile.mkstemp(
            prefix=f".tmp_{filename}_", dir=str(self.session_dir)
        )
        try:
            with os.fdopen(temp_fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, target)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
        return target

    def write_session(self, session: RepairSession) -> None:
        data = (
            json.dumps(
                session.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        self._atomic_write(SESSION_FILENAME, data)

    def read_session(self) -> RepairSession:
        path = self.session_dir / SESSION_FILENAME
        if not path.exists():
            raise FileNotFoundError(f"repair session file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return RepairSession.from_dict(data)

    def write_approval_request(self, request: ApprovalRequest) -> None:
        data = (
            json.dumps(
                request.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        self._atomic_write(APPROVAL_REQUEST_FILENAME, data)

    def read_approval_request(self) -> ApprovalRequest | None:
        path = self.session_dir / APPROVAL_REQUEST_FILENAME
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ApprovalRequest.from_dict(data)

    def write_final_approval(self, approval: FinalApproval) -> None:
        data = (
            json.dumps(
                approval.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        self._atomic_write(FINAL_APPROVAL_FILENAME, data)

    def read_final_approval(self) -> FinalApproval | None:
        path = self.session_dir / FINAL_APPROVAL_FILENAME
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return FinalApproval.from_dict(data)

    def write_summary(self, summary_md: str) -> None:
        self._atomic_write(SUMMARY_FILENAME, summary_md.encode("utf-8"))

    def read_summary(self) -> str | None:
        path = self.session_dir / SUMMARY_FILENAME
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write_lesson_proposal(self, proposal_md: str) -> None:
        self._atomic_write(LESSON_PROPOSAL_FILENAME, proposal_md.encode("utf-8"))

    def read_lesson_proposal(self) -> str | None:
        path = self.session_dir / LESSON_PROPOSAL_FILENAME
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write_manifest(self) -> dict[str, Any]:
        artifacts: list[dict[str, Any]] = []
        for file_path in sorted(self.session_dir.iterdir()):
            if not file_path.is_file() or file_path.name == MANIFEST_FILENAME:
                continue
            if file_path.name.startswith(".tmp_"):
                continue
            data = file_path.read_bytes()
            media_type = "application/json"
            if file_path.name.endswith(".md"):
                media_type = "text/markdown"
            elif file_path.name.endswith(".patch"):
                media_type = "text/x-diff"
            artifacts.append(
                {
                    "path": file_path.name,
                    "media_type": media_type,
                    "size_bytes": len(data),
                    "sha256": sha256_bytes(data),
                }
            )

        manifest = {
            "version": 1,
            "session_id": self.session_id,
            "created_at": utc_timestamp(datetime.now(UTC)),
            "engine_version": __version__,
            "artifacts": artifacts,
        }
        manifest_bytes = (
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        self._atomic_write(MANIFEST_FILENAME, manifest_bytes)
        return manifest

    def read_manifest(self) -> dict[str, Any] | None:
        path = self.session_dir / MANIFEST_FILENAME
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
