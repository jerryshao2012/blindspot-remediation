"""
Infrastructure boundaries for Component 10.

The domain service should not know whether the execution happens in:

    Azure Container Apps Jobs
    an enterprise CI runner
    Azure Batch
    AKS
    a hardened local development container

That is an infrastructure decision.

The security contract remains the same.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    ExecutionRequest,
    RunnerResult,
    SandboxProfile,
)


class SandboxRunnerPort(ABC):
    """Infrastructure execution boundary."""

    @abstractmethod
    def execute(
        self,
        *,
        request: ExecutionRequest,
        profile: SandboxProfile,
    ) -> RunnerResult:
        raise NotImplementedError(
            "A SandboxRunnerPort implementation must be supplied."
        )
