"""Strict YAML loader for task specifications."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .errors import SpecificationValidationError
from .models import TaskSpecification


def load_task_specification(
    path: Path,
) -> TaskSpecification:
    """
    Parse YAML into the strict TaskSpecification schema.

    YAML is only the serialization format.

    The Pydantic model remains the domain contract.
    """

    try:
        raw = yaml.safe_load(
            path.read_text(encoding="utf-8")
        )
    except (OSError, yaml.YAMLError) as exc:
        raise SpecificationValidationError(
            f"Unable to load task specification {path}: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise SpecificationValidationError(
            "Task specification root must be a YAML mapping."
        )

    try:
        return TaskSpecification.model_validate(raw)
    except ValidationError as exc:
        raise SpecificationValidationError(
            f"Invalid task specification {path}: {exc}"
        ) from exc
