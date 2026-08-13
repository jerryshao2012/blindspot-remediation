"""
Minimum smoke tests for the reference implementation.

These tests check the Initial Success Criteria listed in README.md section 46.
They do not test new behaviour and they do not change the design.

No external model is required. The deterministic mapper is used throughout.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import E1_evidence_diversity_mapper_reference as edmr  # noqa: E402


def build_stack():
    """Build the schema, the deterministic mapper, the engine, and the adapter."""

    schema = edmr.build_example_evidence_schema()

    mapper = edmr.RuleBasedArtifactConceptMapper(
        rules=edmr.build_example_evidence_mapping_rules(),
    )

    engine = edmr.GenericDiversityEngine(concept_mapper=mapper)

    adapter = edmr.EvidenceDiversityMapperAdapter(engine=engine)

    return schema, engine, adapter


def test_schema_validates():
    """Criterion 2: the example schema is a valid versioned ConceptSchema."""

    schema = edmr.build_example_evidence_schema()
    schema.validate()

    assert schema.schema_version == edmr.UNIVERSAL_SCHEMA_VERSION
    assert len(schema.dimensions) == 6


def test_bundle_is_assessed_end_to_end():
    """Criteria 1, 8, 9, 10, 12: a bundle produces regions, gaps, and requests."""

    schema, engine, adapter = build_stack()

    bundle = edmr.build_example_evidence_bundle()

    budget = edmr.ResourceBudget(
        max_additional_artifacts=3,
        max_model_calls=3,
    )

    result = adapter.assess_evidence_bundle(
        bundle=bundle,
        schema=schema,
        budget=budget,
    )

    assert len(result.artifact_mappings) == 5
    assert result.coverage_regions
    assert result.coverage_gaps
    assert result.expansion_requests


def test_lineage_aware_count_is_lower_than_raw_count():
    """Criterion 7 and 8: three boundary artifacts share one lineage root."""

    schema, engine, adapter = build_stack()

    bundle = edmr.build_example_evidence_bundle()

    budget = edmr.ResourceBudget()

    result = adapter.assess_evidence_bundle(
        bundle=bundle,
        schema=schema,
        budget=budget,
    )

    boundary_regions = [
        region
        for region in result.coverage_regions
        if region.coordinates == (("behavior_type", "boundary"),)
    ]

    assert len(boundary_regions) == 1

    region = boundary_regions[0]

    # One seed plus two descendants.
    assert region.raw_artifact_count == 3

    # The descendants trace back to the same root, so they are not counted
    # as three independent observations.
    assert region.lineage_aware_count == 1


def test_absent_region_is_detected():
    """Criterion 9: concurrency is absent from the example bundle."""

    schema, engine, adapter = build_stack()

    result = adapter.assess_evidence_bundle(
        bundle=edmr.build_example_evidence_bundle(),
        schema=schema,
        budget=edmr.ResourceBudget(),
    )

    concurrency_true = [
        region
        for region in result.coverage_regions
        if region.coordinates == (("concurrency", True),)
    ]

    assert len(concurrency_true) == 1
    assert concurrency_true[0].status is edmr.RegionStatus.ABSENT


def test_unknown_state_is_preserved():
    """Criterion 3: a missing hint becomes UNKNOWN, not False."""

    schema, engine, adapter = build_stack()

    artifact = edmr.ArtifactDescriptor(
        artifact_id="artifact_without_hints",
        artifact_type="generated_behavioral_test",
        payload={"test": "no concept hints supplied"},
        attributes={},
        lineage=edmr.ArtifactLineage(),
        provenance="unit test",
    )

    mapping = engine.concept_mapper.map_artifact(artifact, schema)

    concurrency = mapping.mapping_for("concurrency")

    assert concurrency.status is edmr.MappingStatus.UNKNOWN
    assert concurrency.value == edmr.UNIVERSAL_UNKNOWN_VALUE
    assert concurrency.value is not False


def test_budget_of_zero_produces_no_requests():
    """Criterion 11: the caller budget is respected."""

    schema, engine, adapter = build_stack()

    result = adapter.assess_evidence_bundle(
        bundle=edmr.build_example_evidence_bundle(),
        schema=schema,
        budget=edmr.ResourceBudget(max_additional_artifacts=0),
    )

    assert result.expansion_requests == ()


def test_llm_mapper_still_raises_not_implemented():
    """The unknown integration must stay explicit. It must not be a placeholder."""

    schema = edmr.build_example_evidence_schema()

    artifact = edmr.ArtifactDescriptor(
        artifact_id="artifact_for_llm",
        artifact_type="generated_behavioral_test",
        payload={},
        attributes={},
        lineage=edmr.ArtifactLineage(),
        provenance="unit test",
    )

    mapper = edmr.LLMArtifactConceptMapper()

    try:
        mapper.map_artifact(artifact, schema)
    except NotImplementedError:
        return

    raise AssertionError("LLMArtifactConceptMapper must raise NotImplementedError.")


def test_reference_poc_runs():
    """Criterion 16 and 17: the end-to-end example executes."""

    edmr.run_reference_poc()
