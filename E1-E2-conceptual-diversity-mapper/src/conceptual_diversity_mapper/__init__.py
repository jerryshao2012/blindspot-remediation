"""
evidence_diversity_mapper_reference.py
======================================

REFERENCE ARCHITECTURE
----------------------

This file implements a domain-neutral Conceptual Diversity Engine underneath
an evidence-specific client-facing adapter.

The key architectural decision is:

    CLIENT / L1 ENGINEERING AUTOMATION
                    |
                    | EvidenceArtifact
                    | EvidenceBundle
                    | EvidenceCoverageAssessment
                    | EvidenceCoverageGap
                    | EvidenceExpansionRequest
                    v
        EvidenceDiversityMapperAdapter
                    |
                    | translates domain contracts
                    v
         GenericDiversityEngine
                    |
        +-----------+------------+
        |           |            |
    Mapping      Coverage      Expansion
        |           |            |
        +-----------+------------+

The internal generic engine is intentionally invisible to the L1 client.

WHY THIS BOUNDARY
-----------------

The client's requirements describe a reusable Diversity Mapper product that
must support multiple artifact domains while preserving an evidence-specific
integration surface for the L1 automation project.

Therefore:

1. ConceptSchema, conceptual mapping, coverage analysis, gap identification,
   uncertainty, lineage, duplication, budgets, and expansion assessment are
   implemented generically.

2. EvidenceArtifact, EvidenceBundle, and the translation between evidence
   concepts and generic artifact contracts live in an evidence adapter.

3. ReleaseGateService, PASS/FAIL/HUMAN_REVIEW_REQUIRED, test execution,
   mutation execution, and code generation are deliberately NOT part of this
   package.

4. The generic core is replaceable without changing the evidence-facing API.

5. The generic engine is based on ports/adapters dependency inversion:
   domain-specific logic is injected through explicit interfaces rather than
   imported into the core.

IMPLEMENTATION STATUS
---------------------

This file provides a runnable deterministic reference implementation of:

- versioned concept schemas;
- categorical, ordinal, continuous, boolean, and multi-label dimensions;
- artifact descriptors;
- provenance and lineage;
- concept mappings;
- UNKNOWN / UNRESOLVED mappings;
- mapping uncertainty;
- exact duplicate detection;
- conceptual duplicate detection;
- lineage-aware support counts;
- coverage-region construction;
- sparse / absent / repeated / uncertain region detection;
- structured CoverageGap objects;
- resource budgets;
- budget-aware ExpansionRequests;
- expansion candidate re-mapping;
- expansion assessment;
- observability counters;
- evidence-domain adapter;
- deterministic test doubles;
- an end-to-end example.

Integrations whose runtime parameters cannot be known here explicitly raise
NotImplementedError. There are no silent placeholders or TODO implementations.

Python requirement:
    Python 3.11+

Third-party dependencies:
    None.

The reference implementation intentionally uses only the Python standard
library so the product contracts can be evaluated independently of a chosen
LLM, embedding model, vector database, or clustering library.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid

from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


# =============================================================================
# UNIVERSAL PRODUCT CONSTANTS
# =============================================================================
#
# These constants contain defaults that are genuinely product-level defaults.
# They are not placeholders for unknown implementation parameters.
#
# Environment-specific items such as model endpoints, credentials, deployment
# names, or proprietary tool parameters must be supplied through explicit
# adapters. Unknown integrations raise NotImplementedError instead of hiding
# fake values here.
# =============================================================================


UNIVERSAL_SCHEMA_VERSION = "1.0.0"
UNIVERSAL_MAPPER_VERSION = "1.0.0"

UNIVERSAL_UNKNOWN_CONFIDENCE = 0.0
UNIVERSAL_DEFAULT_MAPPING_CONFIDENCE = 1.0

UNIVERSAL_SPARSE_SUPPORT_RATIO = 0.20
UNIVERSAL_REPEATED_SUPPORT_RATIO = 0.70
UNIVERSAL_UNCERTAINTY_THRESHOLD = 0.60

UNIVERSAL_CONTINUOUS_BUCKET_COUNT = 5

UNIVERSAL_MAX_LINEAGE_DEPTH = 100

UNIVERSAL_DEFAULT_MAX_ADDITIONAL_ARTIFACTS = 100
UNIVERSAL_DEFAULT_MAX_MODEL_CALLS = 100
UNIVERSAL_DEFAULT_TOKEN_BUDGET = 100_000
UNIVERSAL_DEFAULT_EXECUTION_BUDGET = 1_000
UNIVERSAL_DEFAULT_ELAPSED_TIME_SECONDS = 3_600.0

UNIVERSAL_FLOAT_COMPARISON_TOLERANCE = 1e-9

UNIVERSAL_UNKNOWN_VALUE = "__UNKNOWN__"
UNIVERSAL_UNRESOLVED_VALUE = "__UNRESOLVED__"
UNIVERSAL_ABSENT_VALUE = "__ABSENT__"


# =============================================================================
# GENERAL UTILITIES
# =============================================================================


def utc_now_iso() -> str:
    """Return a stable ISO-8601 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: Any) -> str:
    """
    Produce a deterministic SHA-256 hash for JSON-serializable content.

    JSON keys are sorted so semantically identical dictionaries hash the same
    regardless of insertion order.
    """

    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def new_id(prefix: str) -> str:
    """Create a human-readable unique identifier."""

    return f"{prefix}_{uuid.uuid4().hex}"


def bounded(value: float, minimum: float, maximum: float) -> float:
    """Clamp a numeric value into a closed interval."""

    return max(minimum, min(maximum, value))


# =============================================================================
# PRODUCT ENUMERATIONS
# =============================================================================


class DimensionType(str, Enum):
    """Supported conceptual dimension types."""

    BOOLEAN = "boolean"
    CATEGORICAL = "categorical"
    ORDINAL = "ordinal"
    CONTINUOUS = "continuous"
    MULTI_LABEL = "multi_label"


class MappingStatus(str, Enum):
    """
    Mapping state.

    UNKNOWN:
        The mapper has insufficient information.

    UNRESOLVED:
        Evidence exists but mapping methods disagree or remain ambiguous.

    MAPPED:
        A mapping was produced with explicit confidence.

    UNSUPPORTED:
        The artifact type or requested dimension is unsupported by the mapper.
    """

    MAPPED = "mapped"
    UNKNOWN = "unknown"
    UNRESOLVED = "unresolved"
    UNSUPPORTED = "unsupported"


class RegionStatus(str, Enum):
    """Coverage status for a conceptual region."""

    REPRESENTED = "represented"
    SPARSE = "sparse"
    ABSENT = "absent"
    HIGHLY_REPEATED = "highly_repeated"
    UNCERTAIN = "uncertain"


class ExpansionCandidateStatus(str, Enum):
    """Assessment state for newly produced artifacts."""

    SATISFIED_REQUEST = "satisfied_request"
    PARTIALLY_SATISFIED = "partially_satisfied"
    DID_NOT_SATISFY = "did_not_satisfy"
    UNRESOLVED = "unresolved"


class FailureType(str, Enum):
    """
    Explicit operational failure semantics.

    Infrastructure failures must never silently become "no diversity."
    """

    MAPPER_UNAVAILABLE = "mapper_unavailable"
    MODEL_UNAVAILABLE = "model_unavailable"
    MALFORMED_MODEL_OUTPUT = "malformed_model_output"
    UNSUPPORTED_ARTIFACT = "unsupported_artifact"
    INVALID_SCHEMA = "invalid_schema"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    PARTIAL_MAPPING = "partial_mapping"


class DerivationMethod(str, Enum):
    """How a concept dimension entered a schema."""

    HUMAN_DEFINED = "human_defined"
    EXISTING_TAXONOMY = "existing_taxonomy"
    TASK_SPECIFICATION = "task_specification"
    LLM_DISCOVERED = "llm_discovered"
    EMPIRICAL_CLUSTER = "empirical_cluster"
    OBSERVED_FAILURE = "observed_failure"
    KNOWN_RISK_CATEGORY = "known_risk_category"
    HYBRID = "hybrid"


# =============================================================================
# VERSIONED CONCEPT SCHEMA
# =============================================================================


@dataclass(frozen=True)
class ConceptDimension:
    """
    One interpretable conceptual dimension.

    Examples in the evidence domain might include:

        behavior_type
        authorization_state
        dependency_failure
        temporal_behavior
        invariant_preservation

    The generic engine does not know what these mean. It only knows the
    dimension's declared semantics and type.
    """

    dimension_id: str
    name: str
    definition: str
    rationale: str
    dimension_type: DimensionType

    allowed_values: tuple[Any, ...] = ()
    ordinal_order: tuple[Any, ...] = ()

    minimum_value: float | None = None
    maximum_value: float | None = None

    examples: tuple[str, ...] = ()
    counterexamples: tuple[str, ...] = ()

    derivation_method: DerivationMethod = DerivationMethod.HUMAN_DEFINED
    provenance: str = ""

    maturity_confidence: float = 1.0

    def validate(self) -> None:
        """Validate dimension semantics before a schema can be used."""

        if not self.dimension_id.strip():
            raise ValueError("dimension_id cannot be empty.")

        if not self.name.strip():
            raise ValueError("ConceptDimension.name cannot be empty.")

        if not self.definition.strip():
            raise ValueError(
                f"Dimension {self.dimension_id!r} requires a definition."
            )

        if not 0.0 <= self.maturity_confidence <= 1.0:
            raise ValueError(
                "maturity_confidence must be between 0 and 1."
            )

        if self.dimension_type == DimensionType.CATEGORICAL:
            if not self.allowed_values:
                raise ValueError(
                    f"Categorical dimension {self.name!r} requires "
                    "allowed_values."
                )

        if self.dimension_type == DimensionType.ORDINAL:
            if not self.ordinal_order:
                raise ValueError(
                    f"Ordinal dimension {self.name!r} requires "
                    "ordinal_order."
                )

        if self.dimension_type == DimensionType.CONTINUOUS:
            if (
                self.minimum_value is None
                or self.maximum_value is None
            ):
                raise ValueError(
                    f"Continuous dimension {self.name!r} requires "
                    "minimum_value and maximum_value."
                )

            if self.minimum_value >= self.maximum_value:
                raise ValueError(
                    f"Continuous dimension {self.name!r} has invalid range."
                )


@dataclass(frozen=True)
class ConceptSchema:
    """
    First-class, immutable, versioned concept schema.

    Historical assessments must retain the schema identity used when they were
    produced.
    """

    schema_id: str
    schema_version: str
    dimensions: tuple[ConceptDimension, ...]

    derivation_method: DerivationMethod
    provenance: str

    source_dataset_id: str | None = None
    created_at: str = field(default_factory=utc_now_iso)

    model_versions: tuple[str, ...] = ()
    tool_versions: tuple[str, ...] = ()

    human_review_status: str = "unreviewed"

    def validate(self) -> None:
        """Validate schema integrity and uniqueness."""

        if not self.schema_id.strip():
            raise ValueError("ConceptSchema.schema_id cannot be empty.")

        if not self.schema_version.strip():
            raise ValueError(
                "ConceptSchema.schema_version cannot be empty."
            )

        if not self.dimensions:
            raise ValueError(
                "ConceptSchema must contain at least one dimension."
            )

        ids = [dimension.dimension_id for dimension in self.dimensions]

        if len(ids) != len(set(ids)):
            raise ValueError(
                "ConceptSchema contains duplicate dimension IDs."
            )

        for dimension in self.dimensions:
            dimension.validate()

    def dimension_by_id(
        self,
        dimension_id: str,
    ) -> ConceptDimension:
        """Resolve one dimension by stable ID."""

        for dimension in self.dimensions:
            if dimension.dimension_id == dimension_id:
                return dimension

        raise KeyError(
            f"Unknown dimension_id {dimension_id!r} "
            f"in schema {self.schema_id}:{self.schema_version}."
        )


# =============================================================================
# PROVENANCE AND LINEAGE
# =============================================================================


@dataclass(frozen=True)
class ArtifactLineage:
    """
    Lineage information required to avoid counting descendants as independent
    evidence automatically.
    """

    parent_artifact_ids: tuple[str, ...] = ()
    generation_batch_id: str | None = None

    generator_identity: str | None = None
    model_identity: str | None = None

    prompt_template_identity: str | None = None
    source_method: str | None = None

    transformation_history: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtifactDescriptor:
    """
    Generic domain-neutral artifact consumed by the core engine.

    payload:
        Artifact content or structured information.

    attributes:
        Explicit machine-readable metadata available to mapping strategies.

    content_hash:
        Used for exact duplicate detection.

    lineage:
        Used for lineage-aware support calculations.
    """

    artifact_id: str
    artifact_type: str

    payload: Any
    attributes: Mapping[str, Any]

    lineage: ArtifactLineage

    provenance: str
    created_at: str = field(default_factory=utc_now_iso)

    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            object.__setattr__(
                self,
                "content_hash",
                stable_hash(self.payload),
            )


# =============================================================================
# CONCEPT MAPPING
# =============================================================================


@dataclass(frozen=True)
class DimensionMapping:
    """Mapping result for one artifact against one dimension."""

    dimension_id: str

    status: MappingStatus
    value: Any

    confidence: float

    method: str
    rationale: str

    uncertainty_reason: str | None = None

    def validate(
        self,
        dimension: ConceptDimension,
    ) -> None:
        """Validate mapping output against the schema definition."""

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Mapping confidence for {self.dimension_id!r} "
                "must be between 0 and 1."
            )

        if self.status != MappingStatus.MAPPED:
            return

        if dimension.dimension_type == DimensionType.BOOLEAN:
            if not isinstance(self.value, bool):
                raise ValueError(
                    f"Dimension {dimension.name!r} requires bool."
                )

        elif dimension.dimension_type == DimensionType.CATEGORICAL:
            if self.value not in dimension.allowed_values:
                raise ValueError(
                    f"Value {self.value!r} is invalid for "
                    f"{dimension.name!r}."
                )

        elif dimension.dimension_type == DimensionType.ORDINAL:
            if self.value not in dimension.ordinal_order:
                raise ValueError(
                    f"Value {self.value!r} is invalid for "
                    f"{dimension.name!r}."
                )

        elif dimension.dimension_type == DimensionType.CONTINUOUS:
            if not isinstance(self.value, (int, float)):
                raise ValueError(
                    f"Dimension {dimension.name!r} requires numeric value."
                )

            assert dimension.minimum_value is not None
            assert dimension.maximum_value is not None

            if not (
                dimension.minimum_value
                <= float(self.value)
                <= dimension.maximum_value
            ):
                raise ValueError(
                    f"Value {self.value!r} outside range for "
                    f"{dimension.name!r}."
                )

        elif dimension.dimension_type == DimensionType.MULTI_LABEL:
            if not isinstance(
                self.value,
                (tuple, list, set, frozenset),
            ):
                raise ValueError(
                    f"Dimension {dimension.name!r} requires a collection."
                )

            if dimension.allowed_values:
                invalid_values = (
                    set(self.value)
                    - set(dimension.allowed_values)
                )

                if invalid_values:
                    raise ValueError(
                        f"Invalid values for {dimension.name!r}: "
                        f"{sorted(invalid_values)}"
                    )


@dataclass(frozen=True)
class ConceptMapping:
    """Complete artifact-to-schema mapping."""

    mapping_id: str

    artifact_id: str

    schema_id: str
    schema_version: str

    mapper_version: str

    dimension_mappings: tuple[DimensionMapping, ...]

    created_at: str = field(default_factory=utc_now_iso)

    configuration_hash: str = ""

    def mapping_for(
        self,
        dimension_id: str,
    ) -> DimensionMapping:
        """Retrieve mapping for one dimension."""

        for mapping in self.dimension_mappings:
            if mapping.dimension_id == dimension_id:
                return mapping

        raise KeyError(
            f"No mapping available for dimension {dimension_id!r}."
        )


# =============================================================================
# MAPPING PORT
# =============================================================================


class ArtifactConceptMapperPort(ABC):
    """
    Port used by the generic engine to map artifacts.

    Domain-specific implementations may use:

    - deterministic rules;
    - statistical classifiers;
    - embeddings;
    - LLMs;
    - static analysis;
    - multiple methods with adjudication.

    The core only requires stable ConceptMapping output.
    """

    @abstractmethod
    def map_artifact(
        self,
        artifact: ArtifactDescriptor,
        schema: ConceptSchema,
    ) -> ConceptMapping:
        """Map one artifact into the supplied schema."""


# =============================================================================
# GENERIC DETERMINISTIC MAPPER
# =============================================================================


@dataclass(frozen=True)
class MappingRule:
    """
    Generic declarative mapping rule.

    The rule examines ArtifactDescriptor.attributes.

    supported operators:
        equals
        contains
        exists
        greater_than
        less_than

    mapped_value:
        Value assigned to the concept dimension when the rule matches.
    """

    dimension_id: str

    attribute_name: str
    operator: str
    expected_value: Any

    mapped_value: Any

    confidence: float = UNIVERSAL_DEFAULT_MAPPING_CONFIDENCE

    rationale: str = ""


class RuleBasedArtifactConceptMapper(
    ArtifactConceptMapperPort
):
    """
    Fully implemented generic rule-based mapper.

    This mapper is deliberately domain-neutral.

    Evidence-specific rules can be supplied by the evidence adapter without
    importing evidence-domain classes into the generic engine.
    """

    SUPPORTED_OPERATORS = {
        "equals",
        "contains",
        "exists",
        "greater_than",
        "less_than",
    }

    def __init__(
        self,
        rules: Sequence[MappingRule],
        mapper_version: str = UNIVERSAL_MAPPER_VERSION,
    ) -> None:
        self.rules = tuple(rules)
        self.mapper_version = mapper_version

        for rule in self.rules:
            if rule.operator not in self.SUPPORTED_OPERATORS:
                raise ValueError(
                    f"Unsupported rule operator {rule.operator!r}."
                )

            if not 0.0 <= rule.confidence <= 1.0:
                raise ValueError(
                    "Rule confidence must be between 0 and 1."
                )

    def map_artifact(
        self,
        artifact: ArtifactDescriptor,
        schema: ConceptSchema,
    ) -> ConceptMapping:

        schema.validate()

        rules_by_dimension: dict[
            str,
            list[MappingRule],
        ] = defaultdict(list)

        for rule in self.rules:
            rules_by_dimension[
                rule.dimension_id
            ].append(rule)

        mappings: list[DimensionMapping] = []

        for dimension in schema.dimensions:

            matching_rules: list[MappingRule] = []

            for rule in rules_by_dimension.get(
                dimension.dimension_id,
                [],
            ):
                if self._rule_matches(rule, artifact.attributes):
                    matching_rules.append(rule)

            if not matching_rules:
                mappings.append(
                    DimensionMapping(
                        dimension_id=dimension.dimension_id,
                        status=MappingStatus.UNKNOWN,
                        value=UNIVERSAL_UNKNOWN_VALUE,
                        confidence=UNIVERSAL_UNKNOWN_CONFIDENCE,
                        method=self.__class__.__name__,
                        rationale=(
                            "No deterministic rule produced sufficient "
                            "evidence for this dimension."
                        ),
                        uncertainty_reason=(
                            "Insufficient explicit artifact metadata."
                        ),
                    )
                )
                continue

            distinct_values = {
                self._canonical_value(rule.mapped_value)
                for rule in matching_rules
            }

            if len(distinct_values) > 1:
                mappings.append(
                    DimensionMapping(
                        dimension_id=dimension.dimension_id,
                        status=MappingStatus.UNRESOLVED,
                        value=UNIVERSAL_UNRESOLVED_VALUE,
                        confidence=min(
                            rule.confidence
                            for rule in matching_rules
                        ),
                        method=self.__class__.__name__,
                        rationale=(
                            "Multiple valid rules produced conflicting "
                            "values."
                        ),
                        uncertainty_reason=(
                            "Rule disagreement requires adjudication."
                        ),
                    )
                )
                continue

            best_rule = max(
                matching_rules,
                key=lambda item: item.confidence,
            )

            mapping = DimensionMapping(
                dimension_id=dimension.dimension_id,
                status=MappingStatus.MAPPED,
                value=best_rule.mapped_value,
                confidence=best_rule.confidence,
                method=self.__class__.__name__,
                rationale=(
                    best_rule.rationale
                    or "Matched deterministic mapping rule."
                ),
            )

            mapping.validate(dimension)
            mappings.append(mapping)

        configuration_hash = stable_hash(
            {
                "mapper_version": self.mapper_version,
                "rules": [
                    asdict(rule)
                    for rule in self.rules
                ],
            }
        )

        return ConceptMapping(
            mapping_id=new_id("mapping"),
            artifact_id=artifact.artifact_id,
            schema_id=schema.schema_id,
            schema_version=schema.schema_version,
            mapper_version=self.mapper_version,
            dimension_mappings=tuple(mappings),
            configuration_hash=configuration_hash,
        )

    @staticmethod
    def _canonical_value(value: Any) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            default=str,
        )

    def _rule_matches(
        self,
        rule: MappingRule,
        attributes: Mapping[str, Any],
    ) -> bool:

        present = rule.attribute_name in attributes

        if rule.operator == "exists":
            return present == bool(rule.expected_value)

        if not present:
            return False

        actual_value = attributes[rule.attribute_name]

        if rule.operator == "equals":
            return actual_value == rule.expected_value

        if rule.operator == "contains":
            if isinstance(
                actual_value,
                (list, tuple, set, frozenset),
            ):
                return rule.expected_value in actual_value

            if isinstance(actual_value, str):
                return str(rule.expected_value) in actual_value

            return False

        if rule.operator == "greater_than":
            return (
                isinstance(actual_value, (int, float))
                and actual_value > rule.expected_value
            )

        if rule.operator == "less_than":
            return (
                isinstance(actual_value, (int, float))
                and actual_value < rule.expected_value
            )

        raise RuntimeError(
            f"Unhandled rule operator {rule.operator!r}."
        )


# =============================================================================
# OPTIONAL SEMANTIC MAPPERS
# =============================================================================


class LLMArtifactConceptMapper(
    ArtifactConceptMapperPort
):
    """
    Extension port for an LLM-backed mapper.

    This cannot be responsibly implemented without knowing:

    - approved provider;
    - endpoint;
    - authentication;
    - deployment/model;
    - schema enforcement mechanism;
    - retry policy;
    - timeout;
    - token limits;
    - data-retention requirements;
    - logging/redaction requirements.

    It therefore explicitly raises NotImplementedError.
    """

    def map_artifact(
        self,
        artifact: ArtifactDescriptor,
        schema: ConceptSchema,
    ) -> ConceptMapping:
        raise NotImplementedError(
            "Connect LLMArtifactConceptMapper to the organization's "
            "approved schema-constrained model client."
        )


class ConceptDiscoveryPort(ABC):
    """
    Optional concept-discovery capability.

    Concept discovery proposes candidate dimensions. It does not automatically
    promote them into an approved production schema.
    """

    @abstractmethod
    def discover(
        self,
        artifacts: Sequence[ArtifactDescriptor],
    ) -> tuple[ConceptDimension, ...]:
        """Propose interpretable candidate dimensions."""


class LLMConceptDiscoveryStrategy(
    ConceptDiscoveryPort
):
    """Organization-specific LLM discovery integration."""

    def discover(
        self,
        artifacts: Sequence[ArtifactDescriptor],
    ) -> tuple[ConceptDimension, ...]:
        raise NotImplementedError(
            "Implement with an approved LLM and schema-constrained "
            "concept-discovery contract."
        )


# =============================================================================
# DUPLICATION AND LINEAGE
# =============================================================================


@dataclass(frozen=True)
class DuplicationAssessment:
    """Duplication information for one artifact."""

    artifact_id: str

    exact_duplicate_of: tuple[str, ...]
    conceptual_duplicate_of: tuple[str, ...]

    lineage_root_ids: tuple[str, ...]


class DuplicateAnalyzer:
    """
    Detect exact and conceptual duplicates.

    Exact duplicates:
        Same content hash.

    Conceptual duplicates:
        Same normalized mapped conceptual signature.

    This intentionally does NOT equate embedding distance with conceptual
    duplication.
    """

    def analyze(
        self,
        artifacts: Sequence[ArtifactDescriptor],
        mappings: Sequence[ConceptMapping],
    ) -> tuple[DuplicationAssessment, ...]:

        artifact_lookup = {
            artifact.artifact_id: artifact
            for artifact in artifacts
        }

        mapping_lookup = {
            mapping.artifact_id: mapping
            for mapping in mappings
        }

        hashes: dict[str, list[str]] = defaultdict(list)

        for artifact in artifacts:
            hashes[artifact.content_hash].append(
                artifact.artifact_id
            )

        signatures: dict[str, list[str]] = defaultdict(list)

        for mapping in mappings:
            signature = self._mapping_signature(mapping)
            signatures[signature].append(mapping.artifact_id)

        parent_lookup = {
            artifact.artifact_id:
            artifact.lineage.parent_artifact_ids
            for artifact in artifacts
        }

        assessments: list[DuplicationAssessment] = []

        for artifact in artifacts:

            mapping = mapping_lookup.get(
                artifact.artifact_id
            )

            exact_duplicates = tuple(
                other_id
                for other_id in hashes[
                    artifact.content_hash
                ]
                if other_id != artifact.artifact_id
            )

            conceptual_duplicates: tuple[str, ...] = ()

            if mapping is not None:
                signature = self._mapping_signature(mapping)

                conceptual_duplicates = tuple(
                    other_id
                    for other_id in signatures[signature]
                    if other_id != artifact.artifact_id
                )

            roots = tuple(
                sorted(
                    self._lineage_roots(
                        artifact.artifact_id,
                        parent_lookup,
                    )
                )
            )

            assessments.append(
                DuplicationAssessment(
                    artifact_id=artifact.artifact_id,
                    exact_duplicate_of=exact_duplicates,
                    conceptual_duplicate_of=conceptual_duplicates,
                    lineage_root_ids=roots,
                )
            )

        return tuple(assessments)

    @staticmethod
    def _mapping_signature(
        mapping: ConceptMapping,
    ) -> str:

        signature_payload = []

        for dimension_mapping in sorted(
            mapping.dimension_mappings,
            key=lambda item: item.dimension_id,
        ):
            if (
                dimension_mapping.status
                != MappingStatus.MAPPED
            ):
                continue

            signature_payload.append(
                (
                    dimension_mapping.dimension_id,
                    dimension_mapping.value,
                )
            )

        return stable_hash(signature_payload)

    def _lineage_roots(
        self,
        artifact_id: str,
        parent_lookup: Mapping[
            str,
            tuple[str, ...],
        ],
    ) -> set[str]:

        roots: set[str] = set()
        visited: set[str] = set()

        frontier = [(artifact_id, 0)]

        while frontier:

            current_id, depth = frontier.pop()

            if depth > UNIVERSAL_MAX_LINEAGE_DEPTH:
                raise RuntimeError(
                    "Maximum lineage depth exceeded. "
                    "Possible lineage cycle."
                )

            if current_id in visited:
                continue

            visited.add(current_id)

            parents = parent_lookup.get(current_id, ())

            if not parents:
                roots.add(current_id)
                continue

            for parent_id in parents:
                frontier.append(
                    (parent_id, depth + 1)
                )

        return roots


# =============================================================================
# COVERAGE REPRESENTATION
# =============================================================================


@dataclass(frozen=True)
class CoverageRegion:
    """
    One observed coordinate in conceptual space.

    coordinates:
        Normalized dimension/value pairs describing the region.
    """

    region_id: str

    coordinates: tuple[
        tuple[str, Any],
        ...
    ]

    status: RegionStatus

    artifact_ids: tuple[str, ...]

    raw_artifact_count: int
    lineage_aware_count: int

    mean_mapping_confidence: float

    conceptual_duplicate_count: int

    rationale: str


@dataclass(frozen=True)
class CoverageGap:
    """
    Machine-readable conceptual coverage deficiency.

    The gap is descriptive. It is not a release decision.
    """

    gap_id: str

    schema_id: str
    schema_version: str

    dimension_id: str

    desired_value: Any

    current_support: int
    reference_support: int | None

    uncertainty: float

    priority: float

    provenance: str

    rationale: str


@dataclass(frozen=True)
class CoverageAssessment:
    """Structured assessment of artifact conceptual coverage."""

    assessment_id: str

    schema_id: str
    schema_version: str

    mapper_version: str

    artifact_count: int

    regions: tuple[CoverageRegion, ...]
    gaps: tuple[CoverageGap, ...]

    mapping_uncertainty_rate: float

    exact_duplicate_pairs: int
    conceptual_duplicate_pairs: int

    created_at: str = field(default_factory=utc_now_iso)

    configuration_hash: str = ""


# =============================================================================
# COVERAGE ENGINE
# =============================================================================


class CoverageEngine:
    """
    Domain-neutral coverage assessment.

    The baseline implementation analyzes dimension/value support independently.

    This is intentionally interpretable.

    Higher-order interaction coverage can be added separately without replacing
    this contract.
    """

    def __init__(
        self,
        sparse_support_ratio: float = UNIVERSAL_SPARSE_SUPPORT_RATIO,
        repeated_support_ratio: float = UNIVERSAL_REPEATED_SUPPORT_RATIO,
        uncertainty_threshold: float = UNIVERSAL_UNCERTAINTY_THRESHOLD,
    ) -> None:

        self.sparse_support_ratio = sparse_support_ratio
        self.repeated_support_ratio = repeated_support_ratio
        self.uncertainty_threshold = uncertainty_threshold

        for value in (
            sparse_support_ratio,
            repeated_support_ratio,
            uncertainty_threshold,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    "Coverage thresholds must be between 0 and 1."
                )

    def assess(
        self,
        artifacts: Sequence[ArtifactDescriptor],
        mappings: Sequence[ConceptMapping],
        schema: ConceptSchema,
        mapper_version: str,
    ) -> CoverageAssessment:

        schema.validate()

        artifact_lookup = {
            artifact.artifact_id: artifact
            for artifact in artifacts
        }

        mapping_lookup = {
            mapping.artifact_id: mapping
            for mapping in mappings
        }

        missing_mappings = (
            set(artifact_lookup)
            - set(mapping_lookup)
        )

        if missing_mappings:
            raise ValueError(
                "Coverage assessment requires mappings for every "
                f"artifact. Missing: {sorted(missing_mappings)}"
            )

        duplicate_analyzer = DuplicateAnalyzer()

        duplicate_assessments = (
            duplicate_analyzer.analyze(
                artifacts,
                mappings,
            )
        )

        duplicate_lookup = {
            item.artifact_id: item
            for item in duplicate_assessments
        }

        regions: list[CoverageRegion] = []
        gaps: list[CoverageGap] = []

        total_artifacts = len(artifacts)

        uncertain_mapping_count = 0
        total_dimension_mapping_count = 0

        for mapping in mappings:
            for item in mapping.dimension_mappings:
                total_dimension_mapping_count += 1

                if (
                    item.status
                    != MappingStatus.MAPPED
                    or item.confidence
                    < self.uncertainty_threshold
                ):
                    uncertain_mapping_count += 1

        for dimension in schema.dimensions:

            expected_values = self._expected_values(
                dimension
            )

            support: dict[
                str,
                list[tuple[str, DimensionMapping]],
            ] = defaultdict(list)

            actual_value_lookup: dict[str, Any] = {}

            for mapping in mappings:

                dimension_mapping = mapping.mapping_for(
                    dimension.dimension_id
                )

                if (
                    dimension_mapping.status
                    != MappingStatus.MAPPED
                ):
                    continue

                normalized_values = (
                    self._normalize_dimension_values(
                        dimension,
                        dimension_mapping.value,
                    )
                )

                for normalized_value in normalized_values:

                    key = stable_hash(
                        normalized_value
                    )

                    actual_value_lookup[
                        key
                    ] = normalized_value

                    support[key].append(
                        (
                            mapping.artifact_id,
                            dimension_mapping,
                        )
                    )

            expected_keys = {
                stable_hash(value): value
                for value in expected_values
            }

            all_keys = (
                set(expected_keys)
                | set(support)
            )

            for value_key in sorted(all_keys):

                value = (
                    expected_keys.get(value_key)
                    if value_key in expected_keys
                    else actual_value_lookup[value_key]
                )

                supported = support.get(
                    value_key,
                    [],
                )

                artifact_ids = tuple(
                    artifact_id
                    for artifact_id, _ in supported
                )

                raw_count = len(artifact_ids)

                lineage_roots: set[str] = set()

                conceptual_duplicate_count = 0

                confidences: list[float] = []

                for artifact_id, mapping_item in supported:

                    confidences.append(
                        mapping_item.confidence
                    )

                    lineage_roots.update(
                        duplicate_lookup[
                            artifact_id
                        ].lineage_root_ids
                    )

                    conceptual_duplicate_count += len(
                        duplicate_lookup[
                            artifact_id
                        ].conceptual_duplicate_of
                    )

                lineage_aware_count = len(
                    lineage_roots
                )

                mean_confidence = (
                    sum(confidences) / len(confidences)
                    if confidences
                    else 0.0
                )

                status = self._region_status(
                    raw_count=raw_count,
                    total_artifacts=total_artifacts,
                    mean_confidence=mean_confidence,
                )

                coordinates = (
                    (
                        dimension.dimension_id,
                        value,
                    ),
                )

                region_id = stable_hash(
                    {
                        "schema": (
                            schema.schema_id,
                            schema.schema_version,
                        ),
                        "coordinates": coordinates,
                    }
                )

                regions.append(
                    CoverageRegion(
                        region_id=region_id,
                        coordinates=coordinates,
                        status=status,
                        artifact_ids=artifact_ids,
                        raw_artifact_count=raw_count,
                        lineage_aware_count=(
                            lineage_aware_count
                        ),
                        mean_mapping_confidence=(
                            mean_confidence
                        ),
                        conceptual_duplicate_count=(
                            conceptual_duplicate_count
                        ),
                        rationale=(
                            self._region_rationale(
                                status=status,
                                raw_count=raw_count,
                                total_artifacts=(
                                    total_artifacts
                                ),
                                lineage_aware_count=(
                                    lineage_aware_count
                                ),
                            )
                        ),
                    )
                )

                if status in {
                    RegionStatus.ABSENT,
                    RegionStatus.SPARSE,
                    RegionStatus.UNCERTAIN,
                }:

                    support_ratio = (
                        raw_count / total_artifacts
                        if total_artifacts
                        else 0.0
                    )

                    uncertainty = (
                        1.0 - mean_confidence
                        if raw_count
                        else 1.0
                    )

                    priority = self._gap_priority(
                        status=status,
                        support_ratio=support_ratio,
                        uncertainty=uncertainty,
                        dimension_maturity=(
                            dimension.maturity_confidence
                        ),
                    )

                    gaps.append(
                        CoverageGap(
                            gap_id=new_id("gap"),
                            schema_id=schema.schema_id,
                            schema_version=(
                                schema.schema_version
                            ),
                            dimension_id=(
                                dimension.dimension_id
                            ),
                            desired_value=value,
                            current_support=(
                                lineage_aware_count
                            ),
                            reference_support=None,
                            uncertainty=uncertainty,
                            priority=priority,
                            provenance=(
                                "CoverageEngine "
                                f"{UNIVERSAL_MAPPER_VERSION}"
                            ),
                            rationale=(
                                f"Region classified as "
                                f"{status.value}; "
                                f"raw support={raw_count}, "
                                f"lineage-aware support="
                                f"{lineage_aware_count}."
                            ),
                        )
                    )

        exact_pairs = (
            sum(
                len(item.exact_duplicate_of)
                for item in duplicate_assessments
            )
            // 2
        )

        conceptual_pairs = (
            sum(
                len(
                    item.conceptual_duplicate_of
                )
                for item in duplicate_assessments
            )
            // 2
        )

        uncertainty_rate = (
            uncertain_mapping_count
            / total_dimension_mapping_count
            if total_dimension_mapping_count
            else 0.0
        )

        configuration_hash = stable_hash(
            {
                "sparse_support_ratio":
                    self.sparse_support_ratio,
                "repeated_support_ratio":
                    self.repeated_support_ratio,
                "uncertainty_threshold":
                    self.uncertainty_threshold,
                "schema_id":
                    schema.schema_id,
                "schema_version":
                    schema.schema_version,
            }
        )

        return CoverageAssessment(
            assessment_id=new_id("assessment"),
            schema_id=schema.schema_id,
            schema_version=schema.schema_version,
            mapper_version=mapper_version,
            artifact_count=total_artifacts,
            regions=tuple(regions),
            gaps=tuple(
                sorted(
                    gaps,
                    key=lambda item: item.priority,
                    reverse=True,
                )
            ),
            mapping_uncertainty_rate=(
                uncertainty_rate
            ),
            exact_duplicate_pairs=exact_pairs,
            conceptual_duplicate_pairs=(
                conceptual_pairs
            ),
            configuration_hash=(
                configuration_hash
            ),
        )

    def _expected_values(
        self,
        dimension: ConceptDimension,
    ) -> tuple[Any, ...]:

        if (
            dimension.dimension_type
            == DimensionType.BOOLEAN
        ):
            return (False, True)

        if (
            dimension.dimension_type
            == DimensionType.CATEGORICAL
        ):
            return dimension.allowed_values

        if (
            dimension.dimension_type
            == DimensionType.ORDINAL
        ):
            return dimension.ordinal_order

        if (
            dimension.dimension_type
            == DimensionType.MULTI_LABEL
        ):
            return dimension.allowed_values

        if (
            dimension.dimension_type
            == DimensionType.CONTINUOUS
        ):
            # Continuous spaces do not have enumerable expected values.
            # Coverage is assessed over observed buckets.
            return ()

        raise RuntimeError(
            f"Unhandled dimension type "
            f"{dimension.dimension_type!r}."
        )

    def _normalize_dimension_values(
        self,
        dimension: ConceptDimension,
        value: Any,
    ) -> tuple[Any, ...]:

        if (
            dimension.dimension_type
            == DimensionType.MULTI_LABEL
        ):
            return tuple(
                sorted(value, key=str)
            )

        if (
            dimension.dimension_type
            == DimensionType.CONTINUOUS
        ):
            assert (
                dimension.minimum_value is not None
            )
            assert (
                dimension.maximum_value is not None
            )

            minimum = dimension.minimum_value
            maximum = dimension.maximum_value

            width = (
                maximum - minimum
            ) / UNIVERSAL_CONTINUOUS_BUCKET_COUNT

            numeric_value = float(value)

            bucket_index = min(
                UNIVERSAL_CONTINUOUS_BUCKET_COUNT - 1,
                max(
                    0,
                    int(
                        (numeric_value - minimum)
                        / width
                    ),
                ),
            )

            lower = (
                minimum
                + bucket_index * width
            )
            upper = lower + width

            return (
                (
                    round(lower, 8),
                    round(upper, 8),
                ),
            )

        return (value,)

    def _region_status(
        self,
        raw_count: int,
        total_artifacts: int,
        mean_confidence: float,
    ) -> RegionStatus:

        if raw_count == 0:
            return RegionStatus.ABSENT

        if (
            mean_confidence
            < self.uncertainty_threshold
        ):
            return RegionStatus.UNCERTAIN

        support_ratio = (
            raw_count / total_artifacts
            if total_artifacts
            else 0.0
        )

        if (
            support_ratio
            <= self.sparse_support_ratio
        ):
            return RegionStatus.SPARSE

        if (
            support_ratio
            >= self.repeated_support_ratio
        ):
            return RegionStatus.HIGHLY_REPEATED

        return RegionStatus.REPRESENTED

    @staticmethod
    def _region_rationale(
        status: RegionStatus,
        raw_count: int,
        total_artifacts: int,
        lineage_aware_count: int,
    ) -> str:

        return (
            f"status={status.value}; "
            f"raw_artifacts={raw_count}; "
            f"lineage_independent_roots="
            f"{lineage_aware_count}; "
            f"population={total_artifacts}."
        )

    @staticmethod
    def _gap_priority(
        status: RegionStatus,
        support_ratio: float,
        uncertainty: float,
        dimension_maturity: float,
    ) -> float:
        """
        Transparent heuristic priority.

        High priority is encouraged by:
        - absence/sparsity;
        - mature dimensions;
        - reasonably low uncertainty.

        Uncertainty reduces confidence that the gap is real.
        """

        status_weight = {
            RegionStatus.ABSENT: 1.0,
            RegionStatus.SPARSE: 0.8,
            RegionStatus.UNCERTAIN: 0.4,
            RegionStatus.REPRESENTED: 0.0,
            RegionStatus.HIGHLY_REPEATED: 0.0,
        }[status]

        scarcity = 1.0 - support_ratio

        confidence_gap_is_real = (
            1.0 - uncertainty
        )

        score = (
            0.45 * status_weight
            + 0.25 * scarcity
            + 0.20 * dimension_maturity
            + 0.10 * confidence_gap_is_real
        )

        return bounded(score, 0.0, 1.0)


# =============================================================================
# RESOURCE BUDGETS
# =============================================================================


@dataclass(frozen=True)
class ResourceBudget:
    """Caller-supplied constraints for targeted expansion."""

    max_additional_artifacts: int = (
        UNIVERSAL_DEFAULT_MAX_ADDITIONAL_ARTIFACTS
    )

    max_model_calls: int = (
        UNIVERSAL_DEFAULT_MAX_MODEL_CALLS
    )

    token_budget: int = (
        UNIVERSAL_DEFAULT_TOKEN_BUDGET
    )

    execution_budget: int = (
        UNIVERSAL_DEFAULT_EXECUTION_BUDGET
    )

    elapsed_time_budget_seconds: float = (
        UNIVERSAL_DEFAULT_ELAPSED_TIME_SECONDS
    )

    priority_dimension_ids: tuple[str, ...] = ()

    def validate(self) -> None:

        numeric_values = (
            self.max_additional_artifacts,
            self.max_model_calls,
            self.token_budget,
            self.execution_budget,
        )

        if any(value < 0 for value in numeric_values):
            raise ValueError(
                "Resource budgets cannot be negative."
            )

        if self.elapsed_time_budget_seconds < 0:
            raise ValueError(
                "Elapsed-time budget cannot be negative."
            )


# =============================================================================
# EXPANSION CONTRACTS
# =============================================================================


@dataclass(frozen=True)
class ExpansionRequest:
    """
    Domain-neutral request for additional artifacts.

    The mapper describes what conceptual characteristics are needed.

    It does NOT dictate how those artifacts are produced.
    """

    request_id: str

    schema_id: str
    schema_version: str

    source_gap_id: str

    desired_dimensions: tuple[
        tuple[str, Any],
        ...
    ]

    priority: float

    maximum_artifacts: int

    provenance: str

    rationale: str


@dataclass(frozen=True)
class ExpansionCandidate:
    """
    Artifact produced outside the generic mapper in response to a request.
    """

    request_id: str
    artifact: ArtifactDescriptor


@dataclass(frozen=True)
class ExpansionAssessment:
    """
    Independent assessment of whether a newly produced artifact actually
    satisfied the requested conceptual target.
    """

    candidate_artifact_id: str
    request_id: str

    status: ExpansionCandidateStatus

    matched_dimensions: tuple[
        tuple[str, Any],
        ...
    ]

    missing_dimensions: tuple[
        tuple[str, Any],
        ...
    ]

    mapping_id: str

    rationale: str


# =============================================================================
# EXPANSION PLANNER
# =============================================================================


class ExpansionPlanner:
    """
    Translate selected CoverageGaps into structured ExpansionRequests.

    The planner remains generic and budget-aware.
    """

    def plan(
        self,
        gaps: Sequence[CoverageGap],
        budget: ResourceBudget,
    ) -> tuple[ExpansionRequest, ...]:

        budget.validate()

        if budget.max_additional_artifacts == 0:
            return ()

        priority_dimensions = set(
            budget.priority_dimension_ids
        )

        ranked_gaps = sorted(
            gaps,
            key=lambda gap: (
                gap.dimension_id
                in priority_dimensions,
                gap.priority,
            ),
            reverse=True,
        )

        requests: list[ExpansionRequest] = []

        remaining_artifacts = (
            budget.max_additional_artifacts
        )

        remaining_model_calls = (
            budget.max_model_calls
        )

        for gap in ranked_gaps:

            if remaining_artifacts <= 0:
                break

            if remaining_model_calls <= 0:
                break

            allocation = 1

            requests.append(
                ExpansionRequest(
                    request_id=new_id("expansion"),
                    schema_id=gap.schema_id,
                    schema_version=(
                        gap.schema_version
                    ),
                    source_gap_id=gap.gap_id,
                    desired_dimensions=(
                        (
                            gap.dimension_id,
                            gap.desired_value,
                        ),
                    ),
                    priority=gap.priority,
                    maximum_artifacts=allocation,
                    provenance=(
                        "ExpansionPlanner "
                        f"{UNIVERSAL_MAPPER_VERSION}"
                    ),
                    rationale=(
                        "Request generated from a "
                        f"{gap.rationale}"
                    ),
                )
            )

            remaining_artifacts -= allocation
            remaining_model_calls -= 1

        return tuple(requests)


# =============================================================================
# GENERIC DIVERSITY MAPPING PORT
# =============================================================================


class DiversityMappingPort(ABC):
    """Client-independent measurement interface."""

    @abstractmethod
    def map_artifacts(
        self,
        artifacts: Sequence[ArtifactDescriptor],
        schema: ConceptSchema,
    ) -> tuple[ConceptMapping, ...]:
        pass

    @abstractmethod
    def assess_coverage(
        self,
        artifacts: Sequence[ArtifactDescriptor],
        mappings: Sequence[ConceptMapping],
        schema: ConceptSchema,
    ) -> CoverageAssessment:
        pass


class DiversityExpansionPort(ABC):
    """Client-independent expansion-planning interface."""

    @abstractmethod
    def plan_expansion(
        self,
        assessment: CoverageAssessment,
        budget: ResourceBudget,
    ) -> tuple[ExpansionRequest, ...]:
        pass

    @abstractmethod
    def assess_expansion_candidates(
        self,
        candidates: Sequence[ExpansionCandidate],
        requests: Sequence[ExpansionRequest],
        schema: ConceptSchema,
    ) -> tuple[ExpansionAssessment, ...]:
        pass


# =============================================================================
# OBSERVABILITY
# =============================================================================


@dataclass
class MapperMetrics:
    """Operational measurements for the mapper itself."""

    artifacts_processed: int = 0

    model_calls: int = 0

    input_tokens: int = 0
    output_tokens: int = 0

    mapping_failures: int = 0
    unresolved_mappings: int = 0

    expansion_requests: int = 0

    expansion_candidates_assessed: int = 0
    expansion_candidates_accepted: int = 0

    total_mapping_latency_seconds: float = 0.0

    schema_version: str = ""

    def expansion_acceptance_rate(
        self,
    ) -> float:

        if self.expansion_candidates_assessed == 0:
            return 0.0

        return (
            self.expansion_candidates_accepted
            / self.expansion_candidates_assessed
        )


# =============================================================================
# GENERIC DIVERSITY ENGINE
# =============================================================================


class GenericDiversityEngine(
    DiversityMappingPort,
    DiversityExpansionPort,
):
    """
    Fundamental generic engine.

    IMPORTANT CLIENT-BOUNDARY DECISION
    ----------------------------------

    L1 automation clients should NOT instantiate this class directly.

    They should use EvidenceDiversityMapperAdapter below.

    Keeping this engine generic provides reuse across:

        evidence bundles;
        prompt datasets;
        QA datasets;
        evaluation corpora;
        codebase libraries;
        behavioral tests;
        future artifact collections.

    At the same time, all L1-specific semantics remain in the evidence adapter.
    """

    def __init__(
        self,
        concept_mapper: ArtifactConceptMapperPort,
        mapper_version: str = UNIVERSAL_MAPPER_VERSION,
        coverage_engine: CoverageEngine | None = None,
        expansion_planner: ExpansionPlanner | None = None,
    ) -> None:

        self.concept_mapper = concept_mapper
        self.mapper_version = mapper_version

        self.coverage_engine = (
            coverage_engine
            or CoverageEngine()
        )

        self.expansion_planner = (
            expansion_planner
            or ExpansionPlanner()
        )

        self.metrics = MapperMetrics()

    def map_artifacts(
        self,
        artifacts: Sequence[ArtifactDescriptor],
        schema: ConceptSchema,
    ) -> tuple[ConceptMapping, ...]:

        schema.validate()

        self.metrics.schema_version = (
            schema.schema_version
        )

        mappings: list[ConceptMapping] = []

        for artifact in artifacts:

            start = time.perf_counter()

            try:

                mapping = (
                    self.concept_mapper.map_artifact(
                        artifact,
                        schema,
                    )
                )

                mappings.append(mapping)

                self.metrics.artifacts_processed += 1

                self.metrics.unresolved_mappings += sum(
                    1
                    for item in mapping.dimension_mappings
                    if item.status
                    in {
                        MappingStatus.UNKNOWN,
                        MappingStatus.UNRESOLVED,
                    }
                )

            except Exception:

                self.metrics.mapping_failures += 1
                raise

            finally:

                self.metrics.total_mapping_latency_seconds += (
                    time.perf_counter() - start
                )

        return tuple(mappings)

    def assess_coverage(
        self,
        artifacts: Sequence[ArtifactDescriptor],
        mappings: Sequence[ConceptMapping],
        schema: ConceptSchema,
    ) -> CoverageAssessment:

        return self.coverage_engine.assess(
            artifacts=artifacts,
            mappings=mappings,
            schema=schema,
            mapper_version=self.mapper_version,
        )

    def plan_expansion(
        self,
        assessment: CoverageAssessment,
        budget: ResourceBudget,
    ) -> tuple[ExpansionRequest, ...]:

        requests = self.expansion_planner.plan(
            gaps=assessment.gaps,
            budget=budget,
        )

        self.metrics.expansion_requests += len(
            requests
        )

        return requests

    def assess_expansion_candidates(
        self,
        candidates: Sequence[ExpansionCandidate],
        requests: Sequence[ExpansionRequest],
        schema: ConceptSchema,
    ) -> tuple[ExpansionAssessment, ...]:

        request_lookup = {
            request.request_id: request
            for request in requests
        }

        assessments: list[
            ExpansionAssessment
        ] = []

        for candidate in candidates:

            request = request_lookup.get(
                candidate.request_id
            )

            if request is None:
                raise KeyError(
                    "Expansion candidate references unknown "
                    f"request {candidate.request_id!r}."
                )

            mapping = (
                self.concept_mapper.map_artifact(
                    candidate.artifact,
                    schema,
                )
            )

            mapping_lookup = {
                item.dimension_id: item
                for item
                in mapping.dimension_mappings
            }

            matched: list[
                tuple[str, Any]
            ] = []

            missing: list[
                tuple[str, Any]
            ] = []

            unresolved = False

            for (
                dimension_id,
                desired_value,
            ) in request.desired_dimensions:

                item = mapping_lookup.get(
                    dimension_id
                )

                if (
                    item is None
                    or item.status
                    in {
                        MappingStatus.UNKNOWN,
                        MappingStatus.UNRESOLVED,
                        MappingStatus.UNSUPPORTED,
                    }
                ):
                    missing.append(
                        (
                            dimension_id,
                            desired_value,
                        )
                    )
                    unresolved = True
                    continue

                if self._values_match(
                    item.value,
                    desired_value,
                ):
                    matched.append(
                        (
                            dimension_id,
                            desired_value,
                        )
                    )
                else:
                    missing.append(
                        (
                            dimension_id,
                            desired_value,
                        )
                    )

            if unresolved:

                status = (
                    ExpansionCandidateStatus.UNRESOLVED
                )

            elif not missing:

                status = (
                    ExpansionCandidateStatus
                    .SATISFIED_REQUEST
                )

            elif matched:

                status = (
                    ExpansionCandidateStatus
                    .PARTIALLY_SATISFIED
                )

            else:

                status = (
                    ExpansionCandidateStatus
                    .DID_NOT_SATISFY
                )

            if (
                status
                == ExpansionCandidateStatus
                .SATISFIED_REQUEST
            ):
                self.metrics.expansion_candidates_accepted += 1

            self.metrics.expansion_candidates_assessed += 1

            assessments.append(
                ExpansionAssessment(
                    candidate_artifact_id=(
                        candidate.artifact.artifact_id
                    ),
                    request_id=request.request_id,
                    status=status,
                    matched_dimensions=tuple(
                        matched
                    ),
                    missing_dimensions=tuple(
                        missing
                    ),
                    mapping_id=mapping.mapping_id,
                    rationale=(
                        "Expansion candidate was independently "
                        "mapped against the same ConceptSchema; "
                        "generator intent was not treated as proof "
                        "of conceptual coverage."
                    ),
                )
            )

        return tuple(assessments)

    @staticmethod
    def _values_match(
        actual: Any,
        desired: Any,
    ) -> bool:

        if isinstance(
            actual,
            (tuple, list, set, frozenset),
        ):
            return desired in actual

        if (
            isinstance(actual, float)
            and isinstance(desired, float)
        ):
            return math.isclose(
                actual,
                desired,
                abs_tol=(
                    UNIVERSAL_FLOAT_COMPARISON_TOLERANCE
                ),
            )

        return actual == desired


# =============================================================================
# EVIDENCE-DOMAIN CONTRACTS
# =============================================================================
#
# These are what the internal L1 client should interact with.
#
# The client does NOT need to know ArtifactDescriptor or GenericDiversityEngine
# exist underneath.
