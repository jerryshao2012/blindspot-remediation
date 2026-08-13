"""
Deployment correlation.

This service establishes the chain:

engineering run
    →
release
    →
deployment
    →
runtime observations

Without this chain we may know that production degraded, but we cannot reliably
associate the observation with the change that produced the deployed code.
"""

from __future__ import annotations

from .errors import CorrelationError
from .models import DeploymentIdentity, RuntimeObservation


class DeploymentCorrelationService:
    """Validate deployment/runtime correlation."""

    def validate_observation(
        self,
        *,
        deployment: DeploymentIdentity,
        observation: RuntimeObservation,
    ) -> None:
        if observation.deployment_id != deployment.deployment_id:
            raise CorrelationError(
                "Runtime observation deployment_id does not match "
                "DeploymentIdentity."
            )

        if observation.service_name != deployment.service_name:
            raise CorrelationError(
                "Runtime observation service_name does not match "
                "DeploymentIdentity."
            )

        if observation.timestamp < deployment.deployed_at:
            raise CorrelationError(
                "Runtime observation predates the deployment."
            )
