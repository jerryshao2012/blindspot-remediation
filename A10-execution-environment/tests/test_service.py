from datetime import datetime, timezone

from execution_environment.local_runner import (
    DeterministicTestRunner,
)
from execution_environment.models import (
    ExecutionCommand,
    ExecutionRequest,
    ExecutionStatus,
    NetworkMode,
    NetworkPolicy,
    ResourceLimits,
    SandboxProfile,
    SandboxRole,
)
from execution_environment.service import (
    ExecutionEnvironmentService,
)


NOW = datetime.now(timezone.utc)


def test_execution_returns_provenance_receipt() -> None:
    profile = SandboxProfile(
        profile_id="release-gate-v1",
        role=SandboxRole.RELEASE_GATE,
        runner_image="engineering-verifier",
        runner_image_digest=(
            "sha256:"
            + ("1" * 64)
        ),
        limits=ResourceLimits(),
        network=NetworkPolicy(
            mode=NetworkMode.DENY_ALL
        ),
        allowed_executables=(
            "pytest",
        ),
    )

    service = ExecutionEnvironmentService(
        profiles=(profile,),
        runner=DeterministicTestRunner(),
    )

    request = ExecutionRequest(
        request_id="request-001",
        run_id="run-001",
        component_name="ReleaseGateService",
        role=SandboxRole.RELEASE_GATE,
        profile_id="release-gate-v1",
        inputs=(),
        command=ExecutionCommand(
            executable="pytest",
            arguments=("-q",),
        ),
        created_at=NOW,
    )

    receipt = service.execute(request)

    assert receipt.status == ExecutionStatus.SUCCEEDED

    assert receipt.exit_code == 0

    assert receipt.cleanup_completed is True

    assert len(receipt.stdout_sha256) == 64

    assert len(receipt.stderr_sha256) == 64

    assert len(receipt.environment_fingerprint) == 64

    assert len(receipt.policy_fingerprint) == 64
