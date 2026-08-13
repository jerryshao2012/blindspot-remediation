"""
EvidenceStore abstraction and local content-addressed implementation.

The storage layer intentionally knows nothing about:

* release thresholds;
* LLMs;
* tests;
* mutation scores;
* business KPIs.

It knows only immutable bytes and manifests.

That narrow responsibility is important because the same interface can later
be implemented with Azure Blob Storage while evidence semantics remain in the
recorder and verifier layers.
"""

from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from .canonical import (
    canonical_json_bytes,
    canonical_sha256,
    pretty_json_bytes,
    sha256_bytes,
)
from .errors import (
    EvidenceIntegrityError,
    EvidenceObjectNotFoundError,
    ManifestAlreadyExistsError,
    ManifestNotFoundError,
)
from .models import RunManifest


class EvidenceStore(ABC):
    """Abstract immutable evidence-store contract."""

    @abstractmethod
    def put_object(
        self,
        *,
        content: bytes,
        expected_sha256: str | None = None,
    ) -> str:
        """
        Store immutable bytes and return their logical object key.

        Implementations must be idempotent for identical content and must never
        overwrite an existing object with different bytes.
        """

    @abstractmethod
    def get_object(self, object_key: str) -> bytes:
        """Read immutable object bytes."""

    @abstractmethod
    def object_exists(self, object_key: str) -> bool:
        """Return whether an immutable object exists."""

    @abstractmethod
    def publish_manifest(self, manifest: RunManifest) -> str:
        """
        Publish a run manifest exactly once.

        Re-publishing identical content may be idempotent.

        Publishing different content for the same run ID must fail.
        """

    @abstractmethod
    def get_manifest(self, run_id: str) -> RunManifest:
        """Load a previously published immutable run manifest."""


class LocalContentAddressedEvidenceStore(EvidenceStore):
    """
    Local filesystem content-addressed evidence store.

    Layout:

        <root>/
            objects/
                sha256/
                    ab/
                        abcdef...
            manifests/
                <run-id>.json

    Objects are addressed by digest rather than caller-selected filenames.

    This removes a large class of accidental overwrite and naming-collision
    problems.
    """

    def __init__(
        self,
        root: Path,
        *,
        verify_after_write: bool = True,
    ) -> None:
        self._root = root.expanduser().resolve()
        self._verify_after_write = verify_after_write

        self._objects_root = self._root / "objects" / "sha256"
        self._manifests_root = self._root / "manifests"

        self._objects_root.mkdir(parents=True, exist_ok=True)
        self._manifests_root.mkdir(parents=True, exist_ok=True)

    def put_object(
        self,
        *,
        content: bytes,
        expected_sha256: str | None = None,
    ) -> str:
        digest = sha256_bytes(content)

        if expected_sha256 is not None:
            normalized_expected = expected_sha256.lower()

            if digest != normalized_expected:
                raise EvidenceIntegrityError(
                    "Evidence bytes do not match the expected SHA-256. "
                    f"Expected {normalized_expected}; calculated {digest}."
                )

        object_key = self._object_key(digest)
        destination = self._resolve_object_key(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            existing = destination.read_bytes()
            existing_digest = sha256_bytes(existing)

            if existing_digest != digest:
                raise EvidenceIntegrityError(
                    f"Content-addressed object {object_key!r} contains bytes "
                    "that do not match its digest identity."
                )

            return object_key

        self._atomic_create(destination, content)

        if self._verify_after_write:
            written_digest = sha256_bytes(destination.read_bytes())

            if written_digest != digest:
                raise EvidenceIntegrityError(
                    f"Post-write verification failed for {object_key!r}."
                )

        return object_key

    def get_object(self, object_key: str) -> bytes:
        path = self._resolve_object_key(object_key)

        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise EvidenceObjectNotFoundError(
                f"Evidence object {object_key!r} does not exist."
            ) from exc
        except OSError as exc:
            raise EvidenceObjectNotFoundError(
                f"Unable to read evidence object {object_key!r}: {exc}"
            ) from exc

    def object_exists(self, object_key: str) -> bool:
        return self._resolve_object_key(object_key).is_file()

    def publish_manifest(self, manifest: RunManifest) -> str:
        self._validate_manifest_identity(manifest)

        run_id = self._safe_run_id(manifest.core.run_id)
        destination = self._manifests_root / f"{run_id}.json"

        content = pretty_json_bytes(manifest)

        if destination.exists():
            try:
                existing = RunManifest.model_validate_json(
                    destination.read_text(encoding="utf-8")
                )
            except Exception as exc:
                raise EvidenceIntegrityError(
                    f"Existing manifest for run {run_id!r} cannot be parsed."
                ) from exc

            self._validate_manifest_identity(existing)

            if canonical_json_bytes(existing) != canonical_json_bytes(manifest):
                raise ManifestAlreadyExistsError(
                    f"Run {run_id!r} already has a different immutable manifest."
                )

            return destination.as_uri()

        self._atomic_create(destination, content)

        if self._verify_after_write:
            loaded = self.get_manifest(run_id)

            if canonical_json_bytes(loaded) != canonical_json_bytes(manifest):
                raise EvidenceIntegrityError(
                    f"Post-write manifest verification failed for run {run_id!r}."
                )

        return destination.as_uri()

    def get_manifest(self, run_id: str) -> RunManifest:
        safe_run_id = self._safe_run_id(run_id)
        path = self._manifests_root / f"{safe_run_id}.json"

        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ManifestNotFoundError(
                f"No manifest exists for run {safe_run_id!r}."
            ) from exc
        except OSError as exc:
            raise ManifestNotFoundError(
                f"Unable to read manifest for run {safe_run_id!r}: {exc}"
            ) from exc

        try:
            manifest = RunManifest.model_validate_json(text)
        except Exception as exc:
            raise EvidenceIntegrityError(
                f"Stored manifest for run {safe_run_id!r} is invalid: {exc}"
            ) from exc

        self._validate_manifest_identity(manifest)
        return manifest

    @staticmethod
    def _object_key(digest: str) -> str:
        return f"objects/sha256/{digest[:2]}/{digest}"

    def _resolve_object_key(self, object_key: str) -> Path:
        normalized = object_key.replace("\\", "/")

        parts = normalized.split("/")

        if (
            len(parts) != 4
            or parts[0] != "objects"
            or parts[1] != "sha256"
            or len(parts[2]) != 2
            or len(parts[3]) != 64
        ):
            raise EvidenceIntegrityError(
                f"Invalid content-addressed object key {object_key!r}."
            )

        digest = parts[3]

        if any(character not in "0123456789abcdef" for character in digest):
            raise EvidenceIntegrityError(
                f"Invalid SHA-256 object key {object_key!r}."
            )

        if parts[2] != digest[:2]:
            raise EvidenceIntegrityError(
                f"Object prefix does not match digest in {object_key!r}."
            )

        destination = self._root / normalized

        try:
            destination.resolve().relative_to(self._root)
        except ValueError as exc:
            raise EvidenceIntegrityError(
                f"Object key escapes evidence root: {object_key!r}."
            ) from exc

        return destination

    @staticmethod
    def _safe_run_id(run_id: str) -> str:
        if (
            not run_id
            or run_id in {".", ".."}
            or "/" in run_id
            or "\\" in run_id
            or "\x00" in run_id
        ):
            raise EvidenceIntegrityError(
                f"Unsafe run ID {run_id!r}."
            )

        return run_id

    @staticmethod
    def _validate_manifest_identity(manifest: RunManifest) -> None:
        calculated = canonical_sha256(manifest.core)

        if calculated != manifest.manifest_sha256:
            raise EvidenceIntegrityError(
                "Run manifest digest is invalid. "
                f"Recorded {manifest.manifest_sha256}; "
                f"calculated {calculated}."
            )

    @staticmethod
    def _atomic_create(destination: Path, content: bytes) -> None:
        """
        Create a file atomically without intentionally overwriting an existing
        immutable object.

        The final hard-link operation is atomic on the local filesystem and
        fails if the destination appeared concurrently.
        """

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

            try:
                os.link(temporary_path, destination)
            except FileExistsError:
                # Another writer won the race. The caller will verify identity
                # on its next read or idempotent invocation.
                pass
            finally:
                temporary_path.unlink(missing_ok=True)

        except OSError:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
