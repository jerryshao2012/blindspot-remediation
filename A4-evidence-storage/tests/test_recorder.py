"""
Recorder integration tests.

These tests intentionally focus on invariants that Component 4 owns.

The full end-to-end repository test should additionally run Components 2, 3,
and 4 together once those packages are assembled in the same monorepo.
"""

from pathlib import Path

from ai_engineering_evidence.canonical import sha256_bytes
from ai_engineering_evidence.store import (
    LocalContentAddressedEvidenceStore,
)


def test_store_preserves_exact_bytes(
    tmp_path: Path,
) -> None:
    store = LocalContentAddressedEvidenceStore(
        tmp_path / "evidence"
    )

    content = (
        b'{"decision":"pass","tests":100,'
        b'"coverage":91.25}\n'
    )

    object_key = store.put_object(
        content=content,
        expected_sha256=sha256_bytes(content),
    )

    assert store.get_object(object_key) == content


def test_identical_evidence_deduplicates(
    tmp_path: Path,
) -> None:
    store = LocalContentAddressedEvidenceStore(
        tmp_path / "evidence"
    )

    content = b"same deterministic report"

    first = store.put_object(content=content)
    second = store.put_object(content=content)

    assert first == second
