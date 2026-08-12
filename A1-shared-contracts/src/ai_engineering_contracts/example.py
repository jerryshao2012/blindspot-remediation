"""
Create, validate, serialize, and fingerprint a realistic TaskRunRequest.

This example performs no Azure calls and incurs no LLM cost. It is intended as
the first smoke test for junior developers and data scientists.
"""

from __future__ import annotations

from .enums import EvidenceStrategy
from .models import ExecutionBudget, TaskRunRequest

EXAMPLE_BASE_COMMIT = "a" * 40


def build_example_request() -> TaskRunRequest:
    """Build a fully valid example request without hidden placeholders."""
    return TaskRunRequest(
        run_id="demo-X1-0001",
        task_type="X1-dependency-update",
        task_package_version="1.0.0",
        repository_url="https://dev.azure.com/example-organization/example-project/_git/example-repository",
        base_commit=EXAMPLE_BASE_COMMIT,
        target_branch="main",
        task_description=(
            "Update the approved JSON serialization dependency from the current "
            "patch version to the next approved patch version and make only the "
            "compatibility changes required for the repository to build and pass "
            "its existing tests."
        ),
        acceptance_criteria=[
            "The repository builds successfully in the pinned toolchain.",
            "All pre-existing unit and integration tests pass.",
            "No files outside dependency manifests, lock files, source files directly "
            "affected by the upgrade, and corresponding tests are changed.",
            "No new high- or critical-severity dependency vulnerability is introduced.",
        ],
        permitted_paths=[
            "pyproject.toml",
            "requirements*.txt",
            "src/**/*.py",
            "tests/**/*.py",
        ],
        prohibited_paths=[
            ".azure-pipelines/**",
            "infrastructure/**",
            "secrets/**",
        ],
        execution_budget=ExecutionBudget(
            maximum_llm_calls=8,
            maximum_input_tokens=150_000,
            maximum_output_tokens=30_000,
            maximum_tool_calls=100,
            maximum_repair_iterations=3,
            maximum_runtime_seconds=1_800,
            maximum_estimated_cost=25.00,
            currency="USD",
        ),
        requested_by="poc-operator",
        correlation_id="demo-correlation-0001",
        metadata={
            "risk_tier": "low",
            "environment": "local-demo",
            "evidence_strategy_preview": EvidenceStrategy.EXISTING_TESTS.value,
        },
    )


def main() -> int:
    request = build_example_request()
    print("Validated TaskRunRequest")
    print("========================")
    print(request.to_pretty_json())
    print()
    print(f"Content fingerprint: {request.content_fingerprint()}")
    round_trip = TaskRunRequest.model_validate_json(request.model_dump_json())
    if round_trip != request:
        raise RuntimeError("JSON round-trip validation changed the request.")
    print("JSON round-trip validation: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
