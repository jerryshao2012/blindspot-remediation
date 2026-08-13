"""
Strict domain models for Component 11.

A task specification is intentionally richer than an agent prompt.

It is the machine-readable engineering contract shared by:

    Component 2  ChangeExecutionService
    Component 3  ReleaseGateService
    Component 5  EvaluationCampaignRunner
    Component 9  EngineeringAutomationOrchestrator
    Component 10 ExecutionEnvironmentService
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class RegistryModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class SpecificationStatus(StrEnum):
    DRAFT = "draft"
    QUALIFYING = "qualifying"
    APPROVED = "approved"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class RiskTier(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class GateOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    MORE_EVIDENCE = "more_evidence"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class ArtifactPointer(RegistryModel):
    """
    Immutable reference to a governed artifact.

    Examples:

        SKILL.md
        gate YAML
        benchmark manifest
        test-generation instructions
        static-analysis policy
    """

    artifact_id: Annotated[str, Field(min_length=1, max_length=256)]

    uri: Annotated[str, Field(min_length=1)]

    sha256: Annotated[
        str,
        Field(pattern=r"^[0-9a-f]{64}$"),
    ]

    version: Annotated[str, Field(min_length=1, max_length=64)]


class PathRule(RegistryModel):
    """
    Repository path rule.

    The actual path enforcement belongs below the LLM.

    The LLM may propose a file modification.
    The platform determines whether the path is permitted.
    """

    pattern: Annotated[str, Field(min_length=1)]

    allow_write: bool

    explanation: Annotated[str, Field(min_length=1)]


class RepositoryScope(RegistryModel):
    repository_id: Annotated[str, Field(min_length=1, max_length=256)]

    allowed_base_branches: tuple[str, ...]

    path_rules: tuple[PathRule, ...]

    maximum_files_changed: Annotated[int, Field(ge=1, le=10_000)]

    maximum_changed_lines: Annotated[int, Field(ge=1, le=1_000_000)]


class SkillContract(RegistryModel):
    """
    Instructions and skills supplied to the change agent.

    They are content-addressed so a run can later prove exactly which
    instructions were used.
    """

    required_skills: tuple[ArtifactPointer, ...]

    optional_skills: tuple[ArtifactPointer, ...] = ()

    repository_instructions: tuple[ArtifactPointer, ...] = ()


class ChangeContract(RegistryModel):
    """
    Boundaries within which Component 2 may create a candidate.
    """

    permitted_languages: tuple[str, ...]

    permitted_operations: tuple[str, ...]

    forbidden_operations: tuple[str, ...]

    require_existing_tests_before_change: bool = True

    require_candidate_diff: bool = True

    require_change_rationale: bool = True


class ExecutionContract(RegistryModel):
    """
    References Component 10 profiles rather than duplicating sandbox policy.
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

    maximum_execution_attempts: Annotated[int, Field(ge=1, le=20)] = 3


class EvidenceRequirement(RegistryModel):
    """
    One required evidence family.

    This intentionally describes evidence, not implementation details.
    """

    evidence_type: Annotated[str, Field(min_length=1, max_length=128)]

    required: bool = True

    minimum_observations: Annotated[int, Field(ge=1)] = 1

    independent_from_change_agent: bool = False

    artifact_specification: ArtifactPointer | None = None


class EvidenceContract(RegistryModel):
    requirements: tuple[EvidenceRequirement, ...]

    diversity_specification: ArtifactPointer | None = None

    require_baseline_comparison: bool = True

    require_environment_provenance: bool = True


class GateContract(RegistryModel):
    """
    Gate policy is separately versioned.

    Component 11 says WHICH gate contract applies.

    Component 3 performs the actual decision.
    """

    gate_policy: ArtifactPointer

    permitted_outcomes: tuple[GateOutcome, ...]

    fail_closed_on_missing_required_evidence: bool = True

    fail_closed_on_policy_error: bool = True


class BenchmarkContract(RegistryModel):
    benchmark_suite: ArtifactPointer

    minimum_cases: Annotated[int, Field(ge=1)]

    qualification_policy: ArtifactPointer

    require_hidden_oracle: bool = True


class GovernanceContract(RegistryModel):
    risk_tier: RiskTier

    maximum_llm_input_tokens: Annotated[int, Field(ge=0)]

    maximum_llm_output_tokens: Annotated[int, Field(ge=0)]

    maximum_total_cost_usd: Annotated[float, Field(ge=0)]

    human_review_allowed: bool = True

    auto_release_allowed: bool = False


class TaskSpecification(RegistryModel):
    """
    Complete immutable definition of one task capability version.
    """

    task_type: Annotated[str, Field(min_length=1, max_length=128)]

    version: Annotated[str, Field(min_length=1, max_length=64)]

    display_name: Annotated[str, Field(min_length=1, max_length=256)]

    description: Annotated[str, Field(min_length=1)]

    status: SpecificationStatus

    created_at: datetime

    repository_scope: RepositoryScope

    skill_contract: SkillContract

    change_contract: ChangeContract

    execution_contract: ExecutionContract

    evidence_contract: EvidenceContract

    gate_contract: GateContract

    benchmark_contract: BenchmarkContract

    governance_contract: GovernanceContract


class RegisteredSpecification(RegistryModel):
    """
    Stored specification plus its canonical content identity.
    """

    specification: TaskSpecification

    specification_sha256: Annotated[
        str,
        Field(pattern=r"^[0-9a-f]{64}$"),
    ]


class ResolvedTaskContract(RegistryModel):
    """
    Object returned to Component 9.

    Once resolved, downstream components should carry this digest throughout
    the complete run.
    """

    task_type: str

    version: str

    specification_sha256: str

    specification: TaskSpecification
