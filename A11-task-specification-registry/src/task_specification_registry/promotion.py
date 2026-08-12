"""
Qualification-to-production promotion checks.

A task capability must not become APPROVED while development sentinel
artifacts remain in its contract.
"""

from __future__ import annotations

from .errors import SpecificationValidationError
from .models import ArtifactPointer, TaskSpecification


_SENTINEL_HASHES = {
    character * 64
    for character in ("0", "1", "2", "3", "4")
}


def _all_artifacts(
    specification: TaskSpecification,
) -> tuple[ArtifactPointer, ...]:
    artifacts: list[ArtifactPointer] = []

    artifacts.extend(
        specification.skill_contract.required_skills
    )

    artifacts.extend(
        specification.skill_contract.optional_skills
    )

    artifacts.extend(
        specification.skill_contract.repository_instructions
    )

    if specification.evidence_contract.diversity_specification:
        artifacts.append(
            specification.evidence_contract.diversity_specification
        )

    for requirement in specification.evidence_contract.requirements:
        if requirement.artifact_specification:
            artifacts.append(
                requirement.artifact_specification
            )

    artifacts.append(
        specification.gate_contract.gate_policy
    )

    artifacts.append(
        specification.benchmark_contract.benchmark_suite
    )

    artifacts.append(
        specification.benchmark_contract.qualification_policy
    )

    return tuple(artifacts)


def validate_for_approval(
    specification: TaskSpecification,
) -> None:
    """
    Reject obvious development-only artifact references.

    Production should additionally verify that every referenced digest exists
    in the approved artifact repository.
    """

    for artifact in _all_artifacts(specification):
        if artifact.sha256 in _SENTINEL_HASHES:
            raise SpecificationValidationError(
                "Specification contains development sentinel artifact hash: "
                f"{artifact.artifact_id}"
            )
