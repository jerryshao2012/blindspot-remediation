from datetime import datetime, timedelta, timezone

import pytest

from ai_engineering_observability.correlation import (
    DeploymentCorrelationService,
)
from ai_engineering_observability.errors import CorrelationError
from ai_engineering_observability.models import (
    DeploymentIdentity,
    ExecutionOutcome,
    RuntimeObservation,
)


NOW = datetime.now(timezone.utc)


def deployment() -> DeploymentIdentity:
    return DeploymentIdentity(
        deployment_id="deployment-1",
        release_id="release-1",
        service_name="mortgage-service",
        environment="production",
        source_commit="a" * 40,
        originating_run_id="run-123",
        deployed_at=NOW,
        pipeline_version="1.0",
        gate_version="1.0",
    )


def test_matching_observation_is_accepted() -> None:
    observation = RuntimeObservation(
        observation_id="obs-1",
        timestamp=NOW + timedelta(seconds=10),
        deployment_id="deployment-1",
        service_name="mortgage-service",
        operation_name="process",
        outcome=ExecutionOutcome.SUCCESS,
        duration_ms=100,
    )

    DeploymentCorrelationService().validate_observation(
        deployment=deployment(),
        observation=observation,
    )


def test_wrong_deployment_is_rejected() -> None:
    observation = RuntimeObservation(
        observation_id="obs-1",
        timestamp=NOW + timedelta(seconds=10),
        deployment_id="wrong-deployment",
        service_name="mortgage-service",
        operation_name="process",
        outcome=ExecutionOutcome.SUCCESS,
        duration_ms=100,
    )

    with pytest.raises(CorrelationError):
        DeploymentCorrelationService().validate_observation(
            deployment=deployment(),
            observation=observation,
        )
