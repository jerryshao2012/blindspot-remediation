from datetime import datetime, timezone
from pathlib import Path

from ai_engineering_contracts import ArtifactKind, GateDecision

from ai_engineering_evidence.canonical import (
    canonical_sha256,
    sha256_bytes,
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
from ai_engineering_evidence.verifier import ManifestVerifier


NOW = datetime(2026, 8, 6, 19, 0, tzinfo=timezone.utc)


def create_manifest(
    store: LocalContentAddressedEvidenceStore,
) -> RunManifest:
    content = b"authoritative evidence"
    digest = sha256_bytes(content)
    object_key = store.put_object(content=content)

    artifact = ArtifactManifestEntry(
        artifact_id="gate-evidence",
        kind=ArtifactKind.EVIDENCE_PACKAGE,
        phase=RunPhase.RELEASE_GATE,
        sha256=digest,
        size_bytes=len(content),
        media_type="application/json",
        object_key=object_key,
        producer_component="ReleaseGateService",
        producer_version="0.1.0",
    )

    core = RunManifestCore(
        run_id="verify-run",
        task_type="X1-test",
        task_package_version="1.0.0",
        repository_url="file:///repository",
        base_commit="a" * 40,
        candidate_commit="b" * 40,
        candidate_tree="c" * 40,
        gate_decision=GateDecision.PASS,
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

    manifest = RunManifest(
        core=core,
        manifest_sha256=canonical_sha256(core),
        published_at=NOW,
    )

    store.publish_manifest(manifest)
    return manifest


def test_valid_manifest_verifies(
    tmp_path: Path,
) -> None:
    store = LocalContentAddressedEvidenceStore(tmp_path)
    create_manifest(store)

    result = ManifestVerifier(store).verify_run("verify-run")

    assert result.valid
    assert result.manifest_digest_valid
    assert result.all_artifacts_present
    assert result.all_artifact_digests_valid
    assert result.verified_artifact_count == 1
