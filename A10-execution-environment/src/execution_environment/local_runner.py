"""
Safe test runner for unit/integration testing of Component 10 itself.

IMPORTANT:

This runner does NOT execute arbitrary operating-system commands.

It exists so junior developers and data scientists can run the Component 10
test suite without Docker, Azure credentials, or a cloud sandbox.

Actual candidate code must use the Azure/container runner in deployed
environments.

This implementation deliberately returns deterministic synthetic execution
results rather than weakening the architecture by executing generated code
directly on a developer laptop.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .models import (
    ExecutionRequest,
    ExecutionStatus,
    RunnerResult,
    SandboxProfile,
)
from .ports import SandboxRunnerPort


class DeterministicTestRunner(
    SandboxRunnerPort
):
    """
    Non-executing runner used for tests and demonstrations.

    This is NOT a production sandbox.
    """

    def execute(
        self,
        *,
        request: ExecutionRequest,
        profile: SandboxProfile,
    ) -> RunnerResult:
        started = datetime.now(
            timezone.utc
        )

        stdout = (
            "Component 10 deterministic test runner\n"
            f"request_id={request.request_id}\n"
            f"profile_id={profile.profile_id}\n"
            f"executable={request.command.executable}\n"
        ).encode("utf-8")

        completed = datetime.now(
            timezone.utc
        )

        return RunnerResult(
            sandbox_id=f"test-{uuid4()}",
            status=ExecutionStatus.SUCCEEDED,
            started_at=started,
            completed_at=completed,
            exit_code=0,
            stdout=stdout,
            stderr=b"",
            outputs=(),
            cleanup_completed=True,
        )
