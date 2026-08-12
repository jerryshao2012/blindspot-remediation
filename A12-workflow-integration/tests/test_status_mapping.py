from engineering_workflow_integration.models import (
    EngineeringRunReference,
    ExternalStatusState,
    GateOutcome,
    GatePublication,
    PullRequestReference,
    WorkflowProvider,
)
from engineering_workflow_integration.status_mapping import (
    map_gate_publication,
)


def publication(
    outcome: GateOutcome,
) -> GatePublication:

    run = EngineeringRunReference(
        run_id="run-001",
        task_request_id="request-001",
        task_type="X1",
        task_specification_sha256="a" * 64,
    )

    pull_request = PullRequestReference(
        provider=WorkflowProvider.AZURE_DEVOPS,
        organization="example-org",
        project="example-project",
        repository_id="repo-001",
        pull_request_id="42",
        source_commit_sha="abcdef1234567",
    )

    return GatePublication(
        run=run,
        pull_request=pull_request,
        outcome=outcome,
        summary=f"Gate result: {outcome.value}",
        decision_sha256="b" * 64,
    )


def test_pass_maps_to_success() -> None:
    result = map_gate_publication(
        publication(GateOutcome.PASS)
    )

    assert result.state == ExternalStatusState.SUCCEEDED


def test_fail_maps_to_failed() -> None:
    result = map_gate_publication(
        publication(GateOutcome.FAIL)
    )

    assert result.state == ExternalStatusState.FAILED


def test_more_evidence_remains_blocking() -> None:
    result = map_gate_publication(
        publication(GateOutcome.MORE_EVIDENCE)
    )

    assert result.state == ExternalStatusState.PENDING


def test_human_review_remains_blocking() -> None:
    result = map_gate_publication(
        publication(GateOutcome.HUMAN_REVIEW_REQUIRED)
    )

    assert result.state == ExternalStatusState.PENDING
