"""
Component-specific models.

Cross-service contracts remain in ``ai_engineering_contracts``. Models in this
module are internal inputs and configuration for the deterministic executor.

The most important input is ``ManualPatchExecutionRequest``. It combines the
cross-service TaskRunRequest with a manually authored patch artifact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Self

import yaml
from ai_engineering_contracts import (
    ArtifactKind,
    ArtifactReference,
    TaskRunRequest,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .errors import ConfigurationError


class ExecutorModel(BaseModel):
    """Strict and immutable base model for component-local configuration."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class LocalCheckSpec(ExecutorModel):
    """
    One fast local feedback check executed by ChangeExecutionService.

    A command is represented as a list of arguments and is always executed with
    ``shell=False``. Shell syntax such as pipes, redirection, variable expansion,
    ``&&``, and ``;`` is intentionally unavailable.

    These checks are not authoritative release evidence. They help the executor
    identify obviously broken candidates before handing them to the release gate.
    """

    check_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        ),
    ]
    name: Annotated[str, Field(min_length=1, max_length=512)]
    command: list[Annotated[str, Field(min_length=1, max_length=4_096)]] = Field(
        min_length=1,
        max_length=100,
    )
    timeout_seconds: Annotated[int, Field(gt=0, le=86_400)] = 600
    required: bool = True
    working_directory: Annotated[str, Field(min_length=1, max_length=1_024)] = "."
    environment: dict[
        Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")],
        Annotated[str, Field(max_length=4_096)],
    ] = Field(default_factory=dict)

    @field_validator("command")
    @classmethod
    def reject_shell_control_tokens(cls, value: list[str]) -> list[str]:
        """
        Reject arguments that strongly indicate accidental shell-command input.

        This does not attempt to classify every possible command as safe. The
        task package or operator remains responsible for approving executable
        names. The important guarantee is that this service never invokes a shell.
        """
        prohibited_standalone_tokens = {
            "|",
            "||",
            "&&",
            ";",
            ">",
            ">>",
            "<",
            "<<",
        }
        for argument in value:
            if argument in prohibited_standalone_tokens:
                raise ValueError(
                    f"Shell control token {argument!r} is not allowed. "
                    "Provide an executable and argument list instead."
                )
            if "\x00" in argument:
                raise ValueError("Command arguments must not contain NUL bytes.")
        return value

    @field_validator("working_directory")
    @classmethod
    def validate_working_directory(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        path = Path(normalized)
        if path.is_absolute():
            raise ValueError("working_directory must be repository-relative.")
        if ".." in path.parts:
            raise ValueError(
                "working_directory must not contain parent-directory traversal."
            )
        return normalized


class GitIdentity(ExecutorModel):
    """Identity used for the local candidate commit."""

    name: Annotated[str, Field(min_length=1, max_length=200)]
    email: Annotated[
        str,
        Field(
            min_length=3,
            max_length=320,
            pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        ),
    ]


class ExecutorSettings(ExecutorModel):
    """
    Runtime settings for the deterministic executor.

    ``artifact_root`` is intentionally local in this component. A future Azure
    Blob implementation will satisfy the same artifact-store interface.
    """

    artifact_root: Path
    git_executable: Annotated[str, Field(min_length=1, max_length=1_024)] = "git"
    git_identity: GitIdentity = GitIdentity(
        name="AI Engineering POC Executor",
        email="ai-engineering-poc@example.invalid",
    )
    local_checks: list[LocalCheckSpec] = Field(
        default_factory=list,
        max_length=1_000,
    )
    maximum_captured_output_bytes: Annotated[
        int,
        Field(ge=1_024, le=50_000_000),
    ] = 1_000_000
    keep_failed_workspace: bool = False

    @field_validator("artifact_root")
    @classmethod
    def normalize_artifact_root(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @field_validator("local_checks")
    @classmethod
    def reject_duplicate_check_ids(
        cls,
        value: list[LocalCheckSpec],
    ) -> list[LocalCheckSpec]:
        identifiers = [item.check_id for item in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("local_checks must not contain duplicate check_id values.")
        return value

    @classmethod
    def from_yaml(cls, path: Path) -> "ExecutorSettings":
        """Load and validate settings from a UTF-8 YAML file."""
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigurationError(
                f"Unable to read executor configuration {path}: {exc}"
            ) from exc
        except yaml.YAMLError as exc:
            raise ConfigurationError(
                f"Executor configuration {path} is not valid YAML: {exc}"
            ) from exc
        if raw is None:
            raise ConfigurationError(
                f"Executor configuration {path} is empty."
            )
        if not isinstance(raw, dict):
            raise ConfigurationError(
                f"Executor configuration {path} must contain a YAML mapping."
            )
        try:
            return cls.model_validate(raw)
        except Exception as exc:
            raise ConfigurationError(
                f"Executor configuration {path} failed validation: {exc}"
            ) from exc


class ManualPatchExecutionRequest(ExecutorModel):
    """
    Complete input to the deterministic ChangeExecutionService.

    The patch artifact must contain a Git-compatible unified patch. For maximum
    fidelity, generate it with:

        git diff --binary --full-index

    ``commit_message`` is applied to the local candidate commit. No remote push,
    pull request, merge, or deployment occurs in this component.
    """

    task: TaskRunRequest
    patch_artifact: ArtifactReference
    commit_message: Annotated[str, Field(min_length=1, max_length=4_000)]
    additional_checks: list[LocalCheckSpec] = Field(
        default_factory=list,
        max_length=1_000,
    )

    @model_validator(mode="after")
    def validate_patch_request(self) -> Self:
        if self.patch_artifact.kind != ArtifactKind.PATCH:
            raise ValueError(
                "patch_artifact must have ArtifactKind.PATCH."
            )
        if not self.patch_artifact.immutable:
            raise ValueError(
                "The supplied patch must be represented as an immutable artifact."
            )
        if self.patch_artifact.sha256 is None:
            raise ValueError(
                "The supplied patch must include its SHA-256 digest."
            )
        configured_ids = [item.check_id for item in self.additional_checks]
        if len(configured_ids) != len(set(configured_ids)):
            raise ValueError(
                "additional_checks must not contain duplicate check identifiers."
            )
        return self
