"""
Primary Component 6 orchestration service.

This class deliberately remains small.

Its responsibility is coordination, not implementing every concern itself.

It coordinates:

    correlation
    storage
    telemetry emission
    aggregation
    SLO evaluation

The calculation and policy classes remain independently testable.
"""

from __future__ import annotations

from datetime import datetime

from .aggregation import OperationalMetricsCalculator
from .correlation import DeploymentCorrelationService
from .models import (
    DeploymentIdentity,
    OperationalHealthDecision,
    OperationalPolicy,
    OperationalWindow,
    RuntimeObservation,
)
from .policy import SLOEvaluator
from .storage import OperationalEvidenceRepository
from .telemetry import OperationalTelemetryEmitter


class OperationalMetricsService:
    """
    Application-level facade for Component 6.

    Typical production lifecycle:

        register deployment

        ↓

        ingest runtime observations

        ↓

        periodically aggregate an operational window

        ↓

        evaluate deterministic SLO policy

        ↓

        preserve the resulting operational evidence
    """

    def __init__(
        self,
        *,
        repository: OperationalEvidenceRepository,
        correlation: DeploymentCorrelationService,
        calculator: OperationalMetricsCalculator,
        evaluator: SLOEvaluator,
        telemetry: OperationalTelemetryEmitter,
    ) -> None:
        self._repository = repository
        self._correlation = correlation
        self._calculator = calculator
        self._evaluator = evaluator
        self._telemetry = telemetry

    def register_deployment(
        self,
        deployment: DeploymentIdentity,
    ) -> None:
        self._repository.register_deployment(
            deployment
        )

    def record_observation(
        self,
        *,
        deployment: DeploymentIdentity,
        observation: RuntimeObservation,
    ) -> None:
        self._correlation.validate_observation(
            deployment=deployment,
            observation=observation,
        )

        self._repository.write_observation(
            observation
        )

        self._telemetry.emit(
            observation
        )

    def evaluate_window(
        self,
        *,
        deployment: DeploymentIdentity,
        window_start: datetime,
        window_end: datetime,
        policy: OperationalPolicy,
    ) -> tuple[
        OperationalWindow,
        OperationalHealthDecision,
    ]:
        observations = (
            self._repository.observations_for_deployment(
                deployment.deployment_id
            )
        )

        window = self._calculator.calculate(
            deployment_id=deployment.deployment_id,
            service_name=deployment.service_name,
            observations=observations,
            window_start=window_start,
            window_end=window_end,
        )

        decision = self._evaluator.evaluate(
            window=window,
            policy=policy,
        )

        self._repository.write_window(
            window
        )

        self._repository.write_health_decision(
            decision
        )

        return window, decision
