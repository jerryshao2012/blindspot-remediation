"""
B7 repository-level architecture review.
This module intentionally performs STATIC checks only.
It does not claim to prove:
    Azure RBAC isolation,
    benchmark validity,
    model quality,
    gate accuracy,
    or statistical representativeness.
Those require runtime/integration/evaluation evidence.
The purpose of this module is narrower:
    catch architectural drift cheaply and continuously.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from l1_automation.architecture.repository_check import (
    ArchitectureViolation,
    run_repository_architecture_checks,
)
@dataclass(frozen=True, slots=True)
class B7ReviewReport:
    """
    Machine-readable result of the static B7 repository review.
    """
    passed: bool
    package_root: Path
    violations: tuple[ArchitectureViolation, ...]
def run_b7_static_review(
    *,
    package_root: Path,
) -> B7ReviewReport:
    """
    Execute all currently implemented static architecture checks.
    IMPORTANT:
    `passed=True` means:
        no known STATIC repository-boundary violations were found.
    It does NOT mean:
        the capability is qualified for production.
    Keeping that distinction explicit prevents CI architecture checks from
    being mistaken for AI capability assurance.
    """
    if not package_root.exists():
        raise FileNotFoundError(
            f"Package root does not exist: {package_root}"
        )
    if not package_root.is_dir():
        raise NotADirectoryError(
            f"Package root is not a directory: {package_root}"
        )
    violations = (
        run_repository_architecture_checks(
            package_root
        )
    )
    return B7ReviewReport(
        passed=not violations,
        package_root=package_root,
        violations=violations,
    )
def format_b7_review(
    report: B7ReviewReport,
) -> str:
    """
    Produce a human-readable CI/developer report.
    """
    if report.passed:
        return (
            "B7 STATIC ARCHITECTURE REVIEW: PASS\n"
            f"Package root: {report.package_root}\n"
            "No configured static architecture violations were found.\n"
            "\n"
            "NOTE: This is not a capability qualification result."
        )
    lines = [
        "B7 STATIC ARCHITECTURE REVIEW: FAIL",
        f"Package root: {report.package_root}",
        "",
        "Violations:",
    ]
    for violation in report.violations:
        lines.append(
            f"- {violation.path}:{violation.line} "
            f"[{violation.rule}] "
            f"{violation.details}"
        )
    lines.extend(
        [
            "",
            "Resolve these architecture violations before treating the",
            "repository as B7-consistent.",
        ]
    )
    return "\n".join(
        lines
    )

