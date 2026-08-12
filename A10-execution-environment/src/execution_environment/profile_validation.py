"""Deployment-time validation for sandbox profiles."""

from __future__ import annotations

from .errors import SandboxPolicyError
from .models import SandboxProfile


UNCONFIGURED_IMAGE_DIGEST = (
    "sha256:"
    + ("0" * 64)
)


def validate_deployable_profile(
    profile: SandboxProfile,
) -> None:
    """
    Prevent a demonstration configuration from silently becoming production
    configuration.
    """

    if (
        profile.runner_image_digest
        == UNCONFIGURED_IMAGE_DIGEST
    ):
        raise SandboxPolicyError(
            "Sandbox runner image digest has not been configured. "
            "Deploy an approved runner image and pin its SHA-256 digest."
        )

    if profile.allow_production_credentials:
        raise SandboxPolicyError(
            "Component 10 POC profiles may not expose production credentials."
        )

    if profile.preserve_workspace_after_execution:
        raise SandboxPolicyError(
            "POC sandbox workspaces must be ephemeral."
        )
