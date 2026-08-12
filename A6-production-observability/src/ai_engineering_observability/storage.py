"""
Operational evidence storage boundary.

The domain service should not care whether observations ultimately reside in:

    Azure Monitor / Log Analytics
    Azure Data Explorer
    Blob Storage
    another approved telemetry platform

That decision belongs to infrastructure configuration.

The abstract interface prevents Azure-specific persistence logic from leaking
into operational calculations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    DeploymentIdentity,
    OperationalHealthDecision,
    OperationalWindow,
    RuntimeObservation,
)


class OperationalEvidenceRepository(ABC):
    @abstractmethod
    def register_deployment(
        self,
        deployment: DeploymentIdentity,
    ) -> None:
        raise NotImplementedError(
            "A production OperationalEvidenceRepository must be supplied."
        )

    @abstractmethod
    def write_observation(
        self,
        observation: RuntimeObservation,
    ) -> None:
        raise NotImplementedError(
            "A production OperationalEvidenceRepository must be supplied."
        )

    @abstractmethod
    def write_window(
        self,
        window: OperationalWindow,
    ) -> None:
        raise NotImplementedError(
            "A production OperationalEvidenceRepository must be supplied."
        )

    @abstractmethod
    def write_health_decision(
        self,
        decision: OperationalHealthDecision,
    ) -> None:
        raise NotImplementedError(
            "A production OperationalEvidenceRepository must be supplied."
        )

    @abstractmethod
    def observations_for_deployment(
        self,
        deployment_id: str,
    ) -> tuple[RuntimeObservation, ...]:
        raise NotImplementedError(
            "A production OperationalEvidenceRepository must be supplied."
        )
