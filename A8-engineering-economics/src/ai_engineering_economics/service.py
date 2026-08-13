"""Primary Component 8 application service."""

from __future__ import annotations

from datetime import datetime

from .aggregation import EngineeringEconomicsCalculator
from .models import (
    BaselineMetrics,
    EconomicsSettings,
    EngineeringEconomicsReport,
    ValueAssessment,
)
from .policy import ValueAssessmentService
from .storage import EngineeringEconomicsRepository


class EngineeringEconomicsService:
    """
    Coordinate measurement, reporting, and value assessment.

    Source ingestion and normalization are repository responsibilities.

    Measurement arithmetic and policy evaluation remain deterministic and
    independently testable.
    """

    def __init__(
        self,
        *,
        repository: EngineeringEconomicsRepository,
        calculator: EngineeringEconomicsCalculator,
        assessor: ValueAssessmentService,
    ) -> None:
        self._repository = repository
        self._calculator = calculator
        self._assessor = assessor

    def create_report(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        settings: EconomicsSettings,
    ) -> EngineeringEconomicsReport:
        records = self._repository.normalized_records(
            window_start=window_start,
            window_end=window_end,
        )

        report = self._calculator.calculate(
            records=records,
            window_start=window_start,
            window_end=window_end,
            currency=settings.currency,
            confidence_level=settings.policy.confidence_level,
        )

        self._repository.write_report(report)

        return report

    def assess_value(
        self,
        *,
        report: EngineeringEconomicsReport,
        baseline: BaselineMetrics,
        settings: EconomicsSettings,
    ) -> ValueAssessment:
        assessment = self._assessor.evaluate(
            report=report,
            baseline=baseline,
            policy=settings.policy,
        )

        self._repository.write_value_assessment(
            assessment
        )

        return assessment
