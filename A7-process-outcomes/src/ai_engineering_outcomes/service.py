"""
Primary Component 7 orchestration service.

The class is intentionally small.

It coordinates:

    process-event validation
    correlation
    persistence
    aggregation
    KPI evidence
    attribution evidence

It does NOT:

    run the engineering agent
    gate releases
    monitor infrastructure health
    invent KPI definitions
    claim causality automatically
"""

from __future__ import annotations

from datetime import datetime

from .aggregation import ProcessMetricsCalculator
from .attribution import AttributionAssessor
from .correlation import OutcomeCorrelationService
from .models import (
    AttributionAssessment,
    KPIObservation,
    ProcessEvent,
    ProcessWindow,
)
from .storage import OutcomeEvidenceRepository


class ProcessOutcomeService:
    """Application facade for Component 7."""

    def __init__(
        self,
        *,
        repository: OutcomeEvidenceRepository,
        correlation: OutcomeCorrelationService,
        calculator: ProcessMetricsCalculator,
        attribution: AttributionAssessor,
    ) -> None:
        self._repository = repository
        self._correlation = correlation
        self._calculator = calculator
        self._attribution = attribution

    def record_process_event(
        self,
        *,
        expected_deployment_id: str,
        expected_release_id: str,
        expected_originating_run_id: str,
        event: ProcessEvent,
    ) -> None:
        self._correlation.validate_process_event(
            expected_deployment_id=expected_deployment_id,
            expected_release_id=expected_release_id,
            expected_originating_run_id=expected_originating_run_id,
            event=event,
        )

        self._repository.write_process_event(
            event
        )

    def calculate_process_window(
        self,
        *,
        deployment_id: str,
        process_name: str,
        window_start: datetime,
        window_end: datetime,
    ) -> ProcessWindow:
        events = (
            self._repository.process_events_for_deployment(
                deployment_id
            )
        )

        window = self._calculator.calculate(
            deployment_id=deployment_id,
            process_name=process_name,
            events=events,
            window_start=window_start,
            window_end=window_end,
        )

        self._repository.write_process_window(
            window
        )

        return window

    def record_kpi(
        self,
        observation: KPIObservation,
    ) -> None:
        self._repository.write_kpi_observation(
            observation
        )

    def assess_before_after(
        self,
        *,
        deployment_id: str,
        baseline: KPIObservation,
        treatment: KPIObservation,
        confidence_level: float = 0.95,
    ) -> AttributionAssessment:
        assessment = self._attribution.assess_before_after(
            deployment_id=deployment_id,
            baseline=baseline,
            treatment=treatment,
            confidence_level=confidence_level,
        )

        self._repository.write_attribution_assessment(
            assessment
        )

        return assessment
