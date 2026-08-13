from __future__ import annotations

from pathlib import Path

import pytest
from ai_engineering_contracts import ArtifactKind, ArtifactReference

from ai_engineering_change_executor.artifacts import (
    LocalArtifactLoader,
    LocalArtifactStore,
    sha256_bytes,
)
from ai_engineering_change_executor.errors import ArtifactIntegrityError


def test_store_and_load_local_artifact(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    loader = LocalArtifactLoader()
    reference = store.store_bytes(
        run_id="run-1",
        filename="candidate.patch",
        kind=ArtifactKind.PATCH,
        media_type="text/x-diff",
        content=b"example patch\n",
    )
    assert loader.read_bytes(reference) == b"example patch\n"
    assert reference.sha256 == sha256_bytes(b"example patch\n")


def test_loader_rejects_digest_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "patch.diff"
    path.write_bytes(b"actual content")
    reference = ArtifactReference(
        artifact_id="run-1:input.patch",
        kind=ArtifactKind.PATCH,
        uri=path.resolve().as_uri(),
        sha256="0" * 64,
        media_type="text/x-diff",
        size_bytes=len(b"actual content"),
        immutable=True,
    )
    with pytest.raises(ArtifactIntegrityError):
        LocalArtifactLoader().read_bytes(reference)
