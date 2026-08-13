"""
Canonical ReleaseGate boundary contracts.

ReleaseGateService should return ONE GateDecision object.

The Orchestrator should never need to infer meaning from arbitrary strings or
inspect internal release-gate classes.
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
from .enums import GateDisposition
from .evidence import (
    EvidenceReference,
    UncertaintyStatement,
)
from .ids import (
    CandidateId,
    DecisionId,
    RunId,
)
from .references import ArtifactReference
from .usage import AIUsage


class GateDecision(ContractModel):
    """
    Authoritative candidate-level result emitted by Component 3.

    A PASS with zero evidence is rejected by schema validation.

    This does NOT imply that "some evidence exists" proves the gate is good.
    Component 5 still evaluates the quality of the gate itself.
    """

    schema_version: str = CONTRACT_SCHEMA_VERSION

    decision_id: DecisionId

    run_id: RunId
    candidate_id: CandidateId

    disposition: GateDisposition

    gate_policy: ArtifactReference

    evidence: tuple[
        EvidenceReference,
        ...,
    ]

    uncertainty: tuple[
        UncertaintyStatement,
        ...,
    ] = ()

    reason_codes: tuple[
        str,
        ...,
    ] = ()

    # Used only when the gate explicitly requests another evidence cycle.
    requested_evidence_types: tuple[
        str,
        ...,
    ] = ()

    ai_usage: AIUsage = Field(
        default_factory=AIUsage
    )

    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if not self.evidence:
            raise ValueError(
                "A GateDecision must reference at least one evidence item."
            )

        if (
            self.disposition
            == GateDisposition.MORE_EVIDENCE_REQUIRED
            and not self.requested_evidence_types
        ):
            raise ValueError(
                "MORE_EVIDENCE_REQUIRED must specify the additional "
                "evidence family or families being requested."
            )

        if (
            self.disposition
            != GateDisposition.MORE_EVIDENCE_REQUIRED
            and self.requested_evidence_types
        ):
            raise ValueError(
                "requested_evidence_types are only valid for "
                "MORE_EVIDENCE_REQUIRED."
            )

        return self


class HumanReviewSignal(ContractModel):
    """
    Signal sent OUT of the autonomous pipeline.

    It does not represent the human's eventual decision.

    Component 12 may translate this into the enterprise workflow.
    """

    run_id: RunId
    candidate_id: CandidateId

    gate_decision_id: DecisionId

    reasons: tuple[str, ...]

    evidence: tuple[
        EvidenceReference,
        ...,
    ]

    created_at: AwareDatetime

