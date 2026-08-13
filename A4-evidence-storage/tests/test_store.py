from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_engineering_evidence.canonical import (
    canonical_sha256,
    sha256_bytes,
)
from ai_engineering_evidence.errors import (
    EvidenceIntegrityError,
    ManifestAlreadyExistsError,
)
from ai_engineering_evidence.models import (
    ArtifactManifestEntry,
    ComponentExecutionRecord,
    RunManifest,
    RunManifestCore,
    RunPhase,
)
from ai_engineering_evidence.store import (
    LocalContentAddressedEvidenceStore,
)
from ai_engineering_contracts import ArtifactKind, GateDecision


NOW = datetime(2026, 8, 6, 19, 0, tzinfo=timezone.utc)


def build_manifest(
    *,
    artifact: ArtifactManifestEntry,
    decision: GateDecision = GateDecision.PASS,
) -> RunManifest:
    core = RunManifestCore(
        run_id="run-1",
        task_type="X1-test",
        task_package_version="1.0.0",
        repository_url="file:///repository",
        base_commit="a" * 40,
        candidate_commit="b" * 40,
        candidate_tree="c" * 40,
        gate_decision=decision,
        gate_version="0.1.0",
        policy_version="1.0.0",
        components=[
            ComponentExecutionRecord(
                component_name="ReleaseGateService",
                component_version="0.1.0",
                started_at=NOW,
                completed_at=NOW,
                status="pass",
            )
        ],
        artifacts=[artifact],
        started_at=NOW,
        completed_at=NOW,
    )

    return RunManifest(
        core=core,
        manifest_sha256=canonical_sha256(core),
        published_at=NOW,
    )


def test_content_addressed_store_is_idempotent(
    tmp_path: Path,
) -> None:
    store = LocalContentAddressedEvidenceStore(tmp_path)

    content = b"same evidence"

    first = store.put_object(content=content)
    second = store.put_object(content=content)

    assert first == second
    assert store.get_object(first) == content


def test_expected_digest_is_enforced(
    tmp_path: Path,
) -> None:
    store = LocalContentAddressedEvidenceStore(tmp_path)

    with pytest.raises(EvidenceIntegrityError):
        store.put_object(
            content=b"actual",
            expected_sha256=sha256_bytes(b"different"),
        )


def test_manifest_publication_is_idempotent_for_identical_content(
    tmp_path: Path,
) -> None:
    store = LocalContentAddressedEvidenceStore(tmp_path)

    content = b"artifact"
    digest = sha256_bytes(content)
    object_key = store.put_object(content=content)

    artifact = ArtifactManifestEntry(
        artifact_id="artifact-1",
        kind=ArtifactKind.OTHER,
        phase=RunPhase.RELEASE_GATE,
        sha256=digest,
        size_bytes=len(content),
        media_type="application/octet-stream",
        object_key=object_key,
        producer_component="test",
        producer_version="1.0.0",
    )

    manifest = build_manifest(artifact=artifact)

    first = store.publish_manifest(manifest)
    second = store.publish_manifest(manifest)

    assert first == second


def test_different_manifest_cannot_replace_existing_run(
    tmp_path: Path,
) -> None:
    store = LocalContentAddressedEvidenceStore(tmp_path)

    content = b"artifact"
    digest = sha256_bytes(content)
    object_key = store.put_object(content=content)

    artifact = ArtifactManifestEntry(
        artifact_id="artifact-1",
        kind=ArtifactKind.OTHER,
        phase=RunPhase.RELEASE_GATE,
        sha256=digest,
        size_bytes=len(content),
        media_type="application/octet-stream",
        object_key=object_key,
        producer_component="test",
        producer_version="1.0.0",
    )

    passing = build_manifest(
        artifact=artifact,
        decision=GateDecision.PASS,
    )
    failing = build_manifest(
        artifact=artifact,
        decision=GateDecision.FAIL,
    )

    store.publish_manifest(passing)

    with pytest.raises(ManifestAlreadyExistsError):
        store.publish_manifest(failing)
