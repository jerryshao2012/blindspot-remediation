from datetime import datetime, timezone

import pytest

from task_specification_registry.errors import (
    DuplicateSpecificationError,
    SpecificationNotApprovedError,
)
from task_specification_registry.models import (
    ArtifactPointer,
    BenchmarkContract,
    ChangeContract,
    EvidenceContract,
    EvidenceRequirement,
    ExecutionContract,
    GateContract,
    GateOutcome,
    GovernanceContract,
    PathRule,
    RepositoryScope,
    RiskTier,
    SkillContract,
    SpecificationStatus,
    TaskSpecification,
)
from task_specification_registry.repository import (
    InMemorySpecificationRepository,
)
from task_specification_registry.service import (
    TaskSpecificationRegistry,
)


def artifact(
    name: str,
    digit: str,
) -> ArtifactPointer:
    return ArtifactPointer(
        artifact_id=name,
        uri=f"artifact://{name}",
        sha256=digit * 64,
        version="1.0.0",
    )


def make_specification(
    *,
    status: SpecificationStatus,
) -> TaskSpecification:
    return TaskSpecification(
        task_type="PYTHON_TARGETED_CHANGE",
        version="1.0.0",
        display_name="Python Targeted Change",
        description="Bounded Python change.",
        status=status,
        created_at=datetime.now(timezone.utc),

        repository_scope=RepositoryScope(
            repository_id="poc",
            allowed_base_branches=("main",),
            path_rules=(
                PathRule(
                    pattern="src/**/*.py",
                    allow_write=True,
                    explanation="Python source.",
                ),
            ),
            maximum_files_changed=10,
            maximum_changed_lines=500,
        ),

        skill_contract=SkillContract(
            required_skills=(
                artifact("skill", "a"),
            )
        ),

        change_contract=ChangeContract(
            permitted_languages=("python",),
            permitted_operations=("modify_source",),
            forbidden_operations=("modify_gate",),
        ),

        execution_contract=ExecutionContract(
            change_execution_profile_id="change-execution-v1",
            release_gate_profile_id="release-gate-v1",
            benchmark_profile_id="benchmark-v1",
        ),

        evidence_contract=EvidenceContract(
            requirements=(
                EvidenceRequirement(
                    evidence_type="tests",
                    required=True,
                ),
            )
        ),

        gate_contract=GateContract(
            gate_policy=artifact("gate", "b"),
            permitted_outcomes=(
                GateOutcome.PASS,
                GateOutcome.FAIL,
                GateOutcome.HUMAN_REVIEW_REQUIRED,
            ),
        ),

        benchmark_contract=BenchmarkContract(
            benchmark_suite=artifact("benchmark", "c"),
            minimum_cases=30,
            qualification_policy=artifact(
                "qualification",
                "d",
            ),
        ),

        governance_contract=GovernanceContract(
            risk_tier=RiskTier.MODERATE,
            maximum_llm_input_tokens=2_000_000,
            maximum_llm_output_tokens=500_000,
            maximum_total_cost_usd=100.0,
            human_review_allowed=True,
            auto_release_allowed=False,
        ),
    )


def test_approved_specification_can_be_resolved() -> None:
    registry = TaskSpecificationRegistry(
        repository=InMemorySpecificationRepository()
    )

    registered = registry.register(
        make_specification(
            status=SpecificationStatus.APPROVED
        )
    )

    resolved = registry.resolve(
        task_type="PYTHON_TARGETED_CHANGE",
        version="1.0.0",
    )

    assert (
        resolved.specification_sha256
        == registered.specification_sha256
    )


def test_nonapproved_specification_cannot_run_as_production() -> None:
    registry = TaskSpecificationRegistry(
        repository=InMemorySpecificationRepository()
    )

    registry.register(
        make_specification(
            status=SpecificationStatus.QUALIFYING
        )
    )

    with pytest.raises(SpecificationNotApprovedError):
        registry.resolve(
            task_type="PYTHON_TARGETED_CHANGE",
            version="1.0.0",
        )


def test_specifications_are_immutable() -> None:
    registry = TaskSpecificationRegistry(
        repository=InMemorySpecificationRepository()
    )

    specification = make_specification(
        status=SpecificationStatus.APPROVED
    )

    registry.register(specification)

    with pytest.raises(DuplicateSpecificationError):
        registry.register(specification)
