"""Compatibility entry point for the original conceptual mapper demonstration.

Install conceptual-diversity-mapper and release-gate before running this file.
"""
from dataclasses import asdict
import json
from conceptual_diversity_mapper import *  # noqa: F403
from release_gate.assurance.adapter import *  # noqa: F403

def build_example_evidence_schema() -> ConceptSchema:
    """
    Construct an explicit evidence schema based on concepts in the client's
    requirement document.

    These dimensions remain domain-specific and therefore live outside the
    generic engine.
    """

    dimensions = (

        ConceptDimension(
            dimension_id="behavior_type",
            name="Behavior Type",
            definition=(
                "The behavioral condition examined by the evidence."
            ),
            rationale=(
                "Distinguishes normal, boundary, invalid, error, "
                "and dependency-failure conditions."
            ),
            dimension_type=DimensionType.CATEGORICAL,
            allowed_values=(
                "normal",
                "boundary",
                "invalid_input",
                "error_handling",
                "dependency_failure",
            ),
            examples=(
                "Boundary-value test",
                "Invalid-input test",
            ),
            counterexamples=(
                "Different variable names without behavior change",
            ),
            derivation_method=(
                DerivationMethod.TASK_SPECIFICATION
            ),
            provenance=(
                "L1 engineering automation evidence requirements"
            ),
        ),

        ConceptDimension(
            dimension_id="authorization",
            name="Authorization",
            definition=(
                "Whether the evidence examines authorization "
                "conditions or authorization-state transitions."
            ),
            rationale=(
                "Authorization behavior is explicitly identified as "
                "an important code-change evidence dimension."
            ),
            dimension_type=DimensionType.BOOLEAN,
            derivation_method=(
                DerivationMethod.TASK_SPECIFICATION
            ),
            provenance=(
                "L1 engineering automation evidence requirements"
            ),
        ),

        ConceptDimension(
            dimension_id="temporal_behavior",
            name="Temporal Behavior",
            definition=(
                "Whether the evidence examines behavior whose outcome "
                "depends on timing, ordering, retry, delay, or sequence."
            ),
            rationale=(
                "Temporal conditions may reveal failures absent from "
                "ordinary deterministic examples."
            ),
            dimension_type=DimensionType.BOOLEAN,
            derivation_method=(
                DerivationMethod.TASK_SPECIFICATION
            ),
            provenance=(
                "L1 engineering automation evidence requirements"
            ),
        ),

        ConceptDimension(
            dimension_id="concurrency",
            name="Concurrency",
            definition=(
                "Whether the evidence examines concurrent or "
                "interleaved execution behavior."
            ),
            rationale=(
                "Concurrency is explicitly identified as an example "
                "evidence dimension."
            ),
            dimension_type=DimensionType.BOOLEAN,
            derivation_method=(
                DerivationMethod.TASK_SPECIFICATION
            ),
            provenance=(
                "L1 engineering automation evidence requirements"
            ),
        ),

        ConceptDimension(
            dimension_id="invariant_preservation",
            name="Invariant Preservation",
            definition=(
                "Whether the evidence examines preservation or "
                "violation of a declared invariant."
            ),
            rationale=(
                "Invariant testing provides conceptually distinct "
                "evidence from ordinary example-based testing."
            ),
            dimension_type=DimensionType.BOOLEAN,
            derivation_method=(
                DerivationMethod.TASK_SPECIFICATION
            ),
            provenance=(
                "L1 engineering automation evidence requirements"
            ),
        ),

        ConceptDimension(
            dimension_id="neighbor_interaction",
            name="Neighbor Interaction",
            definition=(
                "Whether the evidence examines interaction between "
                "changed code and unchanged neighboring code."
            ),
            rationale=(
                "The client explicitly identifies interaction with "
                "unchanged neighboring code as an important dimension."
            ),
            dimension_type=DimensionType.BOOLEAN,
            derivation_method=(
                DerivationMethod.TASK_SPECIFICATION
            ),
            provenance=(
                "L1 engineering automation evidence requirements"
            ),
        ),
    )

    schema = ConceptSchema(
        schema_id="l1_evidence_concepts",
        schema_version=UNIVERSAL_SCHEMA_VERSION,
        dimensions=dimensions,
        derivation_method=DerivationMethod.HYBRID,
        provenance=(
            "Initial L1 evidence schema constructed from project "
            "requirements; intended to evolve under explicit versioning."
        ),
        human_review_status="requires_project_review",
    )

    schema.validate()

    return schema


# =============================================================================
# DETERMINISTIC EVIDENCE RULES FOR THE POC
# =============================================================================


def build_example_evidence_mapping_rules(
) -> tuple[MappingRule, ...]:
    """
    Deterministic test-double / POC rules.

    Real evidence collectors can populate concept_hints explicitly, and these
    rules map those hints into the evidence schema.

    This permits integration tests without live model calls.
    """

    rules = (

        # ---------------------------------------------------------------------
        # Behavior Type
        # ---------------------------------------------------------------------

        MappingRule(
            dimension_id="behavior_type",
            attribute_name="concept.behavior_type",
            operator="equals",
            expected_value="normal",
            mapped_value="normal",
            rationale="Evidence collector explicitly classified normal behavior.",
        ),

        MappingRule(
            dimension_id="behavior_type",
            attribute_name="concept.behavior_type",
            operator="equals",
            expected_value="boundary",
            mapped_value="boundary",
            rationale="Evidence collector explicitly classified boundary behavior.",
        ),

        MappingRule(
            dimension_id="behavior_type",
            attribute_name="concept.behavior_type",
            operator="equals",
            expected_value="invalid_input",
            mapped_value="invalid_input",
            rationale="Evidence collector explicitly classified invalid input.",
        ),

        MappingRule(
            dimension_id="behavior_type",
            attribute_name="concept.behavior_type",
            operator="equals",
            expected_value="error_handling",
            mapped_value="error_handling",
            rationale="Evidence collector explicitly classified error handling.",
        ),

        MappingRule(
            dimension_id="behavior_type",
            attribute_name="concept.behavior_type",
            operator="equals",
            expected_value="dependency_failure",
            mapped_value="dependency_failure",
            rationale="Evidence collector explicitly classified dependency failure.",
        ),

        # ---------------------------------------------------------------------
        # Authorization
        # ---------------------------------------------------------------------

        MappingRule(
            dimension_id="authorization",
            attribute_name="concept.authorization",
            operator="equals",
            expected_value=True,
            mapped_value=True,
            rationale="Evidence explicitly examines authorization.",
        ),

        MappingRule(
            dimension_id="authorization",
            attribute_name="concept.authorization",
            operator="equals",
            expected_value=False,
            mapped_value=False,
            rationale="Evidence explicitly does not examine authorization.",
        ),

        # ---------------------------------------------------------------------
        # Temporal behavior
        # ---------------------------------------------------------------------

        MappingRule(
            dimension_id="temporal_behavior",
            attribute_name="concept.temporal_behavior",
            operator="equals",
            expected_value=True,
            mapped_value=True,
        ),

        MappingRule(
            dimension_id="temporal_behavior",
            attribute_name="concept.temporal_behavior",
            operator="equals",
            expected_value=False,
            mapped_value=False,
        ),

        # ---------------------------------------------------------------------
        # Concurrency
        # ---------------------------------------------------------------------

        MappingRule(
            dimension_id="concurrency",
            attribute_name="concept.concurrency",
            operator="equals",
            expected_value=True,
            mapped_value=True,
        ),

        MappingRule(
            dimension_id="concurrency",
            attribute_name="concept.concurrency",
            operator="equals",
            expected_value=False,
            mapped_value=False,
        ),

        # ---------------------------------------------------------------------
        # Invariant preservation
        # ---------------------------------------------------------------------

        MappingRule(
            dimension_id="invariant_preservation",
            attribute_name="concept.invariant_preservation",
            operator="equals",
            expected_value=True,
            mapped_value=True,
        ),

        MappingRule(
            dimension_id="invariant_preservation",
            attribute_name="concept.invariant_preservation",
            operator="equals",
            expected_value=False,
            mapped_value=False,
        ),

        # ---------------------------------------------------------------------
        # Neighbor interaction
        # ---------------------------------------------------------------------

        MappingRule(
            dimension_id="neighbor_interaction",
            attribute_name="concept.neighbor_interaction",
            operator="equals",
            expected_value=True,
            mapped_value=True,
        ),

        MappingRule(
            dimension_id="neighbor_interaction",
            attribute_name="concept.neighbor_interaction",
            operator="equals",
            expected_value=False,
            mapped_value=False,
        ),
    )

    return rules


# =============================================================================
# END-TO-END POC EXAMPLE
# =============================================================================


def build_example_evidence_bundle() -> EvidenceBundle:
    """
    Small integration fixture containing:

    - independent evidence;
    - two descendants from one generated seed;
    - repeated normal behavior;
    - sparse boundary coverage;
    - no concurrency evidence;
    - no temporal evidence.

    This allows the POC to demonstrate lineage-aware counts and gaps.
    """

    candidate_change_id = "change_001"

    evidence = (

        EvidenceArtifact(
            evidence_id="ev_regression_001",
            candidate_change_id=candidate_change_id,
            evidence_type="regression_test",
            observation={
                "test": "existing regression suite",
                "result": "passed",
            },
            addressed_claims=(
                "existing behavior remains valid",
            ),
            addressed_behaviors=(
                "normal execution",
            ),
            method="existing_repository_test",
            producer_identity="pytest",
            result="pass",
            confidence=1.0,
            provenance="repository test suite",
            concept_hints={
                "behavior_type": "normal",
                "authorization": False,
                "temporal_behavior": False,
                "concurrency": False,
                "invariant_preservation": False,
                "neighbor_interaction": True,
            },
        ),

        EvidenceArtifact(
            evidence_id="ev_generated_seed",
            candidate_change_id=candidate_change_id,
            evidence_type="generated_behavioral_test",
            observation={
                "test": "boundary request test",
                "result": "passed",
            },
            addressed_claims=(
                "boundary input is handled",
            ),
            addressed_behaviors=(
                "boundary behavior",
            ),
            method="generated_test",
            producer_identity="test_generator_v1",
            result="pass",
            confidence=0.90,
            provenance="generated evidence",
            generation_batch_id="batch_001",
            concept_hints={
                "behavior_type": "boundary",
                "authorization": False,
                "temporal_behavior": False,
                "concurrency": False,
                "invariant_preservation": False,
                "neighbor_interaction": True,
            },
        ),

        EvidenceArtifact(
            evidence_id="ev_generated_descendant_1",
            candidate_change_id=candidate_change_id,
            evidence_type="generated_behavioral_test",
            observation={
                "test": "boundary request paraphrase one",
                "result": "passed",
            },
            addressed_claims=(
                "boundary input is handled",
            ),
            addressed_behaviors=(
                "boundary behavior",
            ),
            method="generated_test_mutation",
            producer_identity="test_generator_v1",
            result="pass",
            confidence=0.88,
            provenance="generated descendant",
            parent_evidence_ids=(
                "ev_generated_seed",
            ),
            generation_batch_id="batch_001",
            concept_hints={
                "behavior_type": "boundary",
                "authorization": False,
                "temporal_behavior": False,
                "concurrency": False,
                "invariant_preservation": False,
                "neighbor_interaction": True,
            },
        ),

        EvidenceArtifact(
            evidence_id="ev_generated_descendant_2",
            candidate_change_id=candidate_change_id,
            evidence_type="generated_behavioral_test",
            observation={
                "test": "boundary request paraphrase two",
                "result": "passed",
            },
            addressed_claims=(
                "boundary input is handled",
            ),
            addressed_behaviors=(
                "boundary behavior",
            ),
            method="generated_test_mutation",
            producer_identity="test_generator_v1",
            result="pass",
            confidence=0.87,
            provenance="generated descendant",
            parent_evidence_ids=(
                "ev_generated_seed",
            ),
            generation_batch_id="batch_001",
            concept_hints={
                "behavior_type": "boundary",
                "authorization": False,
                "temporal_behavior": False,
                "concurrency": False,
                "invariant_preservation": False,
                "neighbor_interaction": True,
            },
        ),

        EvidenceArtifact(
            evidence_id="ev_static_001",
            candidate_change_id=candidate_change_id,
            evidence_type="static_analysis",
            observation={
                "finding": "authorization path inspected",
                "result": "no violation",
            },
            addressed_claims=(
                "authorization behavior remains valid",
            ),
            addressed_behaviors=(
                "authorization",
            ),
            method="static_analysis",
            producer_identity="static_analyzer",
            result="pass",
            confidence=0.95,
            provenance="static analysis report",
            concept_hints={
                "behavior_type": "normal",
                "authorization": True,
                "temporal_behavior": False,
                "concurrency": False,
                "invariant_preservation": False,
                "neighbor_interaction": True,
            },
        ),
    )

    return EvidenceBundle(
        bundle_id="bundle_001",
        candidate_change_id=candidate_change_id,
        artifacts=evidence,
    )


def run_reference_poc() -> None:
    """
    Demonstrate exactly the client interaction pattern.

    The L1 client sees EvidenceDiversityMapperAdapter.

    It does not interact with GenericDiversityEngine directly.
    """

    # -------------------------------------------------------------------------
    # 1. Build / load a versioned ConceptSchema.
    # -------------------------------------------------------------------------

    schema = build_example_evidence_schema()

    # -------------------------------------------------------------------------
    # 2. Configure deterministic mapping.
    #
    # This is suitable as a test double and first POC integration.
    #
    # A later semantic mapper can replace this mapper without changing the
    # EvidenceDiversityMapperAdapter contract.
    # -------------------------------------------------------------------------

    rules = build_example_evidence_mapping_rules()

    deterministic_mapper = (
        RuleBasedArtifactConceptMapper(
            rules=rules,
            mapper_version=(
                UNIVERSAL_MAPPER_VERSION
            ),
        )
    )

    # -------------------------------------------------------------------------
    # 3. Instantiate the hidden generic engine.
    # -------------------------------------------------------------------------

    generic_engine = GenericDiversityEngine(
        concept_mapper=deterministic_mapper,
    )

    # -------------------------------------------------------------------------
    # 4. Expose only the evidence adapter to the internal L1 client.
    # -------------------------------------------------------------------------

    evidence_mapper = (
        EvidenceDiversityMapperAdapter(
            engine=generic_engine,
        )
    )

    # -------------------------------------------------------------------------
    # 5. Build a representative evidence bundle.
    # -------------------------------------------------------------------------

    evidence_bundle = (
        build_example_evidence_bundle()
    )

    # -------------------------------------------------------------------------
    # 6. EvidencePlanner communicates an explicit resource budget.
    # -------------------------------------------------------------------------

    budget = ResourceBudget(
        max_additional_artifacts=3,
        max_model_calls=3,
        token_budget=10_000,
        execution_budget=10,
        elapsed_time_budget_seconds=60.0,
        priority_dimension_ids=(
            "authorization",
            "concurrency",
            "temporal_behavior",
        ),
    )

    # -------------------------------------------------------------------------
    # 7. Client-facing call.
    #
    # Output contains:
    # - artifact mappings;
    # - uncertainty;
    # - coverage regions;
    # - lineage-aware support;
    # - structured gaps;
    # - budget-aware expansion requests.
    # -------------------------------------------------------------------------

    result = (
        evidence_mapper
        .assess_evidence_bundle(
            bundle=evidence_bundle,
            schema=schema,
            budget=budget,
        )
    )

    print(
        "\n=== CLIENT-FACING COVERAGE RESULT ==="
    )

    print(
        json.dumps(
            asdict(result),
            indent=2,
            default=str,
        )
    )

    # -------------------------------------------------------------------------
    # 8. Example outside-the-mapper collection/generation step.
    #
    # In the real L1 architecture, EvidencePlanner would select an evidence
    # collector. The Diversity Mapper does NOT make that decision.
    # -------------------------------------------------------------------------

    if not result.expansion_requests:

        print(
            "\nNo expansion requests were produced."
        )
        return

    first_request = (
        result.expansion_requests[0]
    )

    # This deterministic fixture represents evidence collected outside this
    # package. It records the ExpansionRequest that motivated its collection.
    generated_evidence = EvidenceArtifact(
        evidence_id="ev_expansion_result_001",
        candidate_change_id=(
            evidence_bundle
            .candidate_change_id
        ),
        evidence_type="generated_behavioral_test",
        observation={
            "test": (
                "new evidence collected for requested "
                "conceptual characteristic"
            ),
            "result": "passed",
        },
        addressed_claims=(
            "requested gap is investigated",
        ),
        addressed_behaviors=(
            "coverage-guided evidence",
        ),
        method="external_evidence_collector",
        producer_identity="evidence_planner_selected_collector",
        result="pass",
        confidence=0.90,
        provenance="external evidence acquisition",
        concept_hints=dict(
            first_request
            .requested_characteristics
        ),
        metadata={
            "expansion_request_id":
                first_request.request_id,
        },
    )

    # -------------------------------------------------------------------------
    # 9. Closed measurement loop.
    #
    # The mapper independently maps the new evidence.
    #
    # It does not trust generator intent.
    # -------------------------------------------------------------------------

    expansion_assessments = (
        evidence_mapper
        .assess_generated_evidence(
            generated_evidence=(
                generated_evidence,
            ),
            requests=(
                first_request,
            ),
            schema=schema,
        )
    )

    print(
        "\n=== EXPANSION ASSESSMENT ==="
    )

    print(
        json.dumps(
            [
                asdict(item)
                for item
                in expansion_assessments
            ],
            indent=2,
            default=str,
        )
    )

    # -------------------------------------------------------------------------
    # 10. Mapper operational observability.
    # -------------------------------------------------------------------------

    print(
        "\n=== MAPPER OBSERVABILITY ==="
    )

    print(
        json.dumps(
            {
                **asdict(
                    generic_engine.metrics
                ),
                "expansion_acceptance_rate":
                    generic_engine.metrics
                    .expansion_acceptance_rate(),
            },
            indent=2,
            default=str,
        )
    )


# =============================================================================
# ARCHITECTURAL JUDGMENT SUMMARY
# =============================================================================
#
# RECOMMENDATION:
#
# Keep the fundamental engine generic.
#
# BUT:
#
# Do not expose genericity as a burden to the evidence client.
#
# The correct boundary is:
#
#     Generic core:
#         ConceptSchema
#         ArtifactDescriptor
#         ConceptMapping
#         CoverageRegion
#         CoverageAssessment
#         CoverageGap
#         ExpansionRequest
#         ExpansionCandidate
#         ExpansionAssessment
#         uncertainty
#         lineage
#         duplication
#         budgets
#         observability
#
#     Evidence adapter:
#         EvidenceArtifact
#         EvidenceBundle
#         EvidenceCoverageGap
#         EvidenceExpansionRequest
#         EvidenceCoverageResult
#         evidence-to-generic translation
#
#     Outside this package:
#         EvidencePlanner
#         evidence collectors
#         generated tests
#         mutation execution
#         static-analysis execution
#         ReleaseGateService
#         GatePolicy
#         PASS / FAIL / HUMAN_REVIEW_REQUIRED
#
# WHY THIS IS THE BEST BALANCE:
#
# 1. Nearly every major requirement in the client's message is actually
#    domain-neutral:
#
#       schemas
#       mapping
#       coverage
#       gaps
#       uncertainty
#       lineage
#       duplicates
#       expansion requests
#       re-mapping
#       budgets
#       reproducibility
#       observability
#
# 2. The things that are genuinely evidence-specific are comparatively thin:
#
#       what an EvidenceArtifact contains;
#       how evidence metadata becomes generic artifact metadata;
#       which ConceptSchema applies to code-change evidence;
#       how generic gaps are expressed to EvidencePlanner.
#
# 3. Making the entire engine evidence-specific would duplicate the same
#    concepts later for prompt datasets, codebase libraries, QA datasets, and
#    evaluation corpora.
#
# 4. Making the client consume a generic API directly would create unnecessary
#    integration complexity and leak product-line implementation decisions.
#
# 5. The adapter therefore provides a stable anti-corruption boundary:
#
#       client semantics remain evidence semantics;
#       core semantics remain artifact/diversity semantics.
#
# 6. This architecture also lets the product team independently improve:
#
#       semantic mapping;
#       concept discovery;
#       density estimation;
#       clustering;
#       graph-based coverage;
#       embeddings;
#       LLM integration;
#
#    without requiring ReleaseGateService or EvidencePlanner to change.
#
# 7. Most importantly, the package preserves the client's central principle:
#
#       conceptual coverage is descriptive evidence about an artifact
#       collection, not a release decision.
#
# FIRST POC RECOMMENDATION:
#
# Begin with:
#
#     human-reviewed ConceptSchema
#         +
#     deterministic mapping/test doubles
#         +
#     explicit UNKNOWN states
#         +
#     lineage-aware coverage
#         +
#     structured gaps
#         +
#     budget-aware expansion requests
#         +
#     independent re-mapping of newly collected evidence.
#
# Add LLM concept discovery and LLM semantic mapping only after the deterministic
# integration contract is working and the team has a benchmark corpus against
# which the model-based components can be evaluated.
#
# This reduces the chance that an impressive-looking taxonomy becomes an
# unvalidated dependency of the release-assurance process.
# =============================================================================


if __name__ == "__main__":
    run_reference_poc()
