"""
Canonical TaskSpecification schema.

MAJOR B1 DECISION
-----------------

The full TaskSpecification schema now belongs in Component 1 because it is
consumed by multiple components:

    Component 2
        needs skill and change contracts.

    Component 3
        needs evidence and gate contracts.

    Component 5
        needs benchmark/qualification contracts.

    Component 9
        needs governance and resource budgets.

    Component 10
        is referenced through execution profile IDs.

    Component 11
        owns registration, validation, approval and resolution behaviour.

Therefore:

    Component 1 = WHAT THE CONTRACT IS.
    Component 11 = HOW THE CONTRACT IS GOVERNED.

The older Component 9 TaskDefinition must be removed.
"""

from __future__ import annotations

from pydantic import (
    Field,
    model_validator,
)
from typing_extensions import (
    Annotated,
    Self,
)

from .base import (
    AwareDatetime,
    CONTRACT_SCHEMA_VERSION,
    ContractModel,
)
from .enums import (
    GateDisposition,
    RiskTier,
    SpecificationStatus,
)
from .evidence import EvidenceRequirement
from .ids import (
    Sha256Digest,
    SpecificationVersion,
)
from .references import ArtifactReference
from .usage import ResourceBudget


class PathRule(ContractModel):
    """
    Declarative repository path permission.

    IMPORTANT:

    This rule is policy DATA.

    Component 10 / repository tooling must actually enforce it.

    Telling an LLM that a path is forbidden is not equivalent to authorization
    enforcement.
    """

    pattern: Annotated[
        str,
        Field(min_length=1),
    ]

    allow_write: bool

    explanation: Annotated[
        str,
        Field(min_length=1),
    ]


class RepositoryScope(ContractModel):
    repository_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    allowed_base_branches: tuple[str, ...]

    path_rules: tuple[PathRule, ...]

    maximum_files_changed: Annotated[
        int,
        Field(ge=1, le=10_000),
    ]

    maximum_changed_lines: Annotated[
        int,
        Field(ge=1, le=1_000_000),
    ]

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if not self.allowed_base_branches:
            raise ValueError(
                "RepositoryScope requires at least one permitted base branch."
            )

        if not self.path_rules:
            raise ValueError(
                "RepositoryScope requires explicit path rules."
            )

        if not any(
            rule.allow_write
            for rule in self.path_rules
        ):
            raise ValueError(
                "RepositoryScope does not permit writing any path."
            )

        return self


class SkillContract(ContractModel):
    """
    Governed instruction artifacts consumed by Component 2.

    Skills are treated as versioned/content-addressed engineering artifacts,
    not merely ephemeral prompt text.
    """

    required_skills: tuple[
        ArtifactReference,
        ...,
    ]

    optional_skills: tuple[
        ArtifactReference,
        ...,
    ] = ()

    repository_instructions: tuple[
        ArtifactReference,
        ...,
    ] = ()


class ChangeContract(ContractModel):
    permitted_languages: tuple[str, ...]

    permitted_operations: tuple[str, ...]

    forbidden_operations: tuple[str, ...]

    require_existing_tests_before_change: bool = True
    require_candidate_diff: bool = True
    require_change_rationale: bool = True

    @model_validator(mode="after")
    def validate_change_contract(self) -> Self:
        if not self.permitted_languages:
            raise ValueError(
                "At least one implementation language must be permitted."
            )

        if not self.permitted_operations:
            raise ValueError(
                "At least one change operation must be permitted."
            )

        overlap = (
            set(self.permitted_operations)
            & set(self.forbidden_operations)
        )

        if overlap:
            raise ValueError(
                "An operation cannot be both permitted and forbidden: "
                f"{sorted(overlap)!r}"
            )

        return self


class ExecutionContract(ContractModel):
    """
    Component 11 says WHICH Component 10 profile should apply.

    Component 10 owns the profile itself.

    This prevents duplicating sandbox policy inside TaskSpecification.
    """

    change_execution_profile_id: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    release_gate_profile_id: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    benchmark_profile_id: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]


class EvidenceContract(ContractModel):
    requirements: tuple[
        EvidenceRequirement,
        ...,
    ]

    diversity_specification: ArtifactReference | None = None

    require_baseline_comparison: bool = True
    require_environment_provenance: bool = True

    @model_validator(mode="after")
    def validate_requirements(self) -> Self:
        if not self.requirements:
            raise ValueError(
                "At least one evidence requirement must exist."
            )

        names = [
            item.evidence_type
            for item in self.requirements
        ]

        if len(names) != len(set(names)):
            raise ValueError(
                "Evidence requirement types must be unique."
            )

        return self


class GateContract(ContractModel):
    gate_policy: ArtifactReference

    permitted_outcomes: tuple[
        GateDisposition,
        ...,
    ]

    fail_closed_on_missing_required_evidence: bool = True
    fail_closed_on_policy_error: bool = True

    @model_validator(mode="after")
    def validate_gate_contract(self) -> Self:
        outcomes = set(self.permitted_outcomes)

        if GateDisposition.PASS not in outcomes:
            raise ValueError(
                "GateContract must permit PASS."
            )

        if GateDisposition.FAIL not in outcomes:
            raise ValueError(
                "GateContract must permit FAIL."
            )

        return self


class BenchmarkContract(ContractModel):
    benchmark_suite: ArtifactReference

    minimum_cases: Annotated[
        int,
        Field(ge=1),
    ]

    qualification_policy: ArtifactReference

    require_hidden_oracle: bool = True


class GovernanceContract(ContractModel):
    """
    Governance and orchestration constraints.

    ResourceBudget used to appear in several places in the prototype.
    It now exists ONCE here.
    """

    risk_tier: RiskTier

    resource_budget: ResourceBudget

    human_review_allowed: bool = True

    auto_release_allowed: bool = False


class TaskSpecification(ContractModel):
    """
    Complete definition of one qualified automation capability version.

    IMPORTANT:
        Changing ANY material field creates a new specification content hash
        and should normally result in a new specification version.

    The registry in Component 11 is responsible for enforcing immutability and
    lifecycle status.
    """

    schema_version: str = CONTRACT_SCHEMA_VERSION

    task_type: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    version: SpecificationVersion

    display_name: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    description: Annotated[
        str,
        Field(min_length=1),
    ]

    status: SpecificationStatus

    created_at: AwareDatetime

    repository_scope: RepositoryScope
    skill_contract: SkillContract
    change_contract: ChangeContract
    execution_contract: ExecutionContract
    evidence_contract: EvidenceContract
    gate_contract: GateContract
    benchmark_contract: BenchmarkContract
    governance_contract: GovernanceContract

    @model_validator(mode="after")
    def validate_cross_contract_rules(self) -> Self:
        outcomes = set(
            self.gate_contract.permitted_outcomes
        )

        if (
            GateDisposition.HUMAN_REVIEW_REQUIRED
            in outcomes
            and not self.governance_contract.human_review_allowed
        ):
            raise ValueError(
                "Gate permits HUMAN_REVIEW_REQUIRED but governance "
                "prohibits human review."
            )

        if (
            self.governance_contract.auto_release_allowed
            and self.status != SpecificationStatus.APPROVED
        ):
            raise ValueError(
                "Only an APPROVED TaskSpecification may allow auto-release."
            )

        budget = self.governance_contract.resource_budget

        if (
            budget.maximum_total_cost is None
            and budget.cost_currency is not None
        ):
            raise ValueError(
                "cost_currency is meaningless when maximum_total_cost "
                "is not configured."
            )

        if (
            budget.maximum_total_cost is not None
            and budget.cost_currency is None
        ):
            raise ValueError(
                "A configured maximum_total_cost requires cost_currency."
            )

        return self


class RegisteredTaskSpecification(ContractModel):
    """
    Registry representation after Component 11 validates and fingerprints the
    specification.
    """

    specification: TaskSpecification
    specification_sha256: Sha256Digest


class ResolvedTaskContract(ContractModel):
    """
    Exact capability contract frozen for an engineering run.

    Every online/offline run should carry this digest all the way through the
    evidence chain.
    """

    specification: TaskSpecification
    specification_sha256: Sha256Digest

