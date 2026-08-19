"""CI entry point for the host-neutral skill contract."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    skill_root = root / "skills" / "release-gate"
    skill = skill_root / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError("SKILL.md must contain YAML frontmatter")
    metadata = yaml.safe_load(parts[1])
    if set(metadata) != {"name", "description"}:
        raise ValueError("skill frontmatter must contain only name and description")
    if metadata["name"] != "release-gate":
        raise ValueError("skill name does not match its directory")
    if not metadata["description"].startswith("Use only when explicitly invoked"):
        raise ValueError("skill description must require explicit invocation")
    if "Do not invoke implicitly" not in metadata["description"]:
        raise ValueError("skill description must disable implicit routing")
    if any(token in text for token in ("TODO", "/Users/", "demo/gate")):
        raise ValueError("skill contains a placeholder or host/repository coupling")

    required = (
        "Missing or unknown subcommand",
        "make no operational tool call",
        "release-gate --version",
        "release-gate init --repo <repo> --from-config <temporary-approved-config>",
        "release-gate validate --repo <repo>",
        "release-gate run --repo <repo> --base <ref>",
        "combined final diff",
        "references/initialization.md",
        "references/config-v1.schema.json",
        "Every field",
        "result.json",
        "PASS",
        "FAIL",
        "NEEDS_HUMAN",
    )
    missing = [phrase for phrase in required if phrase not in text]
    if missing:
        raise ValueError(f"skill is missing required contracts: {missing}")

    source = (root / "src" / "release_gate" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']$', source, re.M)
    if match is None:
        raise ValueError("could not read source version")
    version = match.group(1)
    compatibility = json.loads(
        (skill_root / "references" / "compatibility.json").read_text(encoding="utf-8")
    )
    if compatibility != {"cli": {"name": "release-gate", "version": version}}:
        raise ValueError("compatibility reference must match source version")
    if f"`release-gate {version}`" not in text:
        raise ValueError("skill version check must match source version")

    bundled_schema = skill_root / "references" / "config-v1.schema.json"
    cli_schema = root / "src" / "release_gate" / "schemas" / "config-v1.schema.json"
    if bundled_schema.read_bytes() != cli_schema.read_bytes():
        raise ValueError("bundled config schema must exactly match the CLI schema")
    initialization = (skill_root / "references" / "initialization.md").read_text(
        encoding="utf-8"
    )
    if (
        "no `network` field" not in initialization
        or "without a shell" not in initialization
    ):
        raise ValueError("initialization reference is incomplete")

    agent_metadata = yaml.safe_load(
        (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )
    if set(agent_metadata) != {"interface", "policy"}:
        raise ValueError("Codex metadata must contain only interface and policy")
    if agent_metadata["policy"] != {"allow_implicit_invocation": False}:
        raise ValueError("Codex metadata must disable implicit invocation")
    print(f"VALID: {skill}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
