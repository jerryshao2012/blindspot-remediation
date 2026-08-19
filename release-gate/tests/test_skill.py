from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "release-gate" / "SKILL.md"


def test_portable_skill_has_discoverable_minimal_contract() -> None:
    text = SKILL.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    metadata = yaml.safe_load(frontmatter)
    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == "release-gate"
    assert metadata["description"].startswith("Use when ")
    assert "release candidate" in metadata["description"]
    assert len(text.splitlines()) < 100


def test_skill_preserves_engine_authority_and_three_outcomes() -> None:
    text = SKILL.read_text(encoding="utf-8")
    required = [
        "release-gate run",
        ".release-gate.yaml",
        "result.json",
        "PASS",
        "FAIL",
        "NEEDS_HUMAN",
        "Do not edit",
        "Do not retry",
        "Do not reinterpret",
        "does not merge or deploy",
    ]
    for phrase in required:
        assert phrase in text


def test_skill_ui_metadata_is_host_neutral() -> None:
    metadata = yaml.safe_load(
        (SKILL.parent / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )
    assert set(metadata) == {"interface"}
    assert "$release-gate" in metadata["interface"]["default_prompt"]
    assert "dependencies" not in metadata
