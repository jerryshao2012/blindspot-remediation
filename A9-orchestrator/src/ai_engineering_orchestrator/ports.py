"""
Interfaces between Component 9 and the surrounding platform.

The orchestrator depends on abstractions.

It does not import Azure SDKs, Jira clients, Git libraries, or model clients.

This makes the orchestration logic independently testable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    CandidatePatch,
    ChangeExecutionResult,
    OrchestrationRun,
    ReleaseGateResult,
    RunOutcome,
    TaskDefinition,
    TaskRequest,
)


class ChangeExecutionPort(ABC):
    """Component 2 boundary."""

    @abstractmethod
    def execute(
        self,
        *,
        run_id: str,
        task: TaskRequest,
        definition: TaskDefinition,
    ) -> ChangeExecutionResult:
        raise NotImplementedError(
            "A ChangeExecutionPort implementation must be supplied."
        )


class ReleaseGatePort(ABC):
    """Component 3 boundary."""

    @abstractmethod
    def evaluate(
        self,
        *,
        run_id: str,
        task: TaskRequest,
        candidate: CandidatePatch,
        definition: TaskDefinition,
        evidence_cycle: int,
    ) -> ReleaseGateResult:
        raise NotImplementedError(
            "A ReleaseGatePort implementation must be supplied."
        )


class EvidencePort(ABC):
    """Component 4 boundary."""

    @abstractmethod
    def record_run(
        self,
        run: OrchestrationRun,
    ) -> str:
        """
        Persist the orchestration run and return an immutable evidence reference.
        """

        raise NotImplementedError(
            "An EvidencePort implementation must be supplied."
        )

    @abstractmethod
    def record_outcome(
        self,
        outcome: RunOutcome,
    ) -> str:
        raise NotImplementedError(
            "An EvidencePort implementation must be supplied."
        )


class ReleasePort(ABC):
    """
    Boundary to the approved deployment/release mechanism.

    Component 9 authorizes invocation of the release mechanism.

    It should not contain bespoke deployment scripts for every repository.
    """

    @abstractmethod
    def release(
        self,
        *,
        run_id: str,
        task: TaskRequest,
        candidate: CandidatePatch,
    ) -> str:
        """
        Release candidate through the approved delivery mechanism.

        Return a deployment/evidence reference.
        """

        raise NotImplementedError(
            "A ReleasePort implementation must be supplied."
        )
