"""
Local immutable artifact loading and storage.

The initial gate reads ``file://`` artifacts and writes evidence under a local
artifact root. Azure Blob Storage can later be added behind the same conceptual
boundary.

All immutable artifacts are verified or created using SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml
from ai_engineering_contracts import ArtifactKind, ArtifactReference
from pydantic import BaseModel

from .errors import (
    ArtifactError,
    ArtifactIntegrityError,
    UnsupportedArtifactLocationError,
)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class LocalArtifactLoader:
    """Read and verify immutable local artifacts."""

    def read_bytes(self, reference: ArtifactReference) -> bytes:
        parsed = urlparse(reference.uri)
        if parsed.scheme != "file":
            raise UnsupportedArtifactLocationError(
                "Component 3 supports file:// artifacts only. "
                f"Received {reference.uri!r}."
            )
        if parsed.netloc not in {"", "localhost"}:
            raise UnsupportedArtifactLocationError(
                "Remote file hosts are not supported."
            )
        path = Path(unquote(parsed.path))
        if os.name == "nt":
            text = path.as_posix()
            if len(text) >= 3 and text.startswith("/") and text[2] == ":":
                path = Path(text[1:])
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ArtifactError(
                f"Unable to read artifact {reference.artifact_id!r}: {exc}"
            ) from exc
        if reference.sha256 is None:
            raise ArtifactIntegrityError(
                f"Artifact {reference.artifact_id!r} has no SHA-256 digest."
            )
        actual_digest = sha256_bytes(content)
        if actual_digest != reference.sha256.lower():
            raise ArtifactIntegrityError(
                f"Artifact {reference.artifact_id!r} failed digest validation. "
                f"Expected {reference.sha256.lower()}, calculated {actual_digest}."
            )
        if reference.size_bytes is not None and len(content) != reference.size_bytes:
            raise ArtifactIntegrityError(
                f"Artifact {reference.artifact_id!r} has size {len(content)}, "
                f"but its contract records {reference.size_bytes}."
            )
        return content

    def read_structured_model(
        self,
        reference: ArtifactReference,
        model_type: type[BaseModel],
    ) -> BaseModel:
        """Parse a verified JSON or YAML artifact into a strict Pydantic model."""
        content = self.read_bytes(reference)
        media_type = reference.media_type.lower()
        try:
            if "json" in media_type:
                raw = json.loads(content.decode("utf-8"))
            elif "yaml" in media_type or "yml" in media_type:
                raw = yaml.safe_load(content.decode("utf-8"))
            else:
                # JSON is attempted first because all cross-service contracts are
                # naturally serializable to JSON. YAML is the fallback.
                try:
                    raw = json.loads(content.decode("utf-8"))
                except json.JSONDecodeError:
                    raw = yaml.safe_load(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
            raise ArtifactError(
                f"Artifact {reference.artifact_id!r} is not valid JSON or YAML: "
                f"{exc}"
            ) from exc
        try:
            return model_type.model_validate(raw)
        except Exception as exc:
            raise ArtifactError(
                f"Artifact {reference.artifact_id!r} failed "
                f"{model_type.__name__} validation: {exc}"
            ) from exc


class LocalArtifactStore:
    """Atomically store immutable run artifacts beneath a local root."""

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

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
        safe_run_id = self._safe_component(run_id, "run_id")
        safe_filename = self._safe_component(filename, "filename")
        if Path(safe_filename).name != safe_filename:
            raise ArtifactError("filename must contain one filename only.")
        directory = self._root / safe_run_id
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / safe_filename
        digest = sha256_bytes(content)
        if destination.exists():
            existing_digest = sha256_bytes(destination.read_bytes())
            if existing_digest != digest:
                raise ArtifactError(
                    f"Refusing to overwrite {destination} with different content."
                )
        else:
            self._atomic_write(destination, content)
        return ArtifactReference(
            artifact_id=f"{safe_run_id}:{safe_filename}",
            kind=kind,
            uri=destination.as_uri(),
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
    def _safe_component(value: str, field_name: str) -> str:
        if not value or value in {".", ".."}:
            raise ArtifactError(f"{field_name} contains an unsafe value.")
        if any(character in value for character in {"/", "\\", "\x00"}):
            raise ArtifactError(
                f"{field_name} must not contain separators or NUL bytes."
            )
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
                f"Unable to write artifact {destination}: {exc}"
            ) from exc
