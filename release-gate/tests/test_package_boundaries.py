from __future__ import annotations

import ast
import importlib.resources
import tomllib
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent


def test_package_metadata_declares_standalone_console_command() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["requires-python"] == ">=3.11,<3.14"
    assert metadata["project"]["scripts"]["release-gate"] == "release_gate.cli:main"
    dependency_names = {
        Requirement(item).name.lower() for item in metadata["project"]["dependencies"]
    }
    required = {"pydantic", "pyyaml", "jsonschema", "pathspec", "psutil"}
    assert required <= dependency_names


def test_package_contains_all_v1_schemas() -> None:
    schema_root = importlib.resources.files("release_gate") / "schemas"
    assert {item.name for item in schema_root.iterdir()} == {
        "config-v1.schema.json",
        "result-v1.schema.json",
        "manifest-v1.schema.json",
        "gate-decisions-v1.schema.json",
        "qualification-v1.schema.json",
    }


def test_packaged_schemas_match_canonical_contracts_byte_for_byte() -> None:
    canonical = ROOT / "schemas"
    packaged = ROOT / "src" / "release_gate" / "schemas"
    for source in canonical.glob("*.schema.json"):
        assert (packaged / source.name).read_bytes() == source.read_bytes()


def test_skill_observability_schema_matches_canonical_contract() -> None:
    canonical = ROOT / "schemas" / "gate-decisions-v1.schema.json"
    bundled = (
        ROOT
        / "skills"
        / "release-gate"
        / "references"
        / "gate-decisions-v1.schema.json"
    )
    assert bundled.read_bytes() == canonical.read_bytes()


def test_console_entry_target_is_importable() -> None:
    from release_gate.cli import main

    assert callable(main)


def test_package_imports_no_repository_specific_modules() -> None:
    source_root = ROOT / "src" / "release_gate"
    forbidden = {
        "ai_engineering_release_gate",
        "ai_engineering_shared_contracts",
        "demo",
    }

    for path in source_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(forbidden), path


def test_package_does_not_read_or_bundle_legacy_demo() -> None:
    package_files = list((ROOT / "src" / "release_gate").rglob("*"))
    assert package_files
    assert all("demo/gate" not in path.as_posix() for path in package_files)
    assert (REPOSITORY_ROOT / "demo" / "gate" / "gate.sh").exists()
