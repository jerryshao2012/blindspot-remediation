"""Create a deterministic, length-delimited binding for demo source content."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ITEMS = (
    ".gitignore",
    "README.md",
    "assets",
    "controls",
    "demo.py",
    "examples",
    "oracle",
    "pyproject.toml",
    "requirements-dev.txt",
    "spec.md",
    "src",
    "tests",
    "tools/gauntlet.py",
    "tools/gauntlet.sh",
    "tools/mutants.py",
    "tools/source_state.py",
)
CANDIDATE_ITEMS = (
    ".gitignore",
    ".release-gate.yaml",
    "README.md",
    "examples",
    "pyproject.toml",
    "requirements-dev.txt",
    "spec.md",
    "src",
    "tests",
    "tools/gauntlet.py",
    "tools/gauntlet.sh",
    "tools/mutants.py",
    "tools/source_state.py",
)
EXCLUDED_DIRS = {
    ".hypothesis",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}
EXCLUDED_FILES = {".coverage", ".DS_Store", "coverage.xml"}


class SourceStateError(RuntimeError):
    """The requested source binding cannot be produced safely."""


@dataclass(frozen=True, slots=True)
class ContentManifest:
    digest: str
    files: tuple[str, ...]


def _is_generated(path: Path) -> bool:
    return (
        any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in path.parts)
        or path.name in EXCLUDED_FILES
        or path.suffix == ".pyc"
    )


def _validate_item(item: str) -> PurePosixPath:
    path = PurePosixPath(item)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise SourceStateError(f"unsafe source input: {item}")
    return path


def _files_for_item(root: Path, item: str) -> list[Path]:
    relative = _validate_item(item)
    candidate = root.joinpath(*relative.parts)
    if not candidate.exists() and not candidate.is_symlink():
        raise SourceStateError(f"source input is missing: {item}")
    if candidate.is_symlink():
        raise SourceStateError(
            f"source input is not a regular file or directory: {item}"
        )
    if candidate.is_file():
        return [candidate]
    if not candidate.is_dir():
        raise SourceStateError(
            f"source input is not a regular file or directory: {item}"
        )

    return _walk_directory(root, candidate, item)


def _walk_directory(root: Path, candidate: Path, item: str) -> list[Path]:

    files: list[Path] = []
    try:
        for path in candidate.rglob("*"):
            scoped = path.relative_to(root)
            if _is_generated(scoped):
                continue
            if path.is_symlink() or (not path.is_file() and not path.is_dir()):
                raise SourceStateError(
                    f"source input is not a regular file: {scoped.as_posix()}"
                )
            if path.is_file():
                files.append(path)
    except OSError as error:
        raise SourceStateError(
            f"cannot enumerate source input {item}: {error}"
        ) from error
    if not files:
        raise SourceStateError(f"source input contains no regular files: {item}")
    return files


def _read_regular(path: Path, root: Path) -> bytes:
    relative = path.relative_to(root).as_posix()
    if path.is_symlink() or not path.is_file():
        raise SourceStateError(f"source input is not a regular file: {relative}")
    try:
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
    except OSError as error:
        raise SourceStateError(
            f"cannot read source input {relative}: {error}"
        ) from error
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise SourceStateError(f"source input changed while hashing: {relative}")
    return content


def content_manifest(root: Path, items: tuple[str, ...]) -> ContentManifest:
    resolved = root.resolve(strict=True)
    paths: dict[str, Path] = {}
    for item in items:
        for path in _files_for_item(resolved, item):
            relative = path.relative_to(resolved).as_posix()
            paths[relative] = path
    digest = hashlib.sha256()
    for relative in sorted(paths):
        path_bytes = os.fsencode(relative)
        content = _read_regular(paths[relative], resolved)
        digest.update(len(path_bytes).to_bytes(8, "big"))
        digest.update(path_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return ContentManifest(digest.hexdigest(), tuple(sorted(paths)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        action="store_true",
        help="bind the generated candidate manifest instead of the outer demo",
    )
    arguments = parser.parse_args(argv)
    items = CANDIDATE_ITEMS if arguments.candidate else SOURCE_ITEMS
    try:
        manifest = content_manifest(ROOT, items)
    except (OSError, SourceStateError) as error:
        print(f"source-state error: {error}", file=sys.stderr)
        return 2
    print("manifest: sha256(path-length || path || content-length || content)")
    print(f"files:    {len(manifest.files)}")
    print(f"tree:     {manifest.digest}")
    scope = "candidate" if arguments.candidate else "outer-demo"
    print(f"scope:    {scope}")
    print("commit provenance: not asserted; bind evidence to this content digest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
