"""Evidence domain contracts and the original mapper adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from conceptual_diversity_mapper import (
    ArtifactDescriptor,
    ArtifactLineage,
    ConceptMapping,
    ConceptSchema,
    CoverageGap,
    CoverageRegion,
    ExpansionAssessment,
    ExpansionCandidate,
    ExpansionRequest,
    GenericDiversityEngine,
    ResourceBudget,
)


@dataclass(frozen=True)
class EvidenceArtifact:
    """
    Structured observation relevant to correctness, safety, or suitability of
    a specific candidate code change.
    """

    evidence_id: str

    candidate_change_id: str

    evidence_type: str

    observation: Any

    addressed_claims: tuple[str, ...]
    addressed_behaviors: tuple[str, ...]

    method: str
    producer_identity: str

    result: str

    confidence: float

    provenance: str

    parent_evidence_ids: tuple[str, ...] = ()

    generation_batch_id: str | None = None
    model_identity: str | None = None
    prompt_template_identity: str | None = None

    transformation_history: tuple[str, ...] = ()

    # Explicit concept hints are optional structured metadata supplied by
    # evidence collectors. They are useful for deterministic POC integration.
    #
    # They do not override independent remapping during expansion assessment.
    concept_hints: Mapping[str, Any] = field(default_factory=dict)

    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceBundle:
    """Collection of evidence for one candidate change."""

    bundle_id: str
    candidate_change_id: str

    artifacts: tuple[EvidenceArtifact, ...]


@dataclass(frozen=True)
class EvidenceCoverageGap:
    """Evidence-domain representation of a generic coverage gap."""

    gap_id: str

    evidence_dimension: str
    desired_evidence_characteristic: Any

    lineage_aware_support: int

    uncertainty: float
    priority: float

    rationale: str


@dataclass(frozen=True)
class EvidenceExpansionRequest:
    """
    Evidence-domain request consumed by EvidencePlanner.

    EvidencePlanner remains responsible for choosing the collector:
    generated tests, static analysis, mutation analysis, semantic review, etc.
    """

    request_id: str

    source_gap_id: str

    requested_characteristics: tuple[tuple[str, Any], ...]

    maximum_additional_evidence: int

    priority: float

    rationale: str


@dataclass(frozen=True)
class EvidenceCoverageResult:
    """Complete client-facing result."""

    concept_schema_id: str
    concept_schema_version: str

    generic_assessment_id: str

    artifact_mappings: tuple[ConceptMapping, ...]

    coverage_regions: tuple[CoverageRegion, ...]

    coverage_gaps: tuple[EvidenceCoverageGap, ...]

    expansion_requests: tuple[EvidenceExpansionRequest, ...]

    mapping_uncertainty_rate: float

    mapper_version: str
    configuration_hash: str
    exact_duplicate_pairs: int
    conceptual_duplicate_pairs: int


# =============================================================================
# EVIDENCE ADAPTER
# =============================================================================


class EvidenceDiversityMapperAdapter:
    """
    CLIENT-FACING INTEGRATION SURFACE.

    This is the class the L1 EvidencePlanner / integration layer should use.

    It owns translation between:

        EvidenceArtifact
            <->
        ArtifactDescriptor

    and:

        CoverageGap / ExpansionRequest
            <->
        evidence-domain representations.

    The generic Diversity Mapper never imports ReleaseGateService or GatePolicy.
    """

    def __init__(
        self,
        engine: GenericDiversityEngine,
    ) -> None:

        self.engine = engine

    def assess_evidence_bundle(
        self,
        bundle: EvidenceBundle,
        schema: ConceptSchema,
        budget: ResourceBudget,
    ) -> EvidenceCoverageResult:
        """
        Main L1 integration operation.

        Steps:

        1. Translate EvidenceArtifact objects into domain-neutral descriptors.
        2. Map every artifact.
        3. Assess conceptual coverage.
        4. Identify gaps.
        5. Produce budget-aware expansion requests.
        6. Translate results back to evidence-domain contracts.

        No release decision is produced.
        """

        if not bundle.artifacts:
            raise ValueError("EvidenceBundle cannot be empty.")

        for evidence in bundle.artifacts:
            if evidence.candidate_change_id != bundle.candidate_change_id:
                raise ValueError(
                    "EvidenceBundle contains evidence for a different candidate change."
                )

        generic_artifacts = tuple(
            self._to_artifact_descriptor(evidence) for evidence in bundle.artifacts
        )

        mappings = self.engine.map_artifacts(
            generic_artifacts,
            schema,
        )

        assessment = self.engine.assess_coverage(
            artifacts=generic_artifacts,
            mappings=mappings,
            schema=schema,
        )

        generic_requests = self.engine.plan_expansion(
            assessment,
            budget,
        )

        evidence_gaps = tuple(
            self._to_evidence_gap(
                gap,
                schema,
            )
            for gap in assessment.gaps
        )

        evidence_requests = tuple(
            self._to_evidence_expansion_request(
                request,
                schema,
            )
            for request in generic_requests
        )

        return EvidenceCoverageResult(
            configuration_hash=assessment.configuration_hash,
            exact_duplicate_pairs=assessment.exact_duplicate_pairs,
            conceptual_duplicate_pairs=assessment.conceptual_duplicate_pairs,
            concept_schema_id=schema.schema_id,
            concept_schema_version=(schema.schema_version),
            generic_assessment_id=(assessment.assessment_id),
            artifact_mappings=mappings,
            coverage_regions=(assessment.regions),
            coverage_gaps=evidence_gaps,
            expansion_requests=(evidence_requests),
            mapping_uncertainty_rate=(assessment.mapping_uncertainty_rate),
            mapper_version=(assessment.mapper_version),
        )

    def assess_generated_evidence(
        self,
        generated_evidence: Sequence[EvidenceArtifact],
        requests: Sequence[EvidenceExpansionRequest],
        schema: ConceptSchema,
    ) -> tuple[ExpansionAssessment, ...]:
        """
        Closed-loop re-mapping.

        The method deliberately does NOT assume generated evidence covers a
        requested concept because a generator was asked to create it.
        """

        generic_request_lookup = {
            request.request_id: ExpansionRequest(
                request_id=request.request_id,
                schema_id=schema.schema_id,
                schema_version=(schema.schema_version),
                source_gap_id=(request.source_gap_id),
                desired_dimensions=tuple(
                    (
                        self._dimension_id_from_name(
                            schema,
                            name,
                        ),
                        value,
                    )
                    for name, value in request.requested_characteristics
                ),
                priority=request.priority,
                maximum_artifacts=(request.maximum_additional_evidence),
                provenance=("EvidenceDiversityMapperAdapter"),
                rationale=request.rationale,
            )
            for request in requests
        }

        candidates: list[ExpansionCandidate] = []

        for evidence in generated_evidence:
            request_id = evidence.metadata.get("expansion_request_id")

            if not request_id:
                raise ValueError(
                    f"Generated evidence {evidence.evidence_id!r} "
                    "must record expansion_request_id in metadata."
                )

            if request_id not in generic_request_lookup:
                raise KeyError(f"Unknown expansion_request_id {request_id!r}.")

            candidates.append(
                ExpansionCandidate(
                    request_id=request_id,
                    artifact=(self._to_artifact_descriptor(evidence)),
                )
            )

        return self.engine.assess_expansion_candidates(
            candidates=candidates,
            requests=tuple(generic_request_lookup.values()),
            schema=schema,
        )

    @staticmethod
    def _to_artifact_descriptor(
        evidence: EvidenceArtifact,
    ) -> ArtifactDescriptor:

        attributes = {
            "candidate_change_id": evidence.candidate_change_id,
            "evidence_type": evidence.evidence_type,
            "addressed_claims": evidence.addressed_claims,
            "addressed_behaviors": evidence.addressed_behaviors,
            "method": evidence.method,
            "producer_identity": evidence.producer_identity,
            "result": evidence.result,
            "confidence": evidence.confidence,
            # Concept hints are flattened into the generic attribute namespace.
            # This permits deterministic POC mapping rules while keeping the
            # generic engine free from EvidenceArtifact imports.
            **{
                f"concept.{key}": value for key, value in evidence.concept_hints.items()
            },
            # Metadata is intentionally namespaced to prevent collisions with
            # canonical fields above.
            **{f"metadata.{key}": value for key, value in evidence.metadata.items()},
        }

        return ArtifactDescriptor(
            artifact_id=evidence.evidence_id,
            artifact_type=evidence.evidence_type,
            payload=evidence.observation,
            attributes=attributes,
            lineage=ArtifactLineage(
                parent_artifact_ids=(evidence.parent_evidence_ids),
                generation_batch_id=(evidence.generation_batch_id),
                generator_identity=(evidence.producer_identity),
                model_identity=(evidence.model_identity),
                prompt_template_identity=(evidence.prompt_template_identity),
                source_method=evidence.method,
                transformation_history=(evidence.transformation_history),
            ),
            provenance=evidence.provenance,
        )

    @staticmethod
    def _to_evidence_gap(
        gap: CoverageGap,
        schema: ConceptSchema,
    ) -> EvidenceCoverageGap:

        dimension = schema.dimension_by_id(gap.dimension_id)

        return EvidenceCoverageGap(
            gap_id=gap.gap_id,
            evidence_dimension=dimension.name,
            desired_evidence_characteristic=(gap.desired_value),
            lineage_aware_support=(gap.current_support),
            uncertainty=gap.uncertainty,
            priority=gap.priority,
            rationale=gap.rationale,
        )

    @staticmethod
    def _to_evidence_expansion_request(
        request: ExpansionRequest,
        schema: ConceptSchema,
    ) -> EvidenceExpansionRequest:

        characteristics = []

        for (
            dimension_id,
            value,
        ) in request.desired_dimensions:
            dimension = schema.dimension_by_id(dimension_id)

            characteristics.append(
                (
                    dimension.name,
                    value,
                )
            )

        return EvidenceExpansionRequest(
            request_id=request.request_id,
            source_gap_id=(request.source_gap_id),
            requested_characteristics=tuple(characteristics),
            maximum_additional_evidence=(request.maximum_artifacts),
            priority=request.priority,
            rationale=request.rationale,
        )

    @staticmethod
    def _dimension_id_from_name(
        schema: ConceptSchema,
        name: str,
    ) -> str:

        matches = [
            dimension.dimension_id
            for dimension in schema.dimensions
            if dimension.name == name
        ]

        if len(matches) != 1:
            raise KeyError(
                f"Dimension name {name!r} must resolve to exactly one schema dimension."
            )

        return matches[0]


# =============================================================================
# CLIENT-SPECIFIC EVIDENCE SCHEMA EXAMPLE
# =============================================================================
#
# IMPORTANT:
#
# This schema is an EXAMPLE evidence schema and is not hard-coded into the
# generic engine.
#
# A production L1 project may version and replace it without changing the
# GenericDiversityEngine.
# =============================================================================
