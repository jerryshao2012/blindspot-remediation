#!/usr/bin/env python3
"""Build the deterministic v0.4.0 RC asset set exactly once."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from verify_release_assets import source_version, verify_assets


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _ordinary_directory(path: Path) -> bool:
    status = path.lstat()
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return (
        stat.S_ISDIR(status.st_mode)
        and not path.is_symlink()
        and not getattr(status, "st_file_attributes", 0) & reparse
    )


def build_release_assets(root: Path, output_dir: Path, tag: str) -> None:
    version = source_version(root)
    expected_tag = f"release-gate-v{version}-rc.1"
    if tag != expected_tag:
        raise ValueError(
            f"RC assets must be built for {expected_tag}; "
            "final promotion must reuse them"
        )
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError(
            "output directory already exists; refusing to replace release data"
        )
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    if not _ordinary_directory(parent):
        raise ValueError("output parent must be an ordinary directory")

    temporary = Path(tempfile.mkdtemp(prefix=".release-gate-assets-", dir=parent))
    staged = temporary / "assets"
    package_dir = temporary / "packages"
    skill_dir = temporary / "skills"
    staged.mkdir()
    environment = os.environ.copy()
    environment.update({"PYTHONHASHSEED": "0", "SOURCE_DATE_EPOCH": "315532800"})
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--wheel",
                "--sdist",
                "--outdir",
                str(package_dir),
            ],
            cwd=root,
            env=environment,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(root / "scripts/build_skill_archives.py"),
                "--output-dir",
                str(skill_dir),
            ],
            cwd=root,
            env=environment,
            check=True,
        )
        for source in sorted((*package_dir.iterdir(), *skill_dir.iterdir())):
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"build produced a non-regular asset: {source.name}")
            os.replace(source, staged / source.name)
        lines = [
            f"{_digest(path)}  {path.name}\n"
            for path in sorted(staged.iterdir(), key=lambda item: item.name)
        ]
        (staged / "SHA256SUMS").write_text("".join(lines), encoding="ascii")
        verify_assets(root, staged, tag)
        if output_dir.exists() or output_dir.is_symlink():
            raise ValueError("output directory appeared during build")
        os.replace(staged, output_dir)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    arguments = parser.parse_args()
    build_release_assets(
        Path(__file__).resolve().parents[1],
        arguments.output_dir.absolute(),
        arguments.tag,
    )
    print(arguments.output_dir.absolute())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
