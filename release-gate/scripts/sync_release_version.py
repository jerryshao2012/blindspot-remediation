#!/usr/bin/env python3
"""Synchronize generated current-release references with ``__version__``."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEMVER = r"[0-9]+\.[0-9]+\.[0-9]+"
CANONICAL_VERSION = Path("release-gate/src/release_gate/__init__.py")
COMPATIBILITY = Path(
    "release-gate/skills/release-gate/references/compatibility.json"
)
QUALIFICATION = Path("release-gate/qualification")
MARKER_START = "<!-- release-version-sync:start -->"
MARKER_END = "<!-- release-version-sync:end -->"

MARKED_PATTERNS = (
    re.compile(rf"(?<=release-gate-v){SEMVER}"),
    re.compile(rf"(?<=release_gate-){SEMVER}"),
    re.compile(
        rf"(?<=release-gate-skill-copilot-){SEMVER}"
        rf"|(?<=release-gate-skill-codex-){SEMVER}"
        rf"|(?<=release-gate-skill-claude-code-){SEMVER}"
        rf"|(?<=release-gate-skill-antigravity-){SEMVER}"
    ),
    re.compile(rf"(?<=release-gate ){SEMVER}"),
    re.compile(rf"(?<=Release Gate ){SEMVER}"),
)

MARKED_RELEASE_FILES = {
    Path("release-gate/README.md"): (MARKED_PATTERNS, 22),
    Path("release-gate/demo/python-slugify/README.md"): (MARKED_PATTERNS, 1),
    Path("release-gate/docs/adoption.md"): (
        (
            *MARKED_PATTERNS,
            re.compile(rf"(?<=download the ){SEMVER}(?= `SHA256SUMS`)"),
            re.compile(rf"(?<=immutable ){SEMVER}(?= URL)"),
            re.compile(rf"(?<=same immutable ){SEMVER}(?= release)"),
            re.compile(rf"(?m)^{SEMVER}(?= copied skill)"),
        ),
        65,
    ),
    Path("release-gate/docs/cli.md"): (
        (*MARKED_PATTERNS, re.compile(rf"(?<=The ){SEMVER}(?= assistant archives)")),
        2,
    ),
    Path("release-gate/docs/qualification.md"): (MARKED_PATTERNS, 8),
    Path("release-gate/skills/release-gate/SKILL.md"): (MARKED_PATTERNS, 2),
}

ANCHORED_RELEASE_FILES = {
    Path(".github/workflows/release-gate-ci.yml"): (
        (re.compile(rf"(?<=release-gate-v){SEMVER}"),),
        2,
    ),
    Path(".github/workflows/release-gate-release.yml"): (
        (
            re.compile(rf"(?<=release-gate-v){SEMVER}"),
            re.compile(rf"(?<=Release Gate ){SEMVER}"),
        ),
        10,
    ),
    Path("release-gate/demo/python-slugify/demo.py"): (
        (re.compile(rf"(?<=release-gate ){SEMVER}"),),
        1,
    ),
    Path("release-gate/scripts/build_release_assets.py"): (
        (re.compile(rf"(?<=deterministic v){SEMVER}(?= RC asset)"),),
        1,
    ),
    Path("release-gate/scripts/smoke_installed.py"): (
        (re.compile(rf"(?<=release-gate ){SEMVER}"),),
        1,
    ),
    Path("release-gate/scripts/validate_qualification.py"): (
        (re.compile(rf"(?<=before v){SEMVER}(?= promotion)"),),
        1,
    ),
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root (defaults to the checkout containing this script)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift without changing files",
    )
    return parser.parse_args()


def _read_version(root: Path) -> str:
    source = (root / CANONICAL_VERSION).read_text(encoding="utf-8")
    matches = re.findall(rf'^__version__ = "({SEMVER})"$', source, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError(f"expected one canonical __version__ in {CANONICAL_VERSION}")
    return matches[0]


def _replace_expected(
    path: Path,
    text: str,
    version: str,
    patterns: tuple[re.Pattern[str], ...],
    expected_count: int,
) -> str:
    updated = text
    replacements = 0
    for pattern in patterns:
        updated, count = pattern.subn(version, updated)
        replacements += count
    if replacements != expected_count:
        raise ValueError(
            f"expected {expected_count} release version targets in {path}; "
            f"found {replacements}"
        )
    return updated


def _synchronize_marked(
    path: Path,
    text: str,
    version: str,
    patterns: tuple[re.Pattern[str], ...],
    expected_count: int,
) -> str:
    if text.count(MARKER_START) != 1 or text.count(MARKER_END) != 1:
        raise ValueError(f"expected exactly one release version sync block in {path}")
    start = text.index(MARKER_START) + len(MARKER_START)
    end = text.index(MARKER_END)
    if start >= end:
        raise ValueError(f"release version sync markers are out of order in {path}")
    body = _replace_expected(
        path, text[start:end], version, patterns, expected_count
    )
    return text[:start] + body + text[end:]


def _compatibility_text(path: Path, version: str) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("cli", {}).get("name") != "release-gate":
        raise ValueError(f"unexpected compatibility metadata in {COMPATIBILITY}")
    value["cli"]["version"] = version
    return json.dumps(value, indent=2) + "\n"


def _changelog_text(path: Path, version: str) -> str:
    text = path.read_text(encoding="utf-8")
    headings = list(re.finditer(rf"(?m)^## ({SEMVER})$", text))
    if not headings:
        raise ValueError(
            "expected a current release heading in release-gate/CHANGELOG.md"
        )
    if headings[0].group(1) == version:
        return text
    if any(heading.group(1) == version for heading in headings[1:]):
        raise ValueError(
            f"canonical version {version} is already a historical changelog heading"
        )
    insertion = headings[0].start()
    return text[:insertion] + f"## {version}\n\n" + text[insertion:]


def _qualification_template(root: Path) -> Path:
    matches = sorted((root / QUALIFICATION).glob("release-gate-v*-rc.1.pending.json"))
    if len(matches) != 1:
        raise ValueError(
            "expected exactly one release-gate-v*-rc.1.pending.json template"
        )
    return matches[0]


def _write_if_changed(path: Path, expected: str, check: bool) -> bool:
    if path.read_text(encoding="utf-8") == expected:
        return False
    if not check:
        path.write_text(expected, encoding="utf-8")
    return True


def synchronize(root: Path, *, check: bool) -> tuple[str, list[str]]:
    root = root.resolve()
    version = _read_version(root)
    drift: list[str] = []

    for relative, (patterns, expected_count) in MARKED_RELEASE_FILES.items():
        path = root / relative
        expected = _synchronize_marked(
            relative,
            path.read_text(encoding="utf-8"),
            version,
            patterns,
            expected_count,
        )
        if _write_if_changed(path, expected, check):
            drift.append(f"update: {relative.as_posix()}")

    for relative, (patterns, expected_count) in ANCHORED_RELEASE_FILES.items():
        path = root / relative
        expected = _replace_expected(
            relative,
            path.read_text(encoding="utf-8"),
            version,
            patterns,
            expected_count,
        )
        if _write_if_changed(path, expected, check):
            drift.append(f"update: {relative.as_posix()}")

    compatibility = root / COMPATIBILITY
    if _write_if_changed(
        compatibility, _compatibility_text(compatibility, version), check
    ):
        drift.append(f"update: {COMPATIBILITY.as_posix()}")

    changelog_relative = Path("release-gate/CHANGELOG.md")
    changelog = root / changelog_relative
    if _write_if_changed(changelog, _changelog_text(changelog, version), check):
        drift.append(f"update: {changelog_relative.as_posix()}")

    template = _qualification_template(root)
    template_relative = template.relative_to(root)
    expected_template = _replace_expected(
        template_relative,
        template.read_text(encoding="utf-8"),
        version,
        MARKED_PATTERNS,
        19,
    )
    if _write_if_changed(template, expected_template, check):
        drift.append(f"update: {template_relative.as_posix()}")

    expected_template_path = (
        root / QUALIFICATION / f"release-gate-v{version}-rc.1.pending.json"
    )
    if template != expected_template_path:
        drift.append(
            "rename: "
            f"{template_relative.as_posix()} -> "
            f"{expected_template_path.relative_to(root).as_posix()}"
        )
        if not check:
            template.rename(expected_template_path)

    return version, drift


def main() -> int:
    arguments = _arguments()
    try:
        version, drift = synchronize(arguments.root, check=arguments.check)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"release version synchronization failed: {error}", file=sys.stderr)
        return 2

    if arguments.check and drift:
        print("release version drift:", file=sys.stderr)
        for item in drift:
            print(f"  {item}", file=sys.stderr)
        print("run scripts/sync_release_version.py", file=sys.stderr)
        return 1

    if arguments.check:
        print(f"RELEASE VERSION IN SYNC: {version}")
    else:
        print(f"SYNCHRONIZED RELEASE VERSION: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
