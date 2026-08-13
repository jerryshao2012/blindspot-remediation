"""
Executable architectural-boundary tests.
These tests do not replace enterprise IAM verification.
They prevent obvious source-level boundary regressions.
"""
from pathlib import Path
from l1_automation.architecture.repository_check import (
    find_assurance_policy_environment_variables,
    find_azure_sdk_leakage,
    find_hidden_oracle_leakage,
)
PACKAGE_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
    / "src"
    / "l1_automation"
)
def _render(
    violations,
) -> str:
    return "\n".join(
        f"{item.path}:{item.line}: "
        f"[{item.rule}] "
        f"{item.details}"
        for item in violations
    )
def test_online_domain_does_not_import_azure_sdk_directly() -> None:
    violations = find_azure_sdk_leakage(
        PACKAGE_ROOT
    )
    assert violations == (), _render(
        violations
    )
def test_online_domain_does_not_import_hidden_oracle() -> None:
    violations = find_hidden_oracle_leakage(
        PACKAGE_ROOT
    )
    assert violations == (), _render(
        violations
    )
def test_assurance_policy_is_not_moved_into_environment_variables() -> None:
    violations = (
        find_assurance_policy_environment_variables(
            PACKAGE_ROOT
        )
    )
    assert violations == (), _render(
        violations
    )

