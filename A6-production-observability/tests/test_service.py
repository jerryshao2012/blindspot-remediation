from datetime import datetime, timedelta, timezone

from ai_engineering_observability.aggregation import (
    OperationalMetricsCalculator,
)
from ai_engineering_observability.correlation import (
    DeploymentCorrelationService,
)
from ai_engineering_observability.models import (
    DeploymentIdentity,
    ExecutionOutcome,
    OperationalPolicy,
    RuntimeObservation,
)
from ai_engineering_observability.policy import (
    SLOEvaluator,
)
from ai_engineering_observability.service import (
    OperationalMetricsService,
)
from ai_engineering_observability.storage import (
    OperationalEvidenceRepository,
)


class InMemoryRepository(OperationalEvidenceRepository):
    def __init__(self) -> None:
        self.deployments = {}
        self.observations = []
        self.windows = []
        self.decisions = []

    def register_deployment(self, deployment):
        self.deployments[deployment.deployment_id] = deployment

    def write_observation(self, observation):
        self.observations.append(observation)

    def write_window(self, window):
        self.windows.append(window)

    def write_health_decision(self, decision):
        self.decisions.append(decision)

    def observations_for_deployment(self, deployment_id):
        return tuple(
            observation
            for observation in self.observations
            if observation.deployment_id == deployment_id
        )


class NoOpTelemetry:
    def emit(self, observation):
        return None


def test_complete_operational_flow() -> None:
    now = datetime.now(timezone.utc)

    repository = InMemoryRepository()

    service = OperationalMetricsService(
        repository=repository,
        correlation=DeploymentCorrelationService(),
        calculator=OperationalMetricsCalculator(),
        evaluator=SLOEvaluator(),
        telemetry=NoOpTelemetry(),
    )

    deployment = DeploymentIdentity(
        deployment_id="deployment-1",
        release_id="release-1",
        service_name="mortgage-service",
        environment="production",
        source_commit="a" * 40,
        originating_run_id="run-123",
        deployed_at=now,
        pipeline_version="1.0",
        gate_version="1.0",
    )

    service.register_deployment(deployment)

    for index in range(200):
        service.record_observation(
            deployment=deployment,
            observation=RuntimeObservation(
                observation_id=f"obs-{index}",
                timestamp=now + timedelta(seconds=index + 1),
                deployment_id="deployment-1",
                service_name="mortgage-service",
                operation_name="process",
                outcome=ExecutionOutcome.SUCCESS,
                duration_ms=100,
            ),
        )

    policy = OperationalPolicy(
        policy_version="test",
        minimum_observations=100,
        minimum_availability=0.99,
        maximum_error_rate=0.01,
        critical_error_rate=0.05,
        maximum_timeout_rate=0.01,
        maximum_dependency_failure_rate=0.02,
        maximum_p95_latency_ms=1500,
        critical_p95_latency_ms=5000,
    )

    window, decision = service.evaluate_window(
        deployment=deployment,
        window_start=now,
        window_end=now + timedelta(minutes=10),
        policy=policy,
    )

    assert window.observation_count == 200
    assert decision.status.value == "healthy"
