"""
Primary Component 10 service.

The service performs:

    profile resolution
    deterministic policy enforcement
    environment fingerprinting
    infrastructure invocation
    output-size enforcement
    execution-receipt creation

It deliberately does NOT:

    judge correctness
    interpret test meaning
    decide release
    generate commands using an LLM
"""

from __future__ import annotations

from .errors import (
    OutputLimitExceededError,
    UnsupportedSandboxRoleError,
)
from .hashing import (
    fingerprint,
    sha256_bytes,
)
from .models import (
    ExecutionReceipt,
    ExecutionRequest,
    SandboxProfile,
)
from .policy import SandboxPolicyEngine
from .ports import SandboxRunnerPort


class ExecutionEnvironmentService:
    """
    Controlled gateway to executable compute.

    All Components 2, 3 and 5 should use this service rather than creating
    arbitrary subprocesses themselves.
    """

    def __init__(
        self,
        *,
        profiles: tuple[SandboxProfile, ...],
        runner: SandboxRunnerPort,
        policy_engine: SandboxPolicyEngine | None = None,
    ) -> None:
        self._profiles = {
            profile.profile_id: profile
            for profile in profiles
        }

        if len(self._profiles) != len(profiles):
            raise ValueError(
                "Sandbox profile identifiers must be unique."
            )

        self._runner = runner

        self._policy = (
            policy_engine
            or SandboxPolicyEngine()
        )

    def execute(
        self,
        request: ExecutionRequest,
    ) -> ExecutionReceipt:
        profile = self._resolve_profile(
            request.profile_id
        )

        self._policy.validate(
            request=request,
            profile=profile,
        )

        policy_fingerprint = fingerprint(
            profile
        )

        environment_fingerprint = fingerprint({
            "runner_image": profile.runner_image,
            "runner_image_digest": (
                profile.runner_image_digest
            ),
            "role": profile.role.value,
            "profile_id": profile.profile_id,
            "network": profile.network,
            "limits": profile.limits,
            "inputs": [
                {
                    "artifact_id": artifact.artifact_id,
                    "sha256": artifact.sha256,
                }
                for artifact in request.inputs
            ],
        })

        result = self._runner.execute(
            request=request,
            profile=profile,
        )

        stdout_size = len(result.stdout)
        stderr_size = len(result.stderr)

        total_output = (
            stdout_size + stderr_size
        )

        if total_output > profile.limits.output_bytes:
            raise OutputLimitExceededError(
                "Execution output exceeded configured limit: "
                f"{total_output} > "
                f"{profile.limits.output_bytes}"
            )

        return ExecutionReceipt(
            request_id=request.request_id,
            run_id=request.run_id,
            sandbox_id=result.sandbox_id,
            profile_id=profile.profile_id,
            role=profile.role,
            status=result.status,
            runner_image=profile.runner_image,
            runner_image_digest=(
                profile.runner_image_digest
            ),
            started_at=result.started_at,
            completed_at=result.completed_at,
            exit_code=result.exit_code,
            stdout_sha256=sha256_bytes(
                result.stdout
            ),
            stderr_sha256=sha256_bytes(
                result.stderr
            ),
            stdout_bytes=stdout_size,
            stderr_bytes=stderr_size,
            outputs=result.outputs,
            environment_fingerprint=(
                environment_fingerprint
            ),
            policy_fingerprint=(
                policy_fingerprint
            ),
            cleanup_completed=(
                result.cleanup_completed
            ),
            failure_reason=result.failure_reason,
        )

    def _resolve_profile(
        self,
        profile_id: str,
    ) -> SandboxProfile:
        profile = self._profiles.get(
            profile_id
        )

        if profile is None:
            raise UnsupportedSandboxRoleError(
                f"Unknown sandbox profile: {profile_id!r}"
            )

        return profile
