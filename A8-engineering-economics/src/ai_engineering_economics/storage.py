"""
Storage and source-integration boundaries.

The normalized economics domain must not depend directly on one Jira schema,
one cloud billing format, or one labour-recording tool.

Adapters may read from:

    Jira
    Azure DevOps
    deployment systems
    Components 4–7
    Azure Cost Management exports
    model-provider usage
    Finance-approved labour-cost tables

and convert those observations into Component 8 contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from .models import (
    AIUsageRecord,
    CostRecord,
    EngineeringEconomicsReport,
    HumanEffortRecord,
    ValueAssessment,
    WorkItemEconomicsRecord,
    WorkItemEvent,
)


class EngineeringEconomicsRepository(ABC):
    @abstractmethod
    def write_work_event(
        self,
        event: WorkItemEvent,
    ) -> None:
        raise NotImplementedError(
            "A production EngineeringEconomicsRepository must be supplied."
        )

    @abstractmethod
    def write_human_effort(
        self,
        effort: HumanEffortRecord,
    ) -> None:
        raise NotImplementedError(
            "A production EngineeringEconomicsRepository must be supplied."
        )

    @abstractmethod
    def write_ai_usage(
        self,
        usage: AIUsageRecord,
    ) -> None:
        raise NotImplementedError(
            "A production EngineeringEconomicsRepository must be supplied."
        )

    @abstractmethod
    def write_cost(
        self,
        cost: CostRecord,
    ) -> None:
        raise NotImplementedError(
            "A production EngineeringEconomicsRepository must be supplied."
        )

    @abstractmethod
    def normalized_records(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> tuple[WorkItemEconomicsRecord, ...]:
        raise NotImplementedError(
            "A production EngineeringEconomicsRepository must be supplied."
        )

    @abstractmethod
    def write_report(
        self,
        report: EngineeringEconomicsReport,
    ) -> None:
        raise NotImplementedError(
            "A production EngineeringEconomicsRepository must be supplied."
        )

    @abstractmethod
    def write_value_assessment(
        self,
        assessment: ValueAssessment,
    ) -> None:
        raise NotImplementedError(
            "A production EngineeringEconomicsRepository must be supplied."
        )
