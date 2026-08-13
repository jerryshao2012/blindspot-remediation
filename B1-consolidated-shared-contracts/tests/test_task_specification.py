from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ai_engineering_contracts import (
    ArtifactReference,
    BenchmarkContract,
    ChangeContract,
    EvidenceContract,
    EvidenceRequirement,
    ExecutionContract,
    GateContract,
    GateDisposition,
    GovernanceContract,
    PathRule,
    RepositoryScope,
    ResourceBudget,
    RiskTier,
    SkillContract,
    SpecificationStatus,
    TaskSpecification,
)


NOW = datetime.now(timezone.utc)


def artifact(
    identifier: str,
    digest_character: str,
) -> ArtifactReference:
    """
    Build a valid synthetic artifact for schema tests.

    These are test-only hashes. They are not production configuration.
    """

    return ArtifactReference(
        artifact_id=identifier,
        uri=f"artifact://{identifier}",
        sha256=digest_character * 64,
        media_type="application/octet-stream",
        created_at=NOW,
        producer_component="test-suite",
    )


def make_specification(
    *,
    status: SpecificationStatus = SpecificationStatus.QUALIFYING,
    auto_release: bool = False,
) -> TaskSpecification:

    return TaskSpecification(
        task_type="X1",
        version="1.0.0",
        display_name="POC X1",
        description="A deliberately narrow engineering capability.",
        status=status,
        created_at=NOW,

        repository_scope=RepositoryScope(
            repository_id="engineering-poc",
            allowed_base_branches=("main",),
            path_rules=(
                PathRule(
                    pattern="src/**/*.py",
                    allow_write=True,
                    explanation="Application source.",
                ),
                PathRule(
                    pattern="task_specs/**",
                    allow_write=False,
                    explanation="Agent may not modify governing policy.",
                ),
            ),
            maximum_files_changed=10,
            maximum_changed_lines=500,
        ),

        skill_contract=SkillContract(
            required_skills=(
                artifact("skill", "a"),
            ),
        ),

        change_contract=ChangeContract(
            permitted_languages=("python",),
            permitted_operations=("modify_source",),
            forbidden_operations=("modify_gate_policy",),
        ),

        execution_contract=ExecutionContract(
            change_execution_profile_id="change-v1",
            release_gate_profile_id="gate-v1",
            benchmark_profile_id="benchmark-v1",
        ),

        evidence_contract=EvidenceContract(
            requirements=(
                EvidenceRequirement(
                    evidence_type="baseline_tests",
                ),
                EvidenceRequirement(
                    evidence_type="independent_tests",
                    independent_from_change_agent=True,
                ),
            ),
        ),

        gate_contract=GateContract(
            gate_policy=artifact("gate-policy", "b"),
            permitted_outcomes=(
                GateDisposition.PASS,
                GateDisposition.FAIL,
                GateDisposition.MORE_EVIDENCE_REQUIRED,
                GateDisposition.HUMAN_REVIEW_REQUIRED,
            ),
        ),

        benchmark_contract=BenchmarkContract(
            benchmark_suite=artifact("benchmark", "c"),
            minimum_cases=30,
            qualification_policy=artifact(
                "qualification-policy",
                "d",
            ),
        ),

        governance_contract=GovernanceContract(
            risk_tier=RiskTier.MODERATE,
            resource_budget=ResourceBudget(),
            human_review_allowed=True,
            auto_release_allowed=auto_release,
        ),
    )


def test_qualifying_specification_is_valid() -> None:
    specification = make_specification()

    assert specification.task_type == "X1"


def test_unapproved_capability_cannot_enable_auto_release() -> None:
    with pytest.raises(ValidationError):
        make_specification(
            status=SpecificationStatus.QUALIFYING,
            auto_release=True,
        )


def test_approved_capability_may_enable_auto_release() -> None:
    specification = make_specification(
        status=SpecificationStatus.APPROVED,
        auto_release=True,
    )

    assert (
        specification.governance_contract.auto_release_allowed
        is True
    )


def test_contract_cannot_permit_and_forbid_same_operation() -> None:
    with pytest.raises(ValidationError):
        ChangeContract(
            permitted_languages=("python",),
            permitted_operations=("modify_source",),
            forbidden_operations=("modify_source",),
        )

