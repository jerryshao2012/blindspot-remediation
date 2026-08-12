"""
Semantic validation for task specifications.

Pydantic validates shape and primitive constraints.

This module validates relationships between fields.

These checks are deterministic.

An LLM must not determine whether its own governing specification is valid.
"""

from __future__ import annotations

from .errors import SpecificationValidationError
from .models import (
    GateOutcome,
    SpecificationStatus,
    TaskSpecification,
)


class TaskSpecificationValidator:
    """Perform cross-field semantic validation."""

    def validate(
        self,
        specification: TaskSpecification,
    ) -> None:
        self._validate_repository_scope(specification)
        self._validate_evidence(specification)
        self._validate_gate(specification)
        self._validate_governance(specification)
        self._validate_qualification(specification)

    @staticmethod
    def _validate_repository_scope(
        specification: TaskSpecification,
    ) -> None:
        scope = specification.repository_scope

        if not scope.allowed_base_branches:
            raise SpecificationValidationError(
                "At least one base branch must be permitted."
            )

        if not scope.path_rules:
            raise SpecificationValidationError(
                "Repository scope must contain explicit path rules."
            )

        if not any(rule.allow_write for rule in scope.path_rules):
            raise SpecificationValidationError(
                "Task specification does not permit any writable path."
            )

    @staticmethod
    def _validate_evidence(
        specification: TaskSpecification,
    ) -> None:
        requirements = specification.evidence_contract.requirements

        if not requirements:
            raise SpecificationValidationError(
                "At least one evidence requirement must be defined."
            )

        evidence_types = [
            requirement.evidence_type
            for requirement in requirements
        ]

        if len(evidence_types) != len(set(evidence_types)):
            raise SpecificationValidationError(
                "Evidence requirement types must be unique."
            )

    @staticmethod
    def _validate_gate(
        specification: TaskSpecification,
    ) -> None:
        outcomes = set(
            specification.gate_contract.permitted_outcomes
        )

        if GateOutcome.PASS not in outcomes:
            raise SpecificationValidationError(
                "A usable release gate must permit PASS."
            )

        if GateOutcome.FAIL not in outcomes:
            raise SpecificationValidationError(
                "A usable release gate must permit FAIL."
            )

        if (
            GateOutcome.HUMAN_REVIEW_REQUIRED in outcomes
            and not specification.governance_contract.human_review_allowed
        ):
            raise SpecificationValidationError(
                "Gate permits human review but governance contract "
                "prohibits human review."
            )

    @staticmethod
    def _validate_governance(
        specification: TaskSpecification,
    ) -> None:
        governance = specification.governance_contract

        if (
            governance.auto_release_allowed
            and specification.status != SpecificationStatus.APPROVED
        ):
            raise SpecificationValidationError(
                "Only an APPROVED capability may permit automatic release."
            )

    @staticmethod
    def _validate_qualification(
        specification: TaskSpecification,
    ) -> None:
        benchmark = specification.benchmark_contract

        if (
            specification.status == SpecificationStatus.APPROVED
            and benchmark.minimum_cases < 1
        ):
            raise SpecificationValidationError(
                "Approved capabilities require benchmark qualification."
            )
