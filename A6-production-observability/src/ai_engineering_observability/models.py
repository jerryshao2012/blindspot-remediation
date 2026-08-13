"""
Strict operational data contracts.

The central idea is:

    deployment identity
        +
    runtime observation
        +
    observation window
        +
    deterministic SLO policy

produces an operational-health statement.

Operational observations are immutable facts.

Health classifications are derived conclusions.
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
    field_validator,
    model_validator,
)

from .errors import OperationalPolicyError


class OperationalModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class DeploymentIdentity(OperationalModel):
    """
    Correlation anchor between Components 1–5 and production.

    ``originating_run_id`` connects production behaviour back to the immutable
    engineering evidence created before release.
    """

    deployment_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    release_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    service_name: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    environment: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    source_commit: Annotated[
        str,
        Field(pattern=r"^[0-9a-fA-F]{40}$"),
    ]

    originating_run_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    deployed_at: datetime

    pipeline_version: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    gate_version: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    @field_validator("source_commit")
    @classmethod
    def normalize_commit(cls, value: str) -> str:
        return value.lower()


class ExecutionOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ProcessOutcome(StrEnum):
    """
    Technical/process outcome produced by the software.

    This is deliberately not called BusinessOutcome.

    Example:

        mortgage workflow successfully submitted

    is an observable process outcome.

        mortgage revenue increased

    is a business KPI and belongs elsewhere.
    """

    COMPLETED = "completed"
    REJECTED = "rejected"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"


class RuntimeObservation(OperationalModel):
    """
    One structured observation from production execution.

    High-cardinality data such as full request bodies, customer information,
    source code, or prompts should NOT be inserted into these fields.
    """

    observation_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    timestamp: datetime

    deployment_id: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    service_name: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    operation_name: Annotated[
        str,
        Field(min_length=1, max_length=256),
    ]

    trace_id: str | None = None

    outcome: ExecutionOutcome

    process_outcome: ProcessOutcome = ProcessOutcome.UNKNOWN

    duration_ms: Annotated[
        float,
        Field(ge=0.0),
    ]

    dependency_calls: Annotated[
        int,
        Field(ge=0),
    ] = 0

    dependency_failures: Annotated[
        int,
        Field(ge=0),
    ] = 0

    retry_count: Annotated[
        int,
        Field(ge=0),
    ] = 0

    cpu_seconds: Annotated[
        float,
        Field(ge=0.0),
    ] = 0.0

    memory_peak_mb: Annotated[
        float,
        Field(ge=0.0),
    ] = 0.0

    custom_numeric: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dependency_counts(self) -> Self:
        if self.dependency_failures > self.dependency_calls:
            raise ValueError(
                "dependency_failures cannot exceed dependency_calls."
            )

        return self


class OperationalWindow(OperationalModel):
    deployment_id: str
    service_name: str

    window_start: datetime
    window_end: datetime

    observation_count: Annotated[int, Field(ge=0)]

    successful_executions: Annotated[int, Field(ge=0)]
    failed_executions: Annotated[int, Field(ge=0)]
    timeout_executions: Annotated[int, Field(ge=0)]
    cancelled_executions: Annotated[int, Field(ge=0)]

    completed_processes: Annotated[int, Field(ge=0)]

    availability: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    error_rate: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    timeout_rate: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    dependency_failure_rate: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    process_completion_rate: Annotated[
        float | None,
        Field(ge=0.0, le=1.0),
    ]

    mean_latency_ms: float | None
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    p99_latency_ms: float | None

    mean_retry_count: float | None

    total_cpu_seconds: Annotated[float, Field(ge=0.0)]
    maximum_memory_peak_mb: Annotated[float, Field(ge=0.0)]


class OperationalHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    INSUFFICIENT_DATA = "insufficient_data"


class OperationalPolicy(OperationalModel):
    policy_version: Annotated[
        str,
        Field(min_length=1, max_length=128),
    ]

    minimum_observations: Annotated[
        int,
        Field(ge=1),
    ]

    minimum_availability: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    maximum_error_rate: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    critical_error_rate: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    maximum_timeout_rate: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    maximum_dependency_failure_rate: Annotated[
        float,
        Field(ge=0.0, le=1.0),
    ]

    maximum_p95_latency_ms: Annotated[
        float,
        Field(gt=0.0),
    ]

    critical_p95_latency_ms: Annotated[
        float,
        Field(gt=0.0),
    ]

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.critical_error_rate < self.maximum_error_rate:
            raise ValueError(
                "critical_error_rate must be >= maximum_error_rate."
            )

        if self.critical_p95_latency_ms < self.maximum_p95_latency_ms:
            raise ValueError(
                "critical_p95_latency_ms must be >= "
                "maximum_p95_latency_ms."
            )

        return self


class OperationalHealthDecision(OperationalModel):
    deployment_id: str

    status: OperationalHealth

    policy_version: str

    reasons: tuple[str, ...]

    evaluated_at: datetime


class OperationalSettings(OperationalModel):
    policy: OperationalPolicy

    @classmethod
    def from_yaml(cls, path: str) -> "OperationalSettings":
        from pathlib import Path

        try:
            raw = yaml.safe_load(
                Path(path).read_text(encoding="utf-8")
            )
        except Exception as exc:
            raise OperationalPolicyError(
                f"Unable to read operational policy: {exc}"
            ) from exc

        try:
            return cls.model_validate(raw)
        except Exception as exc:
            raise OperationalPolicyError(
                f"Operational policy is invalid: {exc}"
            ) from exc
