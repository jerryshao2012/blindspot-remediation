from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ai_engineering_contracts import (
    AIUsage,
    ArtifactReference,
    EvidenceReference,
    GateDecision,
    GateDisposition,
)


NOW = datetime.now(timezone.utc)


def artifact(
    identifier: str,
    char: str,
) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=identifier,
        uri=f"artifact://{identifier}",
        sha256=char * 64,
        media_type="application/json",
        created_at=NOW,
        producer_component="ReleaseGateService",
    )


def evidence() -> EvidenceReference:
    return EvidenceReference(
        evidence_id="evidence-1",
        run_id="run-1",
        evidence_type="independent_tests",
        artifact=artifact("test-report", "a"),
        created_at=NOW,
        independent_from_change_agent=True,
    )


def test_pass_requires_evidence() -> None:
    decision = GateDecision(
        decision_id="decision-1",
        run_id="run-1",
        candidate_id="candidate-1",
        disposition=GateDisposition.PASS,
        gate_policy=artifact("gate-policy", "b"),
        evidence=(evidence(),),
        ai_usage=AIUsage(
            input_tokens=1000,
            output_tokens=100,
            request_count=2,
        ),
        created_at=NOW,
    )

    assert decision.disposition == GateDisposition.PASS


def test_gate_decision_without_evidence_is_invalid() -> None:
    with pytest.raises(ValidationError):
        GateDecision(
            decision_id="decision-1",
            run_id="run-1",
            candidate_id="candidate-1",
            disposition=GateDisposition.PASS,
            gate_policy=artifact("gate-policy", "b"),
            evidence=(),
            created_at=NOW,
        )


def test_more_evidence_must_identify_requested_evidence() -> None:
    with pytest.raises(ValidationError):
        GateDecision(
            decision_id="decision-1",
            run_id="run-1",
            candidate_id="candidate-1",
            disposition=GateDisposition.MORE_EVIDENCE_REQUIRED,
            gate_policy=artifact("gate-policy", "b"),
            evidence=(evidence(),),
            requested_evidence_types=(),
            created_at=NOW,
        )


def test_more_evidence_with_explicit_request_is_valid() -> None:
    decision = GateDecision(
        decision_id="decision-1",
        run_id="run-1",
        candidate_id="candidate-1",
        disposition=GateDisposition.MORE_EVIDENCE_REQUIRED,
        gate_policy=artifact("gate-policy", "b"),
        evidence=(evidence(),),
        requested_evidence_types=(
            "additional_mutation_analysis",
        ),
        created_at=NOW,
    )

    assert decision.requested_evidence_types == (
        "additional_mutation_analysis",
    )

