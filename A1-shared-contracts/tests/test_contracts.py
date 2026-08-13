from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ai_engineering_contracts.enums import (
    ArtifactKind,
    CheckStatus,
    ControlSeverity,
    EvidenceStrategy,
    ExecutionStatus,
    GateDecision,
)
from ai_engineering_contracts.example import build_example_request
from ai_engineering_contracts.models import (
    ArtifactReference,
    CheckResult,
    ControlResult,
    EvidenceBudget,
    ExecutionResult,
    GateResult,
    TokenUsage,
)

NOW = datetime(2026, 8, 6, 18, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 8, 6, 18, 1, tzinfo=timezone.utc)
BASE_COMMIT = "a" * 40
CANDIDATE_COMMIT = "b" * 40
SHA256_A = "1" * 64
SHA256_B = "2" * 64


def artifact(
    artifact_id: str,
    kind: ArtifactKind,
    sha256: str = SHA256_A,
) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=artifact_id,
        kind=kind,
        uri=f"https://storage.example.test/container/{artifact_id}.json",
        sha256=sha256,
        media_type="application/json",
        size_bytes=100,
        immutable=True,
        created_at=NOW,
    )


def test_task_request_round_trip_and_fingerprint_are_stable() -> None:
    request = build_example_request()
    restored = type(request).model_validate_json(request.model_dump_json())
    assert restored == request
    assert restored.content_fingerprint() == request.content_fingerprint()
    assert len(request.content_fingerprint()) == 64


def test_unknown_fields_are_rejected() -> None:
    raw = build_example_request().to_json_compatible_dict()
    raw["unexpected_field"] = "must fail"
    with pytest.raises(ValidationError):
        type(build_example_request()).model_validate(raw)


def test_contract_models_are_immutable() -> None:
    request = build_example_request()
    with pytest.raises(ValidationError):
        request.run_id = "different-run"  # type: ignore[misc]


def test_token_usage_addition_does_not_double_count_cached_tokens() -> None:
    first = TokenUsage(
        input_tokens=1_000,
        cached_input_tokens=400,
        output_tokens=200,
        reasoning_tokens=100,
        llm_calls=2,
        estimated_cost=1.25,
    )
    second = TokenUsage(
        input_tokens=500,
        cached_input_tokens=100,
        output_tokens=50,
        reasoning_tokens=0,
        llm_calls=1,
        estimated_cost=0.50,
    )
    total = first.add(second)
    assert total.input_tokens == 1_500
    assert total.cached_input_tokens == 500
    assert total.processed_tokens == 1_850
    assert total.estimated_cost == pytest.approx(1.75)


def test_completed_execution_requires_candidate_and_patch() -> None:
    with pytest.raises(ValidationError):
        ExecutionResult(
            run_id="run-1",
            executor_version="1.0.0",
            status=ExecutionStatus.COMPLETED,
            base_commit=BASE_COMMIT,
            candidate_commit=None,
            patch_artifact=None,
            execution_trace=artifact(
                "trace-1",
                ArtifactKind.EXECUTION_TRACE,
            ),
            started_at=NOW,
            completed_at=LATER,
        )


def test_executor_check_cannot_claim_release_authority() -> None:
    with pytest.raises(ValidationError):
        CheckResult(
            check_id="local-test-1",
            name="Local unit tests",
            status=CheckStatus.PASSED,
            started_at=NOW,
            completed_at=LATER,
            exit_code=0,
            summary="Tests passed in the executor workspace.",
            is_authoritative_release_evidence=True,
        )


def test_pass_gate_rejects_failed_mandatory_control() -> None:
    failed_control = ControlResult(
        control_id="mandatory-tests",
        name="Mandatory acceptance tests",
        status=CheckStatus.FAILED,
        severity=ControlSeverity.MANDATORY,
        strategy=EvidenceStrategy.EXISTING_TESTS,
        deterministic_authority=True,
        summary="One mandatory test failed.",
        started_at=NOW,
        completed_at=LATER,
        reasons=["Expected result did not match actual result."],
    )
    with pytest.raises(ValidationError):
        GateResult(
            run_id="run-1",
            gate_version="1.0.0",
            policy_version="1.0.0",
            decision=GateDecision.PASS,
            base_commit=BASE_COMMIT,
            candidate_commit=CANDIDATE_COMMIT,
            evidence_package=artifact(
                "evidence-1",
                ArtifactKind.EVIDENCE_PACKAGE,
            ),
            hard_control_results=[failed_control],
            decision_reasons=["All release requirements were reportedly met."],
            evidence_rounds_completed=1,
            started_at=NOW,
            completed_at=LATER,
        )


def test_dominant_failure_requires_fail_decision() -> None:
    dominant_failure = ControlResult(
        control_id="secret-detection",
        name="Secret detection",
        status=CheckStatus.FAILED,
        severity=ControlSeverity.DOMINANT_FAILURE,
        strategy=EvidenceStrategy.SECURITY_SCANNING,
        deterministic_authority=True,
        summary="A credential-like value was detected.",
        started_at=NOW,
        completed_at=LATER,
        reasons=["Candidate cannot proceed while the finding is unresolved."],
    )
    with pytest.raises(ValidationError):
        GateResult(
            run_id="run-2",
            gate_version="1.0.0",
            policy_version="1.0.0",
            decision=GateDecision.HUMAN_REVIEW_REQUIRED,
            base_commit=BASE_COMMIT,
            candidate_commit=CANDIDATE_COMMIT,
            evidence_package=artifact(
                "evidence-2",
                ArtifactKind.EVIDENCE_PACKAGE,
                SHA256_B,
            ),
            hard_control_results=[dominant_failure],
            decision_reasons=["Human review was requested."],
            evidence_rounds_completed=1,
            started_at=NOW,
            completed_at=LATER,
        )


def test_evidence_budget_disallows_ai_strategy_without_llm_budget() -> None:
    with pytest.raises(ValidationError):
        EvidenceBudget(
            maximum_llm_calls=0,
            maximum_input_tokens=0,
            maximum_output_tokens=0,
            maximum_evidence_rounds=1,
            maximum_generated_tests=10,
            maximum_mutants=10,
            maximum_tool_calls=100,
            maximum_runtime_seconds=600,
            maximum_estimated_cost=0.0,
            allowed_strategies=[
                EvidenceStrategy.REQUIREMENT_FIRST_TEST_SYNTHESIS
            ],
        )


def test_immutable_artifact_requires_digest() -> None:
    with pytest.raises(ValidationError):
        ArtifactReference(
            artifact_id="missing-digest",
            kind=ArtifactKind.PATCH,
            uri="https://storage.example.test/container/patch.diff",
            sha256=None,
            media_type="text/x-diff",
            immutable=True,
            created_at=NOW,
        )
