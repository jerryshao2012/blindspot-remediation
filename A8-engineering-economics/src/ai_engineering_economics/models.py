"""
Strict data contracts for engineering productivity and economics.

The fundamental measurement unit is WorkItemEconomicsRecord.

It represents one engineering task from intake through its observed final
state and connects:

    work item
    engineering run
    gate decision
    deployment
    human effort
    AI resource consumption
    allocated cost
    incidents and rework
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .errors import EconomicsValidationError


class EconomicsModel(BaseModel):
    """Strict immutable base contract."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class WorkItemStatus(StrEnum):
    INTAKE = "intake"
    IN_PROGRESS = "in_progress"
    CANDIDATE_PRODUCED = "candidate_produced"
    GATE_FAILED = "gate_failed"
    HUMAN_REVIEW = "human_review"
    READY_FOR_RELEASE = "ready_for_release"
    DEPLOYED = "deployed"
    ABANDONED = "abandoned"
    CANCELLED = "cancelled"
    PIPELINE_ERROR = "pipeline_error"


class GateDisposition(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    MORE_EVIDENCE_REQUIRED = "more_evidence_required"
    NOT_REACHED = "not_reached"


class DeliveryOutcome(StrEnum):
    """
    Final delivery outcome used for unit economics.

    SAFELY_DELIVERED:
        The change reached production and no attributable failed-change event
        was recorded within the configured observation period.

    FAILED_CHANGE:
        The deployment required rollback, hotfix, remediation, or produced
        another policy-defined failed-change outcome.

    NOT_DEPLOYED:
        The work item did not reach production.

    UNKNOWN:
        The observation period or evidence was insufficient.
    """

    SAFELY_DELIVERED = "safely_delivered"
    FAILED_CHANGE = "failed_change"
    NOT_DEPLOYED = "not_deployed"
    UNKNOWN = "unknown"


class WorkEventType(StrEnum):
    CREATED = "created"
    AUTOMATION_STARTED = "automation_started"
    CANDIDATE_PRODUCED = "candidate_produced"
    GATE_STARTED = "gate_started"
    GATE_COMPLETED = "gate_completed"
    HUMAN_REVIEW_STARTED = "human_review_started"
    HUMAN_REVIEW_COMPLETED = "human_review_completed"
    DEPLOYMENT_STARTED = "deployment_started"
    DEPLOYED = "deployed"
    INCIDENT_STARTED = "incident_started"
    INCIDENT_RESOLVED = "incident_resolved"
    REWORK_STARTED = "rework_started"
    REWORK_COMPLETED = "rework_completed"
    CANCELLED = "cancelled"


class WorkItemEvent(EconomicsModel):
    """One timestamped event in the engineering value stream."""

    event_id: Annotated[str, Field(min_length=1, max_length=256)]
    work_item_id: Annotated[str, Field(min_length=1, max_length=256)]
    event_type: WorkEventType
    timestamp: datetime

    run_id: str | None = None
    deployment_id: str | None = None

    metadata: dict[str, str] = Field(default_factory=dict)


class HumanActivityType(StrEnum):
    TASK_REFINEMENT = "task_refinement"
    OPERATOR_SUPERVISION = "operator_supervision"
    CODE_REVIEW = "code_review"
    RELEASE_REVIEW = "release_review"
    MANUAL_IMPLEMENTATION = "manual_implementation"
    REWORK = "rework"
    INCIDENT_RESPONSE = "incident_response"
    BENCHMARK_OR_EVAL_WORK = "benchmark_or_eval_work"
    OTHER = "other"


class HumanEffortRecord(EconomicsModel):
    """
    Human effort attributable to one work item.

    Duration is recorded directly rather than inferred from elapsed calendar
    time. A reviewer leaving a task open overnight must not be recorded as
    working continuously overnight.
    """

    effort_id: Annotated[str, Field(min_length=1, max_length=256)]
    work_item_id: Annotated[str, Field(min_length=1, max_length=256)]
    activity_type: HumanActivityType

    started_at: datetime
    completed_at: datetime

    duration_minutes: Annotated[float, Field(ge=0.0)]

    role_category: Annotated[str, Field(min_length=1, max_length=128)]

    fully_loaded_hourly_cost: Annotated[float, Field(ge=0.0)]

    automated_capture: bool = False

    @model_validator(mode="after")
    def validate_effort(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError(
                "Human effort completion precedes its start."
            )

        elapsed_minutes = (
            self.completed_at - self.started_at
        ).total_seconds() / 60.0

        if self.duration_minutes > elapsed_minutes + 1e-9:
            raise ValueError(
                "Recorded active human duration exceeds elapsed time."
            )

        return self


class AIUsageRecord(EconomicsModel):
    """LLM or AI-service usage attributable to one work item."""

    usage_id: Annotated[str, Field(min_length=1, max_length=256)]
    work_item_id: Annotated[str, Field(min_length=1, max_length=256)]
    run_id: str | None = None

    component_name: Annotated[str, Field(min_length=1, max_length=256)]
    provider: Annotated[str, Field(min_length=1, max_length=128)]
    model_name: Annotated[str, Field(min_length=1, max_length=256)]

    input_tokens: Annotated[int, Field(ge=0)]
    output_tokens: Annotated[int, Field(ge=0)]
    cached_input_tokens: Annotated[int, Field(ge=0)] = 0

    request_count: Annotated[int, Field(ge=0)]

    actual_cost: Annotated[float | None, Field(ge=0.0)] = None
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "CAD"

    timestamp: datetime


class CostCategory(StrEnum):
    AI_API = "ai_api"
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    SOFTWARE_LICENSE = "software_license"
    HUMAN_LABOUR = "human_labour"
    SHARED_PLATFORM = "shared_platform"
    INCIDENT = "incident"
    OTHER = "other"


class CostAllocationMethod(StrEnum):
    DIRECT = "direct"
    TAG = "tag"
    TOKEN_SHARE = "token_share"
    COMPUTE_TIME_SHARE = "compute_time_share"
    RUN_SHARE = "run_share"
    EQUAL_SHARE = "equal_share"
    MANUAL = "manual"


class CostRecord(EconomicsModel):
    """
    One actual or allocated cost observation.

    Source-system identifiers should be retained in metadata. Sensitive billing
    information or credentials should not be stored here.
    """

    cost_id: Annotated[str, Field(min_length=1, max_length=256)]

    category: CostCategory

    amount: Annotated[float, Field(ge=0.0)]

    currency: Annotated[str, Field(min_length=3, max_length=3)] = "CAD"

    incurred_at: datetime

    work_item_id: str | None = None
    run_id: str | None = None
    component_name: str | None = None

    allocation_method: CostAllocationMethod = CostAllocationMethod.DIRECT

    source: Annotated[str, Field(min_length=1, max_length=256)]

    metadata: dict[str, str] = Field(default_factory=dict)


class WorkItemEconomicsRecord(EconomicsModel):
    """Complete normalized record for one engineering work item."""

    work_item_id: Annotated[str, Field(min_length=1, max_length=256)]
    task_type: Annotated[str, Field(min_length=1, max_length=128)]
    team: Annotated[str, Field(min_length=1, max_length=256)]

    status: WorkItemStatus
    gate_disposition: GateDisposition
    delivery_outcome: DeliveryOutcome

    created_at: datetime
    automation_started_at: datetime | None = None
    candidate_produced_at: datetime | None = None
    gate_completed_at: datetime | None = None
    deployed_at: datetime | None = None
    incident_resolved_at: datetime | None = None

    run_id: str | None = None
    deployment_id: str | None = None

    human_touch_count: Annotated[int, Field(ge=0)] = 0
    human_effort_minutes: Annotated[float, Field(ge=0.0)] = 0.0

    ai_input_tokens: Annotated[int, Field(ge=0)] = 0
    ai_output_tokens: Annotated[int, Field(ge=0)] = 0
    ai_request_count: Annotated[int, Field(ge=0)] = 0

    ai_cost: Annotated[float, Field(ge=0.0)] = 0.0
    cloud_cost: Annotated[float, Field(ge=0.0)] = 0.0
    human_cost: Annotated[float, Field(ge=0.0)] = 0.0
    incident_cost: Annotated[float, Field(ge=0.0)] = 0.0
    total_cost: Annotated[float, Field(ge=0.0)] = 0.0

    rework_required: bool = False
    human_review_required: bool = False

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        timestamps = [
            item
            for item in (
                self.automation_started_at,
                self.candidate_produced_at,
                self.gate_completed_at,
                self.deployed_at,
                self.incident_resolved_at,
            )
            if item is not None
        ]

        if any(timestamp < self.created_at for timestamp in timestamps):
            raise ValueError(
                "A work-item milestone predates work-item creation."
            )

        calculated_total = (
            self.ai_cost
            + self.cloud_cost
            + self.human_cost
            + self.incident_cost
        )

        if abs(calculated_total - self.total_cost) > 1e-6:
            raise ValueError(
                "total_cost does not equal the sum of cost categories."
            )

        return self


class ProportionMetric(EconomicsModel):
    numerator: Annotated[int, Field(ge=0)]
    denominator: Annotated[int, Field(ge=0)]
    estimate: Annotated[float | None, Field(ge=0.0, le=1.0)]
    confidence_level: Annotated[float, Field(gt=0.0, lt=1.0)]
    lower_bound: Annotated[float | None, Field(ge=0.0, le=1.0)]
    upper_bound: Annotated[float | None, Field(ge=0.0, le=1.0)]


class DurationDistribution(EconomicsModel):
    count: Annotated[int, Field(ge=0)]
    mean_hours: float | None
    p50_hours: float | None
    p85_hours: float | None
    p95_hours: float | None


class EngineeringEconomicsReport(EconomicsModel):
    """Aggregate engineering-flow and unit-economics report."""

    report_id: str
    window_start: datetime
    window_end: datetime
    currency: str

    work_items: Annotated[int, Field(ge=0)]
    deployed_changes: Annotated[int, Field(ge=0)]
    safely_delivered_changes: Annotated[int, Field(ge=0)]
    failed_changes: Annotated[int, Field(ge=0)]

    autonomous_changes: Annotated[int, Field(ge=0)]
    human_review_changes: Annotated[int, Field(ge=0)]
    reworked_changes: Annotated[int, Field(ge=0)]
    pipeline_error_items: Annotated[int, Field(ge=0)]

    automation_completion_rate: ProportionMetric
    autonomous_delivery_rate: ProportionMetric
    human_review_rate: ProportionMetric
    rework_rate: ProportionMetric
    change_failure_rate: ProportionMetric

    intake_to_deployment: DurationDistribution
    automation_cycle_time: DurationDistribution
    gate_cycle_time: DurationDistribution
    failed_deployment_recovery_time: DurationDistribution

    deployment_frequency_per_day: float | None

    total_human_hours: Annotated[float, Field(ge=0.0)]
    mean_human_minutes_per_item: float | None
    mean_human_minutes_per_safe_change: float | None

    total_input_tokens: Annotated[int, Field(ge=0)]
    total_output_tokens: Annotated[int, Field(ge=0)]
    total_ai_requests: Annotated[int, Field(ge=0)]

    total_ai_cost: Annotated[float, Field(ge=0.0)]
    total_cloud_cost: Annotated[float, Field(ge=0.0)]
    total_human_cost: Annotated[float, Field(ge=0.0)]
    total_incident_cost: Annotated[float, Field(ge=0.0)]
    total_cost: Annotated[float, Field(ge=0.0)]

    cost_per_attempted_item: float | None
    cost_per_deployed_change: float | None
    cost_per_safely_delivered_change: float | None

    tokens_per_safely_delivered_change: float | None


class BaselineMetrics(EconomicsModel):
    """
    Relevant human-led or prior-process baseline.

    The baseline must be comparable in task scope and measurement definition.
    Component 8 records supplied baseline evidence but cannot guarantee that
    task populations are comparable.
    """

    baseline_id: str
    metric_version: str
    task_type: str | None = None

    sample_size: Annotated[int, Field(ge=1)]

    cost_per_safely_delivered_change: Annotated[float, Field(ge=0.0)]
    mean_lead_time_hours: Annotated[float, Field(ge=0.0)]
    mean_human_minutes_per_safe_change: Annotated[float, Field(ge=0.0)]
    change_failure_rate: Annotated[float, Field(ge=0.0, le=1.0)]


class ValueStatus(StrEnum):
    VALUE_DEMONSTRATED = "value_demonstrated"
    VALUE_NOT_DEMONSTRATED = "value_not_demonstrated"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ValueAssessment(EconomicsModel):
    status: ValueStatus
    policy_version: str

    cost_difference_per_safe_change: float | None
    cost_reduction_fraction: float | None

    lead_time_difference_hours: float | None
    lead_time_reduction_fraction: float | None

    human_effort_difference_minutes: float | None
    human_effort_reduction_fraction: float | None

    reasons: tuple[str, ...]


class EconomicsPolicy(EconomicsModel):
    """
    Example deterministic value policy.

    Thresholds are POC values, not enterprise production requirements.
    """

    policy_version: str

    minimum_work_items: Annotated[int, Field(ge=1)]
    minimum_safely_delivered_changes: Annotated[int, Field(ge=1)]

    minimum_cost_reduction_fraction: Annotated[
        float,
        Field(ge=-1.0, le=1.0),
    ]

    minimum_human_effort_reduction_fraction: Annotated[
        float,
        Field(ge=-1.0, le=1.0),
    ]

    maximum_change_failure_rate: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    maximum_human_review_rate: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    confidence_level: Annotated[
        float,
        Field(gt=0.0, lt=1.0),
    ] = 0.95


class EconomicsSettings(EconomicsModel):
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "CAD"
    policy: EconomicsPolicy

    @classmethod
    def from_yaml(cls, path: Path) -> "EconomicsSettings":
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise EconomicsValidationError(
                f"Unable to read economics policy: {exc}"
            ) from exc

        try:
            return cls.model_validate(raw)
        except Exception as exc:
            raise EconomicsValidationError(
                f"Economics policy is invalid: {exc}"
            ) from exc
