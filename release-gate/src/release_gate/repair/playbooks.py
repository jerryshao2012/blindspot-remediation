"""Discovery and validation of base-trusted repair playbooks."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from release_gate.git import _base_git_environment, _git_binary

REPAIR_DIR = ".release-gate/repair"


@dataclass(frozen=True, slots=True)
class PlaybookMetadata:
    """Guidance and scoped path allowances for a specific failing check."""

    check_id: str
    name: str
    description: str
    allowed_paths: tuple[str, ...]
    guidance: str


@dataclass(frozen=True, slots=True)
class LoadedPlaybooks:
    """Collection of playbooks and diagnostic warnings loaded from base commit."""

    is_custom: bool
    check_playbooks: dict[str, PlaybookMetadata]
    extra_approved_paths: tuple[str, ...]
    warnings: tuple[str, ...]

    def guidance_for_checks(self, check_ids: Sequence[str]) -> str:
        """Produce structured guidance for the failing checks."""
        if not self.is_custom:
            return (
                "Generic repair workflow:\n"
                "- Inspect result.json and execution logs for failed checks.\n"
                "- Only edit files within approved paths.\n"
                "- Fix root causes without disabling tests or modifying policy."
            )

        sections: list[str] = []
        for check_id in check_ids:
            if check_id in self.check_playbooks:
                pb = self.check_playbooks[check_id]
                sections.append(
                    f"### Playbook: {pb.name} (Check: {check_id})\n{pb.guidance}"
                )

        if not sections:
            return (
                "Generic repair workflow (no check-specific playbooks matched):\n"
                "- Inspect result.json and execution logs for failed checks.\n"
                "- Only edit files within approved paths.\n"
                "- Fix root causes without disabling tests or modifying policy."
            )

        return "\n\n".join(sections)


def has_harness_changes(changed_paths: Sequence[str]) -> bool:
    """Return True if any changed path modifies the repair harness configuration."""
    for path in changed_paths:
        normalized = path.replace("\\", "/").strip("/")
        if normalized == REPAIR_DIR or normalized.startswith(f"{REPAIR_DIR}/"):
            return True
    return False


def load_playbooks_from_base(
    repo: Path,
    base_commit: str,
    failed_check_ids: Sequence[str] = (),
) -> LoadedPlaybooks:
    """Load and validate repair playbooks strictly from the base commit."""

    git_bin = _git_binary()
    env = _base_git_environment()

    try:
        output = subprocess.run(
            [
                git_bin,
                "-C",
                str(repo),
                "ls-tree",
                "-r",
                "--name-only",
                base_commit,
                "--",
                REPAIR_DIR,
            ],
            check=True,
            env=env,
            capture_output=True,
        ).stdout.decode("utf-8")
    except (subprocess.CalledProcessError, UnicodeDecodeError):
        return LoadedPlaybooks(
            is_custom=False,
            check_playbooks={},
            extra_approved_paths=(),
            warnings=(),
        )

    file_paths = [line.strip() for line in output.splitlines() if line.strip()]
    if not file_paths:
        return LoadedPlaybooks(
            is_custom=False,
            check_playbooks={},
            extra_approved_paths=(),
            warnings=(),
        )

    check_playbooks: dict[str, PlaybookMetadata] = {}
    warnings: list[str] = []
    extra_paths: list[str] = []

    for file_path in file_paths:
        if not file_path.endswith((".yaml", ".yml", ".json", ".md")):
            continue
        try:
            raw_bytes = subprocess.run(
                [git_bin, "-C", str(repo), "show", f"{base_commit}:{file_path}"],
                check=True,
                env=env,
                capture_output=True,
            ).stdout
            text = raw_bytes.decode("utf-8")
            if file_path.endswith(".md"):
                check_id = Path(file_path).stem
                check_playbooks[check_id] = PlaybookMetadata(
                    check_id=check_id,
                    name=f"Repair {check_id}",
                    description="",
                    allowed_paths=(),
                    guidance=text,
                )
                continue
            data = yaml.safe_load(text)
            if not isinstance(data, dict):
                warnings.append(f"malformed playbook {file_path}: expected dictionary")
                continue

            entries = data.get("checks")
            items: Sequence[tuple[Any, Any]] = (
                tuple(entries.items())
                if isinstance(entries, dict)
                else ((str(data.get("check_id", Path(file_path).stem)), data),)
            )
            for check_id, raw_entry in items:
                if not isinstance(raw_entry, dict):
                    warnings.append(
                        f"malformed playbook {file_path}: expected check mapping"
                    )
                    continue
                allowed_paths_raw = raw_entry.get(
                    "extra_approved_paths", raw_entry.get("allowed_paths", [])
                )
                allowed_paths = (
                    tuple(str(p) for p in allowed_paths_raw)
                    if isinstance(allowed_paths_raw, list)
                    else ()
                )
                check_id = str(check_id)
                playbook = PlaybookMetadata(
                    check_id=check_id,
                    name=str(raw_entry.get("name", f"Repair {check_id}")),
                    description=str(raw_entry.get("description", "")),
                    allowed_paths=allowed_paths,
                    guidance=str(raw_entry.get("guidance", "")),
                )
                check_playbooks[check_id] = playbook
                if check_id in failed_check_ids:
                    extra_paths.extend(allowed_paths)

        except Exception as error:
            warnings.append(f"malformed playbook {file_path}: {error}")

    return LoadedPlaybooks(
        is_custom=bool(check_playbooks),
        check_playbooks=check_playbooks,
        extra_approved_paths=tuple(dict.fromkeys(extra_paths)),
        warnings=tuple(warnings),
    )
