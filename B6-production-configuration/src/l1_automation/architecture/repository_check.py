"""
Static repository architecture checks.
These checks catch several high-value classes of architectural drift:
    - duplicate shared-contract definitions;
    - Azure SDK leakage into domain/application components;
    - hidden-oracle imports from online release-gate code;
    - assurance thresholds accidentally encoded as environment variables.
This is not a complete static-analysis system.
It is a small set of repository-specific invariants valuable enough to encode
directly.
"""
from __future__ import annotations
import ast
from dataclasses import dataclass
from pathlib import Path
CANONICAL_SHARED_CONTRACT_NAMES = frozenset(
    {
        "TaskRequest",
        "TaskSpecification",
        "CandidateArtifact",
        "GateDecision",
        "GateOutcome",
        "EvidenceArtifact",
        "ExecutionReceipt",
    }
)
ONLINE_PACKAGES = frozenset(
    {
        "change_execution",
        "release_gate",
        "orchestration",
        "workflow",
        "capabilities",
    }
)
AZURE_IMPORT_PREFIXES = (
    "azure.",
)
FORBIDDEN_ONLINE_IMPORT_FRAGMENTS = (
    "evaluation.oracle",
    "hidden_oracle",
    "benchmark.hidden",
)
FORBIDDEN_ASSURANCE_ENVIRONMENT_NAMES = (
    "MUTATION_SCORE",
    "FALSE_RELEASE_TOLERANCE",
    "GATE_THRESHOLD",
    "REQUIRED_EVIDENCE",
    "PASS_THRESHOLD",
)
@dataclass(frozen=True, slots=True)
class ArchitectureViolation:
    path: Path
    line: int
    rule: str
    details: str
def _python_files(
    package_root: Path,
) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in package_root.rglob(
                "*.py"
            )
            if "__pycache__" not in path.parts
        )
    )
def _parse(
    path: Path,
) -> ast.Module:
    try:
        return ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(path),
        )
    except SyntaxError as exc:
        raise RuntimeError(
            f"Cannot architecture-check syntactically invalid file "
            f"{path}: {exc}"
        ) from exc
def find_duplicate_contract_definitions(
    package_root: Path,
) -> tuple[ArchitectureViolation, ...]:
    """
    Shared contracts may be DEFINED only under:
        l1_automation/contracts/
    Other modules may import/re-export them.
    """
    violations: list[
        ArchitectureViolation
    ] = []
    for path in _python_files(
        package_root
    ):
        relative = path.relative_to(
            package_root
        )
        if (
            relative.parts
            and relative.parts[0] == "contracts"
        ):
            continue
        tree = _parse(
            path
        )
        for node in tree.body:
            if (
                isinstance(
                    node,
                    ast.ClassDef,
                )
                and node.name
                in CANONICAL_SHARED_CONTRACT_NAMES
            ):
                violations.append(
                    ArchitectureViolation(
                        path=path,
                        line=node.lineno,
                        rule=(
                            "canonical_contract_defined_outside_contracts"
                        ),
                        details=(
                            f"{node.name} must be imported from the "
                            "canonical B1 contracts package."
                        ),
                    )
                )
    return tuple(
        violations
    )
def find_azure_sdk_leakage(
    package_root: Path,
) -> tuple[ArchitectureViolation, ...]:
    """
    Detect direct Azure SDK imports in online/domain packages.
    Azure adapters may use Azure SDKs.
    Core domain/application services should depend on ports instead.
    """
    violations: list[
        ArchitectureViolation
    ] = []
    for path in _python_files(
        package_root
    ):
        relative = path.relative_to(
            package_root
        )
        if not relative.parts:
            continue
        top_package = (
            relative.parts[0]
        )
        if top_package not in ONLINE_PACKAGES:
            continue
        tree = _parse(
            path
        )
        for node in ast.walk(
            tree
        ):
            module_name: str | None = None
            if isinstance(
                node,
                ast.Import,
            ):
                for alias in node.names:
                    if alias.name.startswith(
                        AZURE_IMPORT_PREFIXES
                    ):
                        violations.append(
                            ArchitectureViolation(
                                path=path,
                                line=node.lineno,
                                rule="azure_sdk_leakage",
                                details=(
                                    f"Direct Azure import {alias.name!r} "
                                    "belongs behind an infrastructure adapter."
                                ),
                            )
                        )
            elif isinstance(
                node,
                ast.ImportFrom,
            ):
                module_name = (
                    node.module
                    or ""
                )
                if module_name.startswith(
                    AZURE_IMPORT_PREFIXES
                ):
                    violations.append(
                        ArchitectureViolation(
                            path=path,
                            line=node.lineno,
                            rule="azure_sdk_leakage",
                            details=(
                                f"Direct Azure import {module_name!r} "
                                "belongs behind an infrastructure adapter."
                            ),
                        )
                    )
    return tuple(
        violations
    )
def find_hidden_oracle_leakage(
    package_root: Path,
) -> tuple[ArchitectureViolation, ...]:
    """
    Detect obvious imports of hidden-evaluation logic from ONLINE packages.
    Infrastructure IAM checks remain necessary.
    Python imports alone cannot prove credential isolation.
    """
    violations: list[
        ArchitectureViolation
    ] = []
    for path in _python_files(
        package_root
    ):
        relative = path.relative_to(
            package_root
        )
        if (
            not relative.parts
            or relative.parts[0]
            not in ONLINE_PACKAGES
        ):
            continue
        tree = _parse(
            path
        )
        for node in ast.walk(
            tree
        ):
            candidates: list[
                str
            ] = []
            if isinstance(
                node,
                ast.Import,
            ):
                candidates.extend(
                    alias.name
                    for alias in node.names
                )
            elif isinstance(
                node,
                ast.ImportFrom,
            ):
                candidates.append(
                    node.module
                    or ""
                )
            for imported_name in candidates:
                normalized = (
                    imported_name.lower()
                )
                if any(
                    fragment
                    in normalized
                    for fragment
                    in FORBIDDEN_ONLINE_IMPORT_FRAGMENTS
                ):
                    violations.append(
                        ArchitectureViolation(
                            path=path,
                            line=node.lineno,
                            rule=(
                                "hidden_oracle_leakage"
                            ),
                            details=(
                                "Online components must not import hidden "
                                f"oracle material: {imported_name!r}."
                            ),
                        )
                    )
    return tuple(
        violations
    )
def find_assurance_policy_environment_variables(
    package_root: Path,
) -> tuple[ArchitectureViolation, ...]:
    """
    Detect suspicious environment-variable names that appear to move
    assurance policy into ordinary runtime configuration.
    This check intentionally uses a small explicit vocabulary.
    It is meant to catch architectural mistakes, not replace code review.
    """
    violations: list[
        ArchitectureViolation
    ] = []
    for path in _python_files(
        package_root
    ):
        tree = _parse(
            path
        )
        for node in ast.walk(
            tree
        ):
            if not isinstance(
                node,
                ast.Constant,
            ):
                continue
            if not isinstance(
                node.value,
                str,
            ):
                continue
            text = (
                node.value.upper()
            )
            if not text.startswith(
                "L1_"
            ):
                continue
            if any(
                marker in text
                for marker
                in FORBIDDEN_ASSURANCE_ENVIRONMENT_NAMES
            ):
                violations.append(
                    ArchitectureViolation(
                        path=path,
                        line=getattr(
                            node,
                            "lineno",
                            0,
                        ),
                        rule=(
                            "assurance_policy_in_environment"
                        ),
                        details=(
                            f"Suspicious runtime setting {node.value!r}. "
                            "Assurance thresholds should be versioned "
                            "policy artifacts."
                        ),
                    )
                )
    return tuple(
        violations
    )
def run_repository_architecture_checks(
    package_root: Path,
) -> tuple[ArchitectureViolation, ...]:
    """
    Execute all B6 architecture checks.
    """
    return (
        find_duplicate_contract_definitions(
            package_root
        )
        + find_azure_sdk_leakage(
            package_root
        )
        + find_hidden_oracle_leakage(
            package_root
        )
        + find_assurance_policy_environment_variables(
            package_root
        )
    )

