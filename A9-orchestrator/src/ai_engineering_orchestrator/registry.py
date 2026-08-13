"""
Task-definition registry.

For the POC, task definitions are stored as version-controlled YAML files.

A future enterprise implementation may replace this storage mechanism with an
approved configuration service.

The orchestration domain should not depend on that storage choice.
"""

from __future__ import annotations

from pathlib import Path

from .errors import (
    TaskDefinitionError,
    UnsupportedTaskTypeError,
)
from .models import TaskDefinition


class TaskDefinitionRegistry:
    """Load and resolve task definitions from a controlled directory."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def load_all(self) -> dict[str, TaskDefinition]:
        if not self._root.exists():
            raise TaskDefinitionError(
                f"Task-definition directory does not exist: {self._root}"
            )

        definitions: dict[str, TaskDefinition] = {}

        for path in sorted(self._root.glob("*.yaml")):
            definition = TaskDefinition.from_yaml(path)

            if definition.task_type in definitions:
                raise TaskDefinitionError(
                    "Duplicate task type: "
                    f"{definition.task_type!r}"
                )

            definitions[definition.task_type] = definition

        return definitions

    def resolve(
        self,
        task_type: str,
    ) -> TaskDefinition:
        definitions = self.load_all()

        definition = definitions.get(task_type)

        if definition is None:
            raise UnsupportedTaskTypeError(
                f"Unsupported task type: {task_type!r}"
            )

        if not definition.enabled:
            raise UnsupportedTaskTypeError(
                f"Task type {task_type!r} is disabled."
            )

        return definition
