"""
EvidenceRecorder.

This is the semantic bridge between Components 1–3 and durable evidence
storage.

It performs four jobs:

1. Ingest artifacts referenced by platform contracts.
2. Verify their existing SHA-256 identities.
3. Store them in content-addressed immutable storage.
4. Build and publish one immutable RunManifest.

The recorder does not reinterpret gate evidence and does not change the gate
decision.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from ai_engineering_contracts import (
    ArtifactReference,
    ExecutionResult,
    GateRequest,
    GateResult,
)

from .canonical import canonical_sha256, sha256_bytes
from .errors import (
    EvidenceIntegrityError,
    ManifestValidationError,
    UnsupportedEvidenceLocationError,
)
from .models import (
    ArtifactManifestEntry,
    ComponentExecutionRecord,
    ResourceConsumption,
    RunManifest,
    RunManifestCore,
    RunPhase,
)
from .store import EvidenceStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceRecorder:
    """
    Build durable evidence provenance from an engineering run.

    The initial POC ingests ``file://`` artifact references.

    Azure Blob support belongs behind an artifact-ingestion abstraction in a
    later revision. Unsupported URI schemes fail explicitly rather than being
    silently skipped.
    """

    RECORDER_VERSION = "0.1.0"

    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    def record_run(
        self,
        *,
        gate_request: GateRequest,
        execution_result: ExecutionResult,
        gate_result: GateResult,
    ) -> RunManifest:
        self._validate_run_identity(
            gate_request=gate_request,
            execution_result=execution_result,
            gate_result=gate_result,
        )

        artifacts: list[ArtifactManifestEntry] = []
        seen_artifact_ids: set[str] = set()

        def ingest(
            reference: ArtifactReference | None,
            *,
            phase: RunPhase,
            producer_component: str,
            producer_version: str,
        ) -> None:
            if reference is None:
                return

            if reference.artifact_id in seen_artifact_ids:
                # Artifact IDs are logical identities. Reusing one ID for
                # multiple different objects would make provenance ambiguous.
                existing = next(
                    item
                    for item in artifacts
                    if item.artifact_id == reference.artifact_id
                )

                if existing.sha256 != reference.sha256:
                    raise ManifestValidationError(
                        f"Artifact ID {reference.artifact_id!r} refers to "
                        "multiple different digests."
                    )

                return

            entry = self._ingest_artifact(
                reference=reference,
                phase=phase,
                producer_component=producer_component,
                producer_version=producer_version,
            )
            artifacts.append(entry)
            seen_artifact_ids.add(reference.artifact_id)

        # ------------------------------------------------------------------
        # Task-package artifacts.
        #
        # These define what was requested and what gate policy was supposed to
        # govern the run. They are evidence, not merely configuration.
        # ------------------------------------------------------------------

        ingest(
            gate_request.requirement_contract,
            phase=RunPhase.TASK_INPUT,
            producer_component="task-package",
            producer_version=gate_request.task_package_version,
        )
        ingest(
            gate_request.evaluation_specification,
            phase=RunPhase.TASK_INPUT,
            producer_component="task-package",
            producer_version=gate_request.task_package_version,
        )
        ingest(
            gate_request.release_policy,
            phase=RunPhase.TASK_INPUT,
            producer_component="task-package",
            producer_version=gate_request.task_package_version,
        )

        # ------------------------------------------------------------------
        # Change-execution artifacts.
        # ------------------------------------------------------------------

        ingest(
            execution_result.patch_artifact,
            phase=RunPhase.CHANGE_EXECUTION,
            producer_component="ChangeExecutionService",
            producer_version=execution_result.executor_version,
        )

        for reference in execution_result.execution_artifacts:
            ingest(
                reference,
                phase=RunPhase.CHANGE_EXECUTION,
                producer_component="ChangeExecutionService",
                producer_version=execution_result.executor_version,
            )

        # ------------------------------------------------------------------
        # Release-gate evidence.
        # ------------------------------------------------------------------

        ingest(
            gate_result.evidence_package,
            phase=RunPhase.RELEASE_GATE,
            producer_component="ReleaseGateService",
            producer_version=gate_result.gate_version,
        )

        for control in gate_result.hard_control_results:
            for reference in control.evidence_artifacts:
                ingest(
                    reference,
                    phase=RunPhase.RELEASE_GATE,
                    producer_component="ReleaseGateService",
                    producer_version=gate_result.gate_version,
                )

        # Sort artifacts to ensure that manifest identity does not depend on the
        # incidental order in which contract lists were traversed.
        artifacts.sort(
            key=lambda item: (
                item.phase.value,
                item.artifact_id,
                item.sha256,
            )
        )

        components = [
            ComponentExecutionRecord(
                component_name="ChangeExecutionService",
                component_version=execution_result.executor_version,
                started_at=execution_result.started_at,
                completed_at=execution_result.completed_at,
                status=execution_result.status.value,
            ),
            ComponentExecutionRecord(
                component_name="ReleaseGateService",
                component_version=gate_result.gate_version,
                started_at=gate_result.started_at,
                completed_at=gate_result.completed_at,
                status=gate_result.decision.value,
            ),
            ComponentExecutionRecord(
                component_name="EvidenceRecorder",
                component_version=self.RECORDER_VERSION,
                started_at=None,
                completed_at=None,
                status="recorded",
            ),
        ]

        components.sort(key=lambda item: item.component_name)

        candidate_tree = gate_result.metadata.get("candidate_tree") or None

        core = RunManifestCore(
            run_id=gate_request.run_id,
            task_type=gate_request.task_type,
            task_package_version=gate_request.task_package_version,
            repository_url=gate_request.repository_url,
            base_commit=gate_request.base_commit,
            candidate_commit=gate_request.candidate_commit,
            candidate_tree=candidate_tree,
            gate_decision=gate_result.decision,
            gate_version=gate_result.gate_version,
            policy_version=gate_result.policy_version,
            requirement_contract_version=(
                gate_request.requirement_contract.metadata.get("version")
            ),
            evaluation_specification_version=(
                gate_request.evaluation_specification.metadata.get("version")
            ),
            components=components,
            artifacts=artifacts,
            evidence_metrics=dict(
                sorted(gate_result.evidence_metrics.items())
            ),
            decision_reasons=list(gate_result.decision_reasons),
            unmet_obligations=list(gate_result.unmet_obligations),
            contradictions=list(gate_result.contradictions),
            resource_consumption=ResourceConsumption(
                llm_calls=(
                    execution_result.token_usage.llm_calls
                    + gate_result.token_usage.llm_calls
                ),
                input_tokens=(
                    execution_result.token_usage.input_tokens
                    + gate_result.token_usage.input_tokens
                ),
                output_tokens=(
                    execution_result.token_usage.output_tokens
                    + gate_result.token_usage.output_tokens
                ),
                estimated_cost=(
                    execution_result.token_usage.estimated_cost
                    + gate_result.token_usage.estimated_cost
                ),
                deterministic_tool_calls=_parse_nonnegative_int(
                    gate_result.metadata.get(
                        "deterministic_tool_calls",
                        "0",
                    ),
                    "deterministic_tool_calls",
                ),
                generated_tests=gate_result.generated_tests_considered,
                qualified_generated_tests=gate_result.qualified_generated_tests,
                mutants_generated=gate_result.mutants_generated,
                meaningful_mutants_survived=(
                    gate_result.meaningful_mutants_survived
                ),
            ),
            started_at=min(
                execution_result.started_at,
                gate_result.started_at,
            ),
            completed_at=max(
                execution_result.completed_at,
                gate_result.completed_at,
            ),
            metadata={
                "evidence_recorder_version": self.RECORDER_VERSION,
                "manifest_semantics": "online-engineering-run",
            },
        )

        manifest = RunManifest(
            core=core,
            manifest_sha256=canonical_sha256(core),
            published_at=utc_now(),
        )

        self._store.publish_manifest(manifest)

        return manifest

    def _ingest_artifact(
        self,
        *,
        reference: ArtifactReference,
        phase: RunPhase,
        producer_component: str,
        producer_version: str,
    ) -> ArtifactManifestEntry:
        if not reference.immutable:
            raise EvidenceIntegrityError(
                f"Artifact {reference.artifact_id!r} is not marked immutable."
            )

        if reference.sha256 is None:
            raise EvidenceIntegrityError(
                f"Artifact {reference.artifact_id!r} has no SHA-256 digest."
            )

        content = self._read_artifact(reference)

        calculated_digest = sha256_bytes(content)

        if calculated_digest != reference.sha256.lower():
            raise EvidenceIntegrityError(
                f"Artifact {reference.artifact_id!r} failed integrity "
                f"validation. Expected {reference.sha256.lower()}, "
                f"calculated {calculated_digest}."
            )

        if (
            reference.size_bytes is not None
            and reference.size_bytes != len(content)
        ):
            raise EvidenceIntegrityError(
                f"Artifact {reference.artifact_id!r} size mismatch. "
                f"Contract records {reference.size_bytes}; "
                f"actual size is {len(content)}."
            )

        object_key = self._store.put_object(
            content=content,
            expected_sha256=reference.sha256,
        )

        return ArtifactManifestEntry(
            artifact_id=reference.artifact_id,
            kind=reference.kind,
            phase=phase,
            sha256=calculated_digest,
            size_bytes=len(content),
            media_type=reference.media_type,
            object_key=object_key,
            source_uri=reference.uri,
            producer_component=producer_component,
            producer_version=producer_version,
            metadata=reference.metadata,
        )

    @staticmethod
    def _read_artifact(reference: ArtifactReference) -> bytes:
        parsed = urlparse(reference.uri)

        if parsed.scheme != "file":
            raise UnsupportedEvidenceLocationError(
                "Component 4 POC currently ingests file:// artifacts only. "
                f"Received {reference.uri!r}."
            )

        if parsed.netloc not in {"", "localhost"}:
            raise UnsupportedEvidenceLocationError(
                "Remote file hosts are not supported."
            )

        path = Path(unquote(parsed.path))

        if os.name == "nt":
            text = path.as_posix()
            if len(text) >= 3 and text.startswith("/") and text[2] == ":":
                path = Path(text[1:])

        try:
            return path.read_bytes()
        except OSError as exc:
            raise EvidenceIntegrityError(
                f"Unable to read artifact {reference.artifact_id!r}: {exc}"
            ) from exc

    @staticmethod
    def _validate_run_identity(
        *,
        gate_request: GateRequest,
        execution_result: ExecutionResult,
        gate_result: GateResult,
    ) -> None:
        if execution_result.run_id != gate_request.run_id:
            raise ManifestValidationError(
                "ExecutionResult run_id does not match GateRequest."
            )

        if gate_result.run_id != gate_request.run_id:
            raise ManifestValidationError(
                "GateResult run_id does not match GateRequest."
            )

        if execution_result.base_commit.lower() != gate_request.base_commit.lower():
            raise ManifestValidationError(
                "ExecutionResult base commit does not match GateRequest."
            )

        if gate_result.base_commit.lower() != gate_request.base_commit.lower():
            raise ManifestValidationError(
                "GateResult base commit does not match GateRequest."
            )

        if (
            execution_result.candidate_commit is None
            or execution_result.candidate_commit.lower()
            != gate_request.candidate_commit.lower()
        ):
            raise ManifestValidationError(
                "ExecutionResult candidate commit does not match GateRequest."
            )

        if (
            gate_result.candidate_commit.lower()
            != gate_request.candidate_commit.lower()
        ):
            raise ManifestValidationError(
                "GateResult candidate commit does not match GateRequest."
            )


def _parse_nonnegative_int(value: str, field_name: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise ManifestValidationError(
            f"Metadata field {field_name!r} must be an integer."
        ) from exc

    if result < 0:
        raise ManifestValidationError(
            f"Metadata field {field_name!r} must not be negative."
        )

    return result
