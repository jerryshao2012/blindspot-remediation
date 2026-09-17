"""Single-pass assurance with its own immutable evidence package."""

from __future__ import annotations

import json
import multiprocessing
import os
import tempfile
import time
from dataclasses import asdict
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Literal, cast

from conceptual_diversity_mapper import (
    ConceptDimension,
    ConceptSchema,
    DerivationMethod,
    DimensionType,
    GenericDiversityEngine,
    MappingRule,
    ResourceBudget,
    RuleBasedArtifactConceptMapper,
)
from pydantic import Field

from release_gate import __version__
from release_gate.config import ConfigError
from release_gate.engine import GateInputError, run_captured_gate
from release_gate.evidence import EvidenceError, _validate_document, verify_run
from release_gate.git import CandidateCapture, CaptureError, capture_candidate
from release_gate.policy import Verdict
from release_gate.reports import _read_regular_file

from .adapter import EvidenceArtifact, EvidenceBundle, EvidenceDiversityMapperAdapter
from .evidence import (
    AssessmentUnavailable,
    NormalizationCapture,
    base_blob,
    digest,
    normalize,
)
from .policy import AssurancePolicy, Model, load_policy

POLICY_PATH = ".release-gate-assurance.yaml"
MAX_PACKAGE_BYTES = 33554432


class AssuranceResult(Model):
    version: Literal[1] = 1
    run_id: str
    engine_version: str = __version__
    gate_result_path: str
    gate_result_sha256: str
    gate_manifest_sha256: str
    base_commit: str
    candidate_tree: str
    patch_sha256: str
    policy_sha256: str
    mode: Literal["advisory", "enforce"]
    gate_verdict: Literal["PASS", "FAIL", "NEEDS_HUMAN"]
    disposition: Literal["PASS", "FAIL", "NEEDS_HUMAN"]
    exit_code: Literal[0, 1, 2]
    assessment_status: Literal["COMPLETE", "UNAVAILABLE", "NOT_EVALUATED"]
    evidence_sufficient: bool
    reason_codes: list[str]
    artifacts: list[dict[str, Any]]
    coverage: dict[str, Any] | None
    unmet_requirements: list[dict[str, Any]]
    duration_ms: int = Field(ge=0)


class ArtifactEntry(Model):
    path: Literal["result.json", "policy.yaml"]
    sha256: str = Field(pattern="^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0, le=MAX_PACKAGE_BYTES)


class AssuranceManifest(Model):
    version: Literal[1] = 1
    run_id: str
    artifacts: list[ArtifactEntry] = Field(min_length=2, max_length=2)


def _assess(
    policy: AssurancePolicy, artifacts: list[dict[str, Any]], candidate: str
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    if not artifacts:
        raise AssessmentUnavailable("empty evidence bundle")
    schema = ConceptSchema(
        schema_id=policy.concept_schema.schema_id,
        schema_version=policy.concept_schema.schema_version,
        dimensions=tuple(
            ConceptDimension(
                d.dimension_id,
                d.name,
                d.definition,
                "Base-reviewed assurance schema",
                DimensionType.CATEGORICAL,
                allowed_values=tuple(d.values),
            )
            for d in policy.concept_schema.dimensions
        ),
        derivation_method=DerivationMethod.HUMAN_DEFINED,
        provenance="base-reviewed assurance policy",
        human_review_status="reviewed",
    )
    rules = tuple(
        MappingRule(
            d.dimension_id,
            f"concept.{d.dimension_id}",
            "equals",
            v,
            v,
            rationale="Reviewed source binding and successful execution",
        )
        for d in policy.concept_schema.dimensions
        for v in d.values
    )
    # Merge overlapping provenance groups rather than summing lineage roots.
    parents = list(range(len(artifacts)))

    def root(index: int) -> int:
        while parents[index] != index:
            index = parents[index]
        return index

    seen: dict[str, int] = {}
    for index, item in enumerate(artifacts):
        keys = [
            "group:" + item["independence_group"],
            "content:" + item["content_sha256"],
        ]
        keys += ["source:" + h for h in item["reviewed_sources"].values()]
        for key in keys:
            if key in seen:
                parents[root(index)] = root(seen[key])
            seen[key] = index
    evidence = []
    for index, item in enumerate(artifacts):
        lineage = "reviewed-root:" + str(root(index))
        item["lineage_root"] = lineage
        evidence.append(
            EvidenceArtifact(
                evidence_id=item["evidence_id"],
                candidate_change_id=candidate,
                evidence_type="junit_case"
                if item["selector"]["report_id"]
                else "deterministic_check",
                observation=item["observation"],
                addressed_claims=(),
                addressed_behaviors=(),
                method="reviewed_mapping",
                producer_identity=item["selector"]["check_id"],
                result=item["status"],
                confidence=1.0 if item["concepts"] else 0.0,
                provenance=(
                    "verified gate evidence; confidence denotes rule match, not safety"
                ),
                parent_evidence_ids=(lineage,),
                concept_hints=item["concepts"],
                metadata={"report_sha256": item["report_sha256"]},
            )
        )
    adapter = EvidenceDiversityMapperAdapter(
        engine=GenericDiversityEngine(
            concept_mapper=RuleBasedArtifactConceptMapper(rules=rules)
        )
    )
    coverage = adapter.assess_evidence_bundle(
        EvidenceBundle(candidate, candidate, tuple(evidence)),
        schema,
        ResourceBudget(max_additional_artifacts=0),
    )
    unmet = []
    for required in policy.required_regions:
        support = {
            item["lineage_root"]
            for item in artifacts
            if item["concepts"].get(required.dimension_id) == required.value
        }
        if len(support) < required.minimum_independent_support:
            unmet.append({**required.model_dump(), "independent_support": len(support)})
    sufficient = (
        not unmet
        and coverage.mapping_uncertainty_rate <= policy.maximum_mapping_uncertainty_rate
    )
    return asdict(coverage), unmet, sufficient


def persist(root: Path, result: AssuranceResult, policy_bytes: bytes) -> Path:
    parent = root / "_assurance"
    if parent.is_symlink():
        raise EvidenceError("unsafe assurance output directory")
    parent.mkdir(mode=0o700, exist_ok=True)
    if not parent.is_dir():
        raise EvidenceError("unsafe assurance output directory")
    target = parent / result.run_id
    target.mkdir(mode=0o700)  # Exclusive; never replace an existing run.
    marker = target / ".incomplete"
    marker.touch()
    documents = {
        "policy.yaml": policy_bytes,
        "result.json": (result.model_dump_json() + "\n").encode(),
    }
    manifest = AssuranceManifest(
        run_id=result.run_id,
        artifacts=[
            ArtifactEntry(
                path=cast(Literal["result.json", "policy.yaml"], name),
                sha256=digest(data),
                size_bytes=len(data),
            )
            for name, data in documents.items()
        ],
    )
    _validate_document(
        "assurance-result-v1.schema.json", result.model_dump(mode="json")
    )
    _validate_document(
        "assurance-manifest-v1.schema.json", manifest.model_dump(mode="json")
    )
    documents["manifest.json"] = (manifest.model_dump_json() + "\n").encode()
    if sum(map(len, documents.values())) > MAX_PACKAGE_BYTES:
        raise EvidenceError("assurance evidence size limit exceeded")
    for name, data in documents.items():
        fd, temporary = tempfile.mkstemp(dir=target, prefix=".staging-")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target / name)
        finally:
            Path(temporary).unlink(missing_ok=True)
    marker.unlink()
    return target / "result.json"


def run_assurance(
    repository: Path,
    *,
    base: str,
    output: Path | None = None,
    run_id: str | None = None,
) -> tuple[AssuranceResult, Path]:
    try:
        capture = capture_candidate(repository, base=base)
    except CaptureError as error:
        raise GateInputError(str(error)) from error
    try:
        policy_bytes = base_blob(capture, POLICY_PATH)
    except Exception as error:
        raise ConfigError("base assurance policy is missing or unreadable") from error
    policy = load_policy(policy_bytes)
    checks = {c.id: c for c in capture.config.checks}
    for mapping in policy.mappings:
        selector = mapping.selector
        if selector.check_id not in checks:
            raise ConfigError("assurance mapping refers to unknown check")
        reports = {r.id: r for r in checks[selector.check_id].reports}
        if selector.report_id is not None and (
            selector.report_id not in reports
            or reports[selector.report_id].parser.value != "junit-xml"
        ):
            raise ConfigError("assurance case mapping requires a declared JUnit report")
        if selector.report_id is None and any(
            r.parser.value == "junit-xml" for r in reports.values()
        ):
            raise ConfigError("JUnit checks require case-level mappings")
    outcome = run_captured_gate(capture, output=output, run_id=run_id)
    started = time.monotonic()
    verify_run(outcome.result_path.parent)
    gate_bytes = outcome.result_path.read_bytes()
    gate = json.loads(gate_bytes)
    status: Literal["COMPLETE", "UNAVAILABLE", "NOT_EVALUATED"] = "NOT_EVALUATED"
    reasons: list[str] = []
    artifacts: list[dict[str, Any]] = []
    coverage = None
    unmet: list[dict[str, Any]] = []
    sufficient = False
    changed_policy = POLICY_PATH in capture.changed_paths
    if changed_policy:
        reasons.append("ASSURANCE_POLICY_CHANGED")
    elif outcome.verdict is Verdict.PASS:
        try:
            coverage, unmet, sufficient = assess(
                policy,
                artifacts,
                capture.candidate_tree,
                policy.limits.max_elapsed_seconds - (time.monotonic() - started),
                capture=capture,
                run=outcome.result_path.parent,
            )
            if time.monotonic() - started > policy.limits.max_elapsed_seconds:
                raise AssessmentUnavailable("assessment deadline exceeded")
            status = "COMPLETE"
            if not sufficient:
                reasons.append("ASSURANCE_INSUFFICIENT")
        except Exception as error:
            status = "UNAVAILABLE"
            sufficient = False
            coverage = None
            reasons.append("ASSURANCE_UNAVAILABLE:" + type(error).__name__)
    disposition = outcome.verdict.value
    if disposition == "PASS" and (
        changed_policy or (policy.mode == "enforce" and not sufficient)
    ):
        disposition = "NEEDS_HUMAN"
    result = AssuranceResult(
        run_id=gate["run_id"],
        gate_result_path=str(outcome.result_path.absolute()),
        gate_result_sha256=digest(gate_bytes),
        gate_manifest_sha256=digest(
            (outcome.result_path.parent / "manifest.json").read_bytes()
        ),
        base_commit=capture.base_commit,
        candidate_tree=capture.candidate_tree,
        patch_sha256=capture.patch_sha256,
        policy_sha256=digest(policy_bytes),
        mode=policy.mode,
        gate_verdict=outcome.verdict.value,
        disposition=cast(Literal["PASS", "FAIL", "NEEDS_HUMAN"], disposition),
        exit_code=cast(
            Literal[0, 1, 2], {"PASS": 0, "FAIL": 1, "NEEDS_HUMAN": 2}[disposition]
        ),
        assessment_status=status,
        evidence_sufficient=sufficient,
        reason_codes=reasons,
        artifacts=artifacts,
        coverage=coverage,
        unmet_requirements=unmet,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return result, persist(outcome.result_path.parent.parent, result, policy_bytes)


def _worker(
    connection: Connection,
    policy: AssurancePolicy,
    artifacts: list[dict[str, Any]],
    candidate: str,
    capture: NormalizationCapture | None,
    run: Path | None,
) -> None:
    try:
        if capture is not None and run is not None:
            _, artifacts = normalize(capture, run, policy, time.monotonic())
        coverage, unmet, sufficient = _assess(policy, artifacts, candidate)
        payload = json.dumps(
            {
                "coverage": coverage,
                "unmet": unmet,
                "sufficient": sufficient,
                "artifacts": artifacts,
            }
        ).encode()
        if len(payload) > MAX_PACKAGE_BYTES - 2097152:
            raise AssessmentUnavailable("assessment output exceeds limit")
    except Exception as error:
        payload = json.dumps({"error": type(error).__name__}).encode()
    try:
        connection.send_bytes(payload)
    finally:
        connection.close()


def assess_bounded(
    policy: AssurancePolicy,
    artifacts: list[dict[str, Any]],
    candidate: str,
    timeout: float,
    *,
    capture: CandidateCapture | None = None,
    run: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    if timeout <= 0:
        raise AssessmentUnavailable("assessment deadline exceeded")
    if (capture is None) != (run is None):
        raise AssessmentUnavailable("incomplete normalization input")
    normalization_capture = (
        NormalizationCapture.from_candidate(capture) if capture is not None else None
    )
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker,
        args=(writer, policy, artifacts, candidate, normalization_capture, run),
    )
    try:
        process.start()
        writer.close()
        if not reader.poll(timeout):
            raise AssessmentUnavailable("assessment deadline exceeded")
        payload = json.loads(reader.recv_bytes(MAX_PACKAGE_BYTES))
        if "error" in payload:
            raise AssessmentUnavailable("mapper failed: " + payload["error"])
        artifacts[:] = payload["artifacts"]
        return payload["coverage"], payload["unmet"], payload["sufficient"]
    finally:
        writer.close()
        reader.close()
        if process.pid is not None:
            process.join(timeout=0.1)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()


def assess(
    policy: AssurancePolicy,
    artifacts: list[dict[str, Any]],
    candidate: str,
    timeout: float,
    *,
    capture: CandidateCapture | None = None,
    run: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    return assess_bounded(
        policy, artifacts, candidate, timeout, capture=capture, run=run
    )


def verify_assurance(path: Path) -> None:
    """Validate an assurance package and its linked deterministic evidence."""
    if path.is_symlink() or {p.name for p in path.iterdir()} != {
        "result.json",
        "policy.yaml",
        "manifest.json",
    }:
        raise EvidenceError("incomplete or unsafe assurance package")
    manifest_bytes = _read_regular_file(path / "manifest.json", 1048576)
    manifest = AssuranceManifest.model_validate_json(manifest_bytes)
    if {a.path for a in manifest.artifacts} != {"result.json", "policy.yaml"}:
        raise EvidenceError("invalid assurance inventory")
    for item in manifest.artifacts:
        data = _read_regular_file(path / item.path, MAX_PACKAGE_BYTES)
        if len(data) != item.size_bytes or digest(data) != item.sha256:
            raise EvidenceError("assurance artifact hash mismatch")
    result = AssuranceResult.model_validate_json(
        _read_regular_file(path / "result.json", MAX_PACKAGE_BYTES)
    )
    if result.run_id != manifest.run_id or result.policy_sha256 != digest(
        _read_regular_file(path / "policy.yaml", 1048576)
    ):
        raise EvidenceError("assurance identity mismatch")
    gate_path = Path(result.gate_result_path)
    verify_run(gate_path.parent)
    gate_bytes = _read_regular_file(gate_path, 2097152)
    if (
        digest(gate_bytes) != result.gate_result_sha256
        or digest(_read_regular_file(gate_path.parent / "manifest.json", 4194304))
        != result.gate_manifest_sha256
    ):
        raise EvidenceError("linked gate evidence changed")
    gate = json.loads(gate_bytes)
    if (
        any(
            gate[key] != getattr(result, key)
            for key in ("run_id", "base_commit", "candidate_tree", "patch_sha256")
        )
        or gate["verdict"] != result.gate_verdict
    ):
        raise EvidenceError("linked gate identity mismatch")
