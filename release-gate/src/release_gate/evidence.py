"""Atomic, tamper-evident Release Gate evidence packages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import unicodedata
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from release_gate.timestamps import parse_timestamp

FINALIZATION_RESERVE = 7_340_032
RESULT_LIMIT = 2 * 1024 * 1024
MANIFEST_LIMIT = 4 * 1024 * 1024
TRACE_LIMIT = 1024 * 1024
MAX_TOTAL = 200 * 1024 * 1024
_REPLACE_RETRY_DELAY = 0.05
_REPLACE_RETRIES = 3
_RUN_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?$")
_DOS_DEVICE = re.compile(r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.I)
_ILLEGAL_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_MEDIA_DEFAULTS = {
    ".json": "application/json",
    ".patch": "text/x-diff",
    ".log": "application/octet-stream",
    ".xml": "application/xml",
}


class EvidenceError(ValueError):
    """Evidence cannot be created or verified safely."""


class EvidenceBudgetExhausted(EvidenceError):
    """Optional runtime evidence no longer fits the configured allowance."""


def ensure_preflight_feasible(total_bytes: int, patch: bytes, config: bytes) -> int:
    """Return optional allowance after proving the fixed finalization reserve."""

    if total_bytes > MAX_TOTAL:
        raise EvidenceError("total evidence budget exceeds the 200 MiB ceiling")
    needed = len(patch) + len(config) + FINALIZATION_RESERVE
    if needed > total_bytes:
        raise EvidenceError("candidate and configuration exceed finalization reserve")
    return total_bytes - len(patch) - len(config)


class EvidenceRun:
    """Append-only run directory with atomic per-file writes."""

    def __init__(self, path: Path, total_bytes: int) -> None:
        self.path = path
        self.total_bytes = total_bytes
        self._artifacts: dict[str, dict[str, Any]] = {}
        self._retained_bytes = 0
        self._complete = False

    @classmethod
    def create(
        cls,
        root: Path,
        run_id: str,
        *,
        total_bytes: int,
        patch: bytes,
        effective_config: bytes,
    ) -> EvidenceRun:
        _validate_run_id(run_id)
        ensure_preflight_feasible(total_bytes, patch, effective_config)
        root.mkdir(parents=True, exist_ok=True)
        for sibling in root.iterdir():
            if sibling.name.casefold() == run_id.casefold():
                raise EvidenceError(f"run ID collides with existing {sibling.name!r}")
        path = root / run_id
        try:
            path.mkdir(mode=0o700)
        except FileExistsError as error:
            raise EvidenceError(f"run ID already exists: {run_id}") from error
        run = cls(path, total_bytes)
        run._atomic_write(".incomplete", b"")
        run.write_artifact("candidate.patch", patch, "text/x-diff")
        run.write_artifact(
            "effective-config.json", effective_config, "application/json"
        )
        return run

    def write_artifact(
        self,
        relative_path: str,
        data: bytes,
        media_type: str | None = None,
        *,
        truncated: bool = False,
        original_size_bytes: int | None = None,
        full_sha256: str | None = None,
    ) -> Path:
        return self._write_artifact(
            relative_path,
            data,
            media_type,
            truncated=truncated,
            original_size_bytes=original_size_bytes,
            full_sha256=full_sha256,
            preserve_finalization_reserve=True,
        )

    def _write_artifact(
        self,
        relative_path: str,
        data: bytes,
        media_type: str | None,
        *,
        truncated: bool = False,
        original_size_bytes: int | None = None,
        full_sha256: str | None = None,
        preserve_finalization_reserve: bool,
    ) -> Path:
        if self._complete:
            raise EvidenceError("completed evidence is append-only")
        _validate_artifact_path(relative_path)
        key = unicodedata.normalize("NFC", relative_path).casefold()
        if any(path.casefold() == key for path in self._artifacts):
            raise EvidenceError(f"artifact path collides: {relative_path}")
        reserve = FINALIZATION_RESERVE if preserve_finalization_reserve else 0
        if self._retained_bytes + len(data) + reserve > self.total_bytes:
            raise EvidenceBudgetExhausted("evidence budget exhausted")
        if truncated and (original_size_bytes is None or full_sha256 is None):
            raise EvidenceError("truncated artifacts require full-stream facts")
        self._atomic_write(relative_path, data)
        record: dict[str, Any] = {
            "path": relative_path,
            "media_type": media_type
            or _MEDIA_DEFAULTS.get(
                Path(relative_path).suffix, "application/octet-stream"
            ),
            "size_bytes": len(data),
            "sha256": _digest(data),
            "truncated": truncated,
        }
        if truncated:
            assert original_size_bytes is not None
            assert full_sha256 is not None
            record.update(
                original_size_bytes=original_size_bytes, full_sha256=full_sha256
            )
        self._artifacts[relative_path] = record
        self._retained_bytes += len(data)
        return self.path / relative_path

    def finalize(
        self,
        result: dict[str, Any],
        manifest: dict[str, Any],
        trace: bytes,
    ) -> Path:
        if len(trace) > TRACE_LIMIT:
            raise EvidenceError("trace.json exceeds 1 MiB")
        self._write_artifact(
            "trace.json",
            trace,
            "application/json",
            preserve_finalization_reserve=False,
        )
        result_bytes = _canonical_json(result)
        if len(result_bytes) > RESULT_LIMIT:
            raise EvidenceError("result.json exceeds 2 MiB")
        _validate_document("result-v1.schema.json", result)
        self._write_artifact(
            "result.json",
            result_bytes,
            "application/json",
            preserve_finalization_reserve=False,
        )
        completed_manifest = {**manifest, "artifacts": list(self._artifacts.values())}
        _validate_document("manifest-v1.schema.json", completed_manifest)
        _validate_timestamps(completed_manifest)
        manifest_bytes = _canonical_json(completed_manifest)
        if len(manifest_bytes) > MANIFEST_LIMIT:
            raise EvidenceError("manifest.json exceeds 4 MiB")
        projected = self._retained_bytes + len(manifest_bytes)
        if projected > self.total_bytes:
            raise EvidenceError("completed evidence exceeds total budget")
        self._atomic_write("manifest.json", manifest_bytes)
        (self.path / ".incomplete").unlink(missing_ok=True)
        self._complete = True
        return self.path

    def _atomic_write(self, relative_path: str, data: bytes) -> None:
        target = self.path / PurePosixPath(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".release-gate-", dir=target.parent
        )
        try:
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            for attempt in range(_REPLACE_RETRIES):
                try:
                    os.replace(temporary, target)
                    break
                except PermissionError as error:
                    final_attempt = attempt == _REPLACE_RETRIES - 1
                    if getattr(error, "winerror", None) != 32 or final_attempt:
                        raise
                    time.sleep(_REPLACE_RETRY_DELAY)
        finally:
            try:
                os.unlink(temporary)
            except (FileNotFoundError, PermissionError):
                pass


def verify_run(path: Path) -> None:
    """Verify schema, timestamp profile, inventory completeness, size, and hashes."""

    try:
        manifest = json.loads((path / "manifest.json").read_bytes())
        result = json.loads((path / "result.json").read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError("evidence JSON is missing or malformed") from error
    _validate_document("result-v1.schema.json", result)
    _validate_document("manifest-v1.schema.json", manifest)
    _validate_timestamps(result)
    _validate_timestamps(manifest)
    actual: dict[str, Path] = {}
    for candidate in path.rglob("*"):
        if candidate.is_dir():
            continue
        relative = candidate.relative_to(path).as_posix()
        if relative.casefold() == "manifest.json":
            continue
        if relative == ".incomplete":
            raise EvidenceError("completed evidence retains .incomplete")
        _validate_artifact_path(relative)
        key = unicodedata.normalize("NFC", relative).casefold()
        if key in actual:
            raise EvidenceError("artifact path alias detected")
        actual[key] = candidate
    records: dict[str, dict[str, Any]] = {}
    for record in manifest["artifacts"]:
        relative = record["path"]
        _validate_artifact_path(relative)
        key = unicodedata.normalize("NFC", relative).casefold()
        if key in records:
            raise EvidenceError("duplicate artifact inventory path")
        records[key] = record
    if actual.keys() != records.keys():
        raise EvidenceError("artifact inventory has missing or extra paths")
    for key, candidate in actual.items():
        data = candidate.read_bytes()
        record = records[key]
        if len(data) != record["size_bytes"]:
            raise EvidenceError(f"artifact size changed: {record['path']}")
        if _digest(data) != record["sha256"]:
            raise EvidenceError(f"artifact digest changed: {record['path']}")


def _validate_run_id(value: str) -> None:
    if not _RUN_ID.fullmatch(value) or value.endswith(".") or _DOS_DEVICE.match(value):
        raise EvidenceError(f"invalid portable run ID: {value!r}")


def _validate_artifact_path(value: str) -> None:
    if not value or len(value) > 1024 or "\\" in value:
        raise EvidenceError(f"invalid artifact path: {value!r}")
    pure = PurePosixPath(value)
    parts = value.split("/")
    if (
        pure.is_absolute()
        or len(parts) > 32
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise EvidenceError(f"invalid artifact path: {value!r}")
    for part in parts:
        if (
            len(part) > 128
            or part != unicodedata.normalize("NFC", part)
            or _ILLEGAL_COMPONENT.search(part)
            or part.endswith((" ", "."))
            or _DOS_DEVICE.match(part)
        ):
            raise EvidenceError(f"invalid artifact component: {part!r}")
    if unicodedata.normalize("NFC", value).casefold() == "manifest.json":
        raise EvidenceError("manifest path is reserved")


def _validate_document(schema_name: str, document: dict[str, Any]) -> None:
    schema_path = files("release_gate.schemas").joinpath(schema_name)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if errors:
        raise EvidenceError(f"{schema_name} validation failed: {errors[0].message}")


def _validate_timestamps(document: dict[str, Any]) -> None:
    for key in ("created_at", "started_at", "finished_at"):
        if key in document:
            parse_timestamp(document[key])
    for execution in document.get("executions", []):
        parse_timestamp(execution["started_at"])
        parse_timestamp(execution["finished_at"])


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
