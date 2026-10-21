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
        repairs_dir.mkdir(parents=True, exist_ok=True)
        try:
            session_dir.mkdir()
        except FileExistsError as error:
            raise ValueError(f"repair session already exists: {session_id}") from error
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
        self.verify_manifest()
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

    def verify_manifest(self) -> None:
        """Reject incomplete or changed session evidence before consuming state."""
        try:
            manifest_path = self.session_dir / MANIFEST_FILENAME
            if manifest_path.is_symlink():
                raise ValueError("unsafe manifest")
            manifest = self.read_manifest()
            if (
                manifest is None
                or manifest.get("version") != 1
                or manifest.get("session_id") != self.session_id
                or not isinstance(manifest.get("artifacts"), list)
            ):
                raise ValueError("invalid manifest")
            records = {}
            for record in manifest["artifacts"]:
                name = record["path"]
                if (
                    not isinstance(name, str)
                    or not name
                    or name in {".", "..", MANIFEST_FILENAME}
                    or "/" in name
                    or "\\" in name
                    or name in records
                ):
                    raise ValueError("invalid inventory path")
                records[name] = record
            actual = {
                p.name: p for p in self.session_dir.iterdir()
                if p.name != MANIFEST_FILENAME
            }
            if records.keys() != actual.keys():
                raise ValueError("inventory mismatch")
            for name, path in actual.items():
                if path.is_symlink() or not path.is_file():
                    raise ValueError("unsafe artifact")
                data = path.read_bytes()
                if (
                    len(data) != records[name]["size_bytes"]
                    or sha256_bytes(data) != records[name]["sha256"]
                ):
                    raise ValueError("artifact changed")
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise ValueError("invalid repair evidence: " + str(error)) from error

    def read_manifest(self) -> dict[str, Any] | None:
        path = self.session_dir / MANIFEST_FILENAME
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
