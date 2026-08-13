from pathlib import Path

from ai_engineering_orchestrator.registry import (
    TaskDefinitionRegistry,
)


def test_registry_loads_task_definition(
    tmp_path: Path,
) -> None:
    definition = tmp_path / "x1.yaml"

    definition.write_text(
        """
task_type: X1
definition_version: 1.0.0
enabled: true
skill_reference: skills/x1/1.0.0
change_execution_profile: x1-execution
release_gate_profile: x1-gate

required_evidence_types:
  - build_result

allowed_repository_patterns:
  - engineering-poc

budget:
  maximum_execution_attempts: 2
  maximum_gate_attempts: 3
  maximum_total_llm_input_tokens: 100000
  maximum_total_llm_output_tokens: 20000
  maximum_total_llm_requests: 100
  maximum_elapsed_seconds: 3600

maximum_more_evidence_cycles: 2
automatic_release_allowed: false
""",
        encoding="utf-8",
    )

    registry = TaskDefinitionRegistry(
        tmp_path
    )

    loaded = registry.resolve("X1")

    assert loaded.task_type == "X1"
    assert loaded.definition_version == "1.0.0"
