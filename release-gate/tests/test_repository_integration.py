from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_repository_docs_distinguish_product_demo_and_scaffolding() -> None:
    expected = {
        "README.md": ["release-gate/", "demo/gate/gate.sh", "A3-release-gate-service"],
        "demo/RUN.md": ["Legacy demo", "release-gate/"],
        "demo/DIAGRAMS.md": ["Legacy demo", "release-gate/"],
        "ORIGINS.md": ["2026-08-18", "release-gate/"],
        "INDEX.md": ["2026-08-18", "release-gate/"],
        "NOTES.md": ["2026-08-18", "release-gate/"],
        "SCAFFOLDING-LEDGER.md": ["2026-08-18", "release-gate/"],
        "A3-release-gate-service/README.md": [
            "Legacy source material",
            "known defects",
        ],
    }
    for relative, phrases in expected.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase in text, f"{relative} is missing {phrase!r}"


def test_legacy_bash_interface_is_byte_for_byte_unchanged() -> None:
    expected = {
        "demo/gate/gate.sh": (
            "00d5e7e93dc5dab1d753e477e767565b87a51b469b83336bc391d71622354e06"
        ),
        "demo/gate/SKILL.md": (
            "e464e9961dea066170eedacb0c287ca8f5191e23efaa8f428c67cc13695b6e71"
        ),
    }
    for relative, digest in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest


def test_ci_covers_supported_operating_systems_and_python_versions() -> None:
    workflow = (ROOT / ".github/workflows/release-gate-ci.yml").read_text(
        encoding="utf-8"
    )
    for value in (
        "ubuntu-latest",
        "macos-latest",
        "windows-latest",
        '"3.11"',
        '"3.12"',
        '"3.13"',
        "python -m pytest",
        "python -m mypy",
        "python -m ruff",
        "python -m build",
    ):
        assert value in workflow
