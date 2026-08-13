"""
Protect B1 canonical contract ownership.
B4/B5 compatibility types must disappear after reconciliation.
"""
from pathlib import Path
from l1_automation.architecture.repository_check import (
    find_duplicate_contract_definitions,
)
def test_shared_contracts_are_defined_only_in_contract_package() -> None:
    package_root = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "src"
        / "l1_automation"
    )
    violations = (
        find_duplicate_contract_definitions(
            package_root
        )
    )
    assert violations == (), (
        "Duplicate shared contract definitions found:\n"
        + "\n".join(
            f"{item.path}:{item.line}: "
            f"{item.details}"
            for item in violations
        )
    )

