from datetime import datetime, timezone

import pytest

from execution_environment.errors import (
    SandboxPolicyError,
)
from execution_environment.models import (
    ExecutionCommand,
    ExecutionRequest,
    NetworkMode,
    NetworkPolicy,
    ResourceLimits,
    SandboxProfile,
    SandboxRole,
)
from execution_environment.policy import (
    SandboxPolicyEngine,
)


NOW = datetime.now(timezone.utc)


def make_profile() -> SandboxProfile:
    return SandboxProfile(
        profile_id="release-gate-v1",
        role=SandboxRole.RELEASE_GATE,
        runner_image="verifier",
        runner_image_digest=(
            "sha256:"
            + ("1" * 64)
        ),
        limits=ResourceLimits(),
        network=NetworkPolicy(
            mode=NetworkMode.DENY_ALL
        ),
        allowed_executables=(
            "python",
            "pytest",
        ),
    )


def make_request(
    executable: str = "pytest",
) -> ExecutionRequest:
    return ExecutionRequest(
        request_id="request-001",
        run_id="run-001",
        component_name="ReleaseGateService",
        role=SandboxRole.RELEASE_GATE,
        profile_id="release-gate-v1",
        inputs=(),
        command=ExecutionCommand(
            executable=executable,
            arguments=("-q",),
        ),
        created_at=NOW,
    )


def test_allowed_executable_passes() -> None:
    SandboxPolicyEngine().validate(
        request=make_request(),
        profile=make_profile(),
    )


def test_unapproved_executable_is_rejected() -> None:
    with pytest.raises(SandboxPolicyError):
        SandboxPolicyEngine().validate(
            request=make_request(
                executable="unapproved-program"
            ),
            profile=make_profile(),
        )


def test_secret_like_environment_variable_is_rejected() -> None:
    request = make_request().model_copy(
        update={
            "command": ExecutionCommand(
                executable="pytest",
                environment={
                    "PRODUCTION_TOKEN": "must-not-enter-sandbox"
                },
            )
        }
    )

    with pytest.raises(SandboxPolicyError):
        SandboxPolicyEngine().validate(
            request=request,
            profile=make_profile(),
        )
