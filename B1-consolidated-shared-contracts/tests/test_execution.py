from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ai_engineering_contracts import (
    ArtifactReference,
    ExecutionCommand,
    ExecutionRequest,
    SandboxRole,
)


NOW = datetime.now(timezone.utc)


def artifact() -> ArtifactReference:
    return ArtifactReference(
        artifact_id="repo-snapshot",
        uri="artifact://repo-snapshot",
        sha256="a" * 64,
        media_type="application/x-tar",
        created_at=NOW,
        producer_component="ArtifactBroker",
    )


def test_execution_request_is_structured() -> None:
    request = ExecutionRequest(
        request_id="execution-1",
        run_id="run-1",
        component_name="ReleaseGateService",
        role=SandboxRole.RELEASE_GATE,
        profile_id="release-gate-v1",
        inputs=(artifact(),),
        command=ExecutionCommand(
            executable="pytest",
            arguments=("-q",),
        ),
        created_at=NOW,
    )

    assert request.command.executable == "pytest"


def test_naive_timestamp_is_rejected() -> None:
    from datetime import datetime

    with pytest.raises(ValidationError):
        ExecutionRequest(
            request_id="execution-1",
            run_id="run-1",
            component_name="ReleaseGateService",
            role=SandboxRole.RELEASE_GATE,
            profile_id="release-gate-v1",
            inputs=(artifact(),),
            command=ExecutionCommand(
                executable="pytest",
            ),
            created_at=datetime(2026, 8, 7, 10, 0, 0),
        )

