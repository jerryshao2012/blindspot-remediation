"""
Strict contracts for process and business measurement.

The core hierarchy is:

    ProcessEvent
        ↓
    ProcessWindow
        ↓
    KPIObservation
        ↓
    AttributionAssessment

The hierarchy deliberately does NOT mean that one layer automatically causes
the next.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from .errors import OutcomeValidationError


class OutcomeModel(BaseModel):
    """Base model shared by all Component 7 contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class ProcessEventType(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"
    MANUAL_INTERVENTION = "manual_intervention"
    REWORK_REQUIRED = "rework_required"


class ProcessEvent(OutcomeModel):
    """
    One meaningful process-level occurrence.

    Example:

        A mortgage-processing workflow completed.

    This is intentionally different from:

        HTTP request returned 200.

    The latter belongs to technical observability.

    IMPORTANT:

    Do not place customer names, account numbers, application contents,
    authentication information, or other sensitive payloads in this object.
    """

    event_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    process_instance_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    process_name: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    event_type: ProcessEventType

    timestamp: datetime

    deployment_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    release_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    originating_run_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    trace_id: str | None = None

    duration_ms: Annotated[
        float | None,
        Field(ge=0.0),
    ] = None

    numeric_attributes: dict[str, float] = Field(
        default_factory=dict
    )


class ProcessWindow(OutcomeModel):
    """
    Aggregated process behaviour for a deployment and time window.

    This is the process equivalent of Component 6's OperationalWindow.
    """

    deployment_id: str
    process_name: str

    window_start: datetime
    window_end: datetime

    process_instances: Annotated[
        int,
        Field(ge=0),
    ]

    completed_instances: Annotated[
        int,
        Field(ge=0),
    ]

    failed_instances: Annotated[
        int,
        Field(ge=0),
    ]

    abandoned_instances: Annotated[
        int,
        Field(ge=0),
    ]

    manual_intervention_instances: Annotated[
        int,
        Field(ge=0),
    ]

    rework_instances: Annotated[
        int,
        Field(ge=0),
    ]

    completion_rate: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    failure_rate: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    abandonment_rate: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    manual_intervention_rate: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    rework_rate: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    mean_completion_duration_ms: float | None
    p50_completion_duration_ms: float | None
    p95_completion_duration_ms: float | None


class KPIType(StrEnum):
    RATE = "rate"
    COUNT = "count"
    DURATION = "duration"
    CURRENCY = "currency"
    CONTINUOUS = "continuous"


class KPIObservation(OutcomeModel):
    """
    One explicitly defined business/process KPI measurement.

    Examples:

        straight-through processing rate
        average processing duration
        manual-touch rate
        abandonment rate

    The object records a measurement.

    It does NOT assert that a deployment caused the measurement.
    """

    observation_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    metric_name: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    metric_version: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    metric_type: KPIType

    value: float

    unit: Annotated[
        str,
        Field(min_length=1, max_length=64),
    ]

    window_start: datetime
    window_end: datetime

    sample_size: Annotated[
        int,
        Field(ge=0),
    ]

    deployment_id: str | None = None

    process_name: str | None = None

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.window_end <= self.window_start:
            raise ValueError(
                "KPI window_end must be after window_start."
            )

        return self


class AttributionDesign(StrEnum):
    """
    Increasing levels of evidential strength.

    ASSOCIATION:
        We merely observed the KPI during/after a deployment.

    BEFORE_AFTER:
        We compare a post-deployment period with a historical baseline.

    CONCURRENT_CONTROL:
        We have a contemporaneous comparison population.

    RANDOMIZED:
        Assignment was randomized.

    These labels intentionally describe design strength rather than making a
    binary causal/not-causal declaration.
    """

    ASSOCIATION = "association"
    BEFORE_AFTER = "before_after"
    CONCURRENT_CONTROL = "concurrent_control"
    RANDOMIZED = "randomized"


class AttributionStrength(StrEnum):
    DESCRIPTIVE_ONLY = "descriptive_only"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class AttributionAssessment(OutcomeModel):
    deployment_id: str

    metric_name: str

    design: AttributionDesign

    strength: AttributionStrength

    baseline_value: float | None

    treatment_value: float

    absolute_difference: float | None

    relative_difference: float | None

    baseline_sample_size: Annotated[
        int | None,
        Field(ge=0),
    ]

    treatment_sample_size: Annotated[
        int,
        Field(ge=0),
    ]

    confidence_level: Annotated[
        float,
        Field(gt=0.0, lt=1.0),
    ]

    notes: tuple[str, ...]


class MeasurementPolicy(OutcomeModel):
    """
    Minimum evidence requirements.

    These values govern whether we have enough observations to describe a KPI.
    They do NOT magically turn observational data into causal evidence.
    """

    policy_version: str

    minimum_process_instances: Annotated[
        int,
        Field(ge=1),
    ]

    minimum_kpi_sample_size: Annotated[
        int,
        Field(ge=1),
    ]

    confidence_level: Annotated[
        float,
        Field(gt=0.0, lt=1.0),
    ] = 0.95


class MeasurementSettings(OutcomeModel):
    policy: MeasurementPolicy

    @classmethod
    def from_yaml(cls, path: str) -> "MeasurementSettings":
        from pathlib import Path

        try:
            raw = yaml.safe_load(
                Path(path).read_text(encoding="utf-8")
            )
        except Exception as exc:
            raise OutcomeValidationError(
                f"Unable to read measurement policy: {exc}"
            ) from exc

        try:
            return cls.model_validate(raw)
        except Exception as exc:
            raise OutcomeValidationError(
                f"Measurement policy is invalid: {exc}"
            ) from exc
