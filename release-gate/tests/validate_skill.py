"""CI entry point for the host-neutral skill contract."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    skill = root / "skills" / "release-gate" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError("SKILL.md must contain YAML frontmatter")
    metadata = yaml.safe_load(parts[1])
    if set(metadata) != {"name", "description"}:
        raise ValueError("skill frontmatter must contain only name and description")
    if metadata["name"] != "release-gate":
        raise ValueError("skill name does not match its directory")
    if not metadata["description"].startswith("Use when "):
        raise ValueError("skill description must state its trigger")
    if any(token in text for token in ("TODO", "/Users/", "demo/gate")):
        raise ValueError("skill contains a placeholder or host/repository coupling")
    print(f"VALID: {skill}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
