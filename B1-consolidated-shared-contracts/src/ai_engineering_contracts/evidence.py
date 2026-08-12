"""
Shared evidence contracts.

We deliberately keep `evidence_type` extensible rather than creating a giant
enum.

Task classes can legitimately introduce evidence families that do not exist
today.

Examples:

    baseline_tests
    independent_tests
    mutation_analysis
    static_analysis
    compiler_analysis
    API_compatibility
    security_scan

The TaskSpecification determines which evidence types are required.
"""

from __future__ import annotations

from pydantic import Field, model_validator
from typing_extensions import Annotated, Self

from .base import (
    AwareDatetime,
    ContractModel,
)
from .ids import (
    EvidenceId,
    RunId,
)
from .references import ArtifactReference


class EvidenceRequirement(ContractModel):
    evidence_type: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    required: bool = True

    minimum_observations: Annotated[
        int,
        Field(ge=1),
    ] = 1

    independent_from_change_agent: bool = False

    specification_artifact: ArtifactReference | None = None


class EvidenceReference(ContractModel):
    """
    Canonical pointer to a piece or bundle of gate/qualification evidence.
    """

    evidence_id: EvidenceId

    run_id: RunId

    evidence_type: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    artifact: ArtifactReference

    created_at: AwareDatetime

    independent_from_change_agent: bool = False


class UncertaintyStatement(ContractModel):
    """
    Statistical uncertainty associated with ONE named measurement.

    ReleaseGateService may produce several of these.

    Example:

        metric_name = "mutation_detection_rate"
        estimate = 0.92
        lower_bound = 0.86
        upper_bound = 0.96
        sample_size = 100

    The contract does NOT prescribe which statistical method must be used.

    `method` records it explicitly.
    """

    metric_name: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    estimate: float

    lower_bound: float
    upper_bound: float

    confidence_level: Annotated[
        float,
        Field(gt=0.0, lt=1.0),
    ]

    sample_size: Annotated[
        int,
        Field(ge=1),
    ]

    method: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.lower_bound > self.upper_bound:
            raise ValueError(
                "Uncertainty lower_bound cannot exceed upper_bound."
            )

        if not (
            self.lower_bound
            <= self.estimate
            <= self.upper_bound
        ):
            raise ValueError(
                "Uncertainty estimate must lie within its interval."
            )

        return self

