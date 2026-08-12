"""
Artifact loading and local immutable artifact storage.

The POC uses local ``file://`` artifact references. The implementation is
separated behind small classes so Azure Blob Storage can later be added without
changing ChangeExecutionService.

Artifact integrity is always verified through SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from ai_engineering_contracts import ArtifactKind, ArtifactReference

from .errors import (
    ArtifactError,
    ArtifactIntegrityError,
    UnsupportedArtifactLocationError,
)


def sha256_bytes(content: bytes) -> str:
    """Return the lowercase SHA-256 digest of bytes."""
    return hashlib.sha256(content).hexdigest()


class LocalArtifactLoader:
    """
    Read immutable local artifacts and verify their recorded digests.

    Only ``file://`` references are supported in this initial implementation.
    Unsupported locations fail explicitly rather than being silently treated as
    local paths.
    """

    def read_bytes(self, reference: ArtifactReference) -> bytes:
        parsed = urlparse(reference.uri)
        if parsed.scheme != "file":
            raise UnsupportedArtifactLocationError(
                f"LocalArtifactLoader supports only file:// artifacts; "
                f"received {reference.uri!r}."
            )
        if parsed.netloc not in {"", "localhost"}:
            raise UnsupportedArtifactLocationError(
                "Remote file hosts are not supported by LocalArtifactLoader."
            )
        path = Path(unquote(parsed.path))
        # On Windows, file:///C:/path may be parsed as /C:/path.
        if os.name == "nt" and len(path.as_posix()) >= 3:
            text = path.as_posix()
            if text.startswith("/") and text[2] == ":":
                path = Path(text[1:])
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ArtifactError(
                f"Unable to read artifact {reference.artifact_id!r} "
                f"from {path}: {exc}"
            ) from exc
        actual_digest = sha256_bytes(content)
        if reference.sha256 is None:
            raise ArtifactIntegrityError(
                f"Artifact {reference.artifact_id!r} has no SHA-256 digest."
            )
        if actual_digest != reference.sha256.lower():
            raise ArtifactIntegrityError(
                f"Artifact {reference.artifact_id!r} failed integrity validation. "
                f"Expected {reference.sha256.lower()}, calculated {actual_digest}."
            )
        if reference.size_bytes is not None and len(content) != reference.size_bytes:
            raise ArtifactIntegrityError(
                f"Artifact {reference.artifact_id!r} has size {len(content)}, "
                f"but the contract records {reference.size_bytes}."
            )
        return content


class LocalArtifactStore:
    """
    Store immutable run artifacts beneath a configured local root.

    Artifacts are written atomically. If a path already exists with different
    content, the write fails instead of overwriting historical evidence.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def store_bytes(
        self,
        *,
        run_id: str,
        filename: str,
        kind: ArtifactKind,
        media_type: str,
        content: bytes,
        metadata: dict[str, str] | None = None,
    ) -> ArtifactReference:
        safe_run_id = self._validate_path_component(run_id, "run_id")
        safe_filename = self._validate_filename(filename)
        run_directory = self._root / safe_run_id
        run_directory.mkdir(parents=True, exist_ok=True)
        destination = run_directory / safe_filename
        digest = sha256_bytes(content)
        if destination.exists():
            existing = destination.read_bytes()
            existing_digest = sha256_bytes(existing)
            if existing_digest != digest:
                raise ArtifactError(
                    f"Refusing to overwrite existing artifact {destination} "
                    "with different content."
                )
        else:
            self._atomic_write(destination, content)
        return ArtifactReference(
            artifact_id=f"{safe_run_id}:{safe_filename}",
            kind=kind,
            uri=destination.resolve().as_uri(),
            sha256=digest,
            media_type=media_type,
            size_bytes=len(content),
            immutable=True,
            metadata=metadata or {},
        )

    def store_json(
        self,
        *,
        run_id: str,
        filename: str,
        kind: ArtifactKind,
        payload: object,
        metadata: dict[str, str] | None = None,
    ) -> ArtifactReference:
        content = (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        ).encode("utf-8")
        return self.store_bytes(
            run_id=run_id,
            filename=filename,
            kind=kind,
            media_type="application/json",
            content=content,
            metadata=metadata,
        )

    @staticmethod
    def _validate_path_component(value: str, field_name: str) -> str:
        if not value:
            raise ArtifactError(f"{field_name} must not be empty.")
        if value in {".", ".."}:
            raise ArtifactError(f"{field_name} contains an unsafe value.")
        if any(character in value for character in {"/", "\\", "\x00"}):
            raise ArtifactError(
                f"{field_name} must not contain path separators or NUL bytes."
            )
        return value

    @classmethod
    def _validate_filename(cls, value: str) -> str:
        cls._validate_path_component(value, "filename")
        if Path(value).name != value:
            raise ArtifactError("filename must contain one file name only.")
        return value

    @staticmethod
    def _atomic_write(destination: Path, content: bytes) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            temporary_path.replace(destination)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ArtifactError(
                f"Unable to atomically write artifact {destination}: {exc}"
            ) from exc
