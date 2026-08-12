"""
Deterministic sandbox policy enforcement.

No LLM participates in these decisions.

This is deliberate.

An AI agent should not decide whether it deserves additional execution
privileges.
"""

from __future__ import annotations

from .errors import SandboxPolicyError
from .models import (
    ExecutionRequest,
    NetworkMode,
    SandboxProfile,
)


FORBIDDEN_ENVIRONMENT_KEY_FRAGMENTS = (
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "PRIVATE_KEY",
    "CONNECTION_STRING",
)


class SandboxPolicyEngine:
    """Validate an execution request against an approved profile."""

    def validate(
        self,
        *,
        request: ExecutionRequest,
        profile: SandboxProfile,
    ) -> None:
        if request.role != profile.role:
            raise SandboxPolicyError(
                "Execution role does not match sandbox profile."
            )

        if request.profile_id != profile.profile_id:
            raise SandboxPolicyError(
                "Requested profile identifier does not match "
                "the resolved sandbox profile."
            )

        if (
            request.command.executable
            not in profile.allowed_executables
        ):
            raise SandboxPolicyError(
                "Executable is not permitted by sandbox profile: "
                f"{request.command.executable!r}"
            )

        if not request.command.working_directory.startswith(
            "/workspace"
        ):
            raise SandboxPolicyError(
                "Commands must execute inside /workspace."
            )

        self._validate_environment(
            request=request,
            profile=profile,
        )

        self._validate_network(profile)

    @staticmethod
    def _validate_environment(
        *,
        request: ExecutionRequest,
        profile: SandboxProfile,
    ) -> None:
        """
        The POC intentionally refuses secret-like environment variables.

        Production secrets should be injected through a dedicated
        identity/secret broker with short-lived, scoped credentials.

        They should not arrive from arbitrary task payloads.
        """

        if profile.allow_production_credentials:
            raise SandboxPolicyError(
                "Production credentials are prohibited by Component 10 "
                "POC policy."
            )

        for key in request.command.environment:
            normalized = key.upper()

            if any(
                fragment in normalized
                for fragment
                in FORBIDDEN_ENVIRONMENT_KEY_FRAGMENTS
            ):
                raise SandboxPolicyError(
                    "Potential credential material cannot be supplied "
                    f"through command environment variable {key!r}."
                )

    @staticmethod
    def _validate_network(
        profile: SandboxProfile,
    ) -> None:
        if (
            profile.network.mode == NetworkMode.DENY_ALL
            and profile.network.allowed_hosts
        ):
            raise SandboxPolicyError(
                "DENY_ALL network policy cannot contain allowed hosts."
            )

        if (
            profile.network.mode == NetworkMode.ALLOW_LIST
            and not profile.network.allowed_hosts
        ):
            raise SandboxPolicyError(
                "ALLOW_LIST network policy requires at least one host."
            )
