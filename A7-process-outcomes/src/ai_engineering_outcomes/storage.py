"""
Storage boundary for Component 7.

The domain layer deliberately does not assume whether BMO ultimately stores
these records in:

    Azure Data Explorer
    Azure SQL
    Microsoft Fabric
    an enterprise data platform
    an approved telemetry/event store

The production adapter should be chosen according to enterprise architecture.

No fake production implementation is silently supplied.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    AttributionAssessment,
    KPIObservation,
    ProcessEvent,
    ProcessWindow,
)


class OutcomeEvidenceRepository(ABC):
    @abstractmethod
    def write_process_event(
        self,
        event: ProcessEvent,
    ) -> None:
        raise NotImplementedError(
            "A production OutcomeEvidenceRepository must be supplied."
        )

    @abstractmethod
    def process_events_for_deployment(
        self,
        deployment_id: str,
    ) -> tuple[ProcessEvent, ...]:
        raise NotImplementedError(
            "A production OutcomeEvidenceRepository must be supplied."
        )

    @abstractmethod
    def write_process_window(
        self,
        window: ProcessWindow,
    ) -> None:
        raise NotImplementedError(
            "A production OutcomeEvidenceRepository must be supplied."
        )

    @abstractmethod
    def write_kpi_observation(
        self,
        observation: KPIObservation,
    ) -> None:
        raise NotImplementedError(
            "A production OutcomeEvidenceRepository must be supplied."
        )

    @abstractmethod
    def write_attribution_assessment(
        self,
        assessment: AttributionAssessment,
    ) -> None:
        raise NotImplementedError(
            "A production OutcomeEvidenceRepository must be supplied."
        )
