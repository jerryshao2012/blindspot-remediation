"""
Independent run-manifest verification.

Verification intentionally does not trust the recorder.

It independently checks:

1. The manifest's own canonical digest.
2. Existence of every referenced evidence object.
3. SHA-256 of every referenced evidence object.
4. Recorded size of every referenced object.

This is the mechanism that turns "we saved the evidence" into the stronger
statement:

    "The evidence currently stored is exactly the evidence identified by the
     immutable run manifest."
"""

from __future__ import annotations

from .canonical import canonical_sha256, sha256_bytes
from .models import ManifestVerificationResult, RunManifest
from .store import EvidenceStore


class ManifestVerifier:
    """Verify one immutable manifest and all of its referenced evidence."""

    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    def verify_run(self, run_id: str) -> ManifestVerificationResult:
        manifest = self._store.get_manifest(run_id)
        return self.verify_manifest(manifest)

    def verify_manifest(
        self,
        manifest: RunManifest,
    ) -> ManifestVerificationResult:
        calculated_manifest_digest = canonical_sha256(manifest.core)

        manifest_digest_valid = (
            calculated_manifest_digest == manifest.manifest_sha256
        )

        missing: list[str] = []
        corrupted: list[str] = []
        errors: list[str] = []
        verified_count = 0

        for artifact in manifest.core.artifacts:
            if not self._store.object_exists(artifact.object_key):
                missing.append(artifact.artifact_id)
                continue

            try:
                content = self._store.get_object(artifact.object_key)
            except Exception as exc:
                errors.append(
                    f"{artifact.artifact_id}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            calculated_digest = sha256_bytes(content)

            if calculated_digest != artifact.sha256:
                corrupted.append(artifact.artifact_id)
                continue

            if len(content) != artifact.size_bytes:
                corrupted.append(artifact.artifact_id)
                continue

            verified_count += 1

        all_artifacts_present = not missing
        all_artifact_digests_valid = not corrupted and not errors

        valid = (
            manifest_digest_valid
            and all_artifacts_present
            and all_artifact_digests_valid
            and verified_count == len(manifest.core.artifacts)
        )

        if not manifest_digest_valid:
            errors.append(
                "Manifest canonical SHA-256 does not match the recorded digest."
            )

        return ManifestVerificationResult(
            run_id=manifest.core.run_id,
            valid=valid,
            manifest_digest_valid=manifest_digest_valid,
            all_artifacts_present=all_artifacts_present,
            all_artifact_digests_valid=all_artifact_digests_valid,
            verified_artifact_count=verified_count,
            missing_artifacts=sorted(missing),
            corrupted_artifacts=sorted(corrupted),
            errors=errors,
        )
