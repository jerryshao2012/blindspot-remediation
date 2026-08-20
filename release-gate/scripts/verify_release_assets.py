#!/usr/bin/env python3
"""Verify the complete, immutable Release Gate release asset set."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

HOSTS = ("antigravity", "claude-code", "codex", "copilot")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
MANIFEST_RE = re.compile(r"^([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)$")
MAX_SKILL_MEMBERS = 9
MAX_SKILL_FILE_BYTES = 1024 * 1024
MAX_SKILL_TOTAL_BYTES = 4 * 1024 * 1024
MAX_SDIST_MEMBERS = 4096
MAX_SDIST_FILE_BYTES = 8 * 1024 * 1024
MAX_SDIST_TOTAL_BYTES = 32 * 1024 * 1024
MAX_WHEEL_MEMBERS = 4096
MAX_WHEEL_FILE_BYTES = 8 * 1024 * 1024
MAX_WHEEL_TOTAL_BYTES = 32 * 1024 * 1024


def source_version(root: Path) -> str:
    source = (root / "src" / "release_gate" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']$', source, re.M)
    if match is None or not VERSION_RE.fullmatch(match.group(1)):
        raise ValueError("source __version__ is missing or invalid")
    return match.group(1)


def expected_asset_names(version: str) -> set[str]:
    if not VERSION_RE.fullmatch(version):
        raise ValueError("invalid release version")
    return {
        f"release_gate-{version}-py3-none-any.whl",
        f"release_gate-{version}.tar.gz",
        *(f"release-gate-skill-{host}-{version}.tar.gz" for host in HOSTS),
    }


def parse_manifest(path: Path) -> dict[str, str]:
    status = path.lstat()
    if not stat.S_ISREG(status.st_mode) or path.is_symlink():
        raise ValueError("checksum manifest must be a regular file")
    if status.st_size > 1024 * 1024:
        raise ValueError("checksum manifest is too large")
    entries: dict[str, str] = {}
    text = path.read_text(encoding="ascii")
    if not text.endswith("\n"):
        raise ValueError("checksum manifest must end with a newline")
    for line in text.splitlines():
        match = MANIFEST_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid checksum manifest line: {line!r}")
        digest, name = match.groups()
        candidate = PurePosixPath(name)
        if candidate.name != name or candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"unsafe checksum manifest path: {name}")
        if name == path.name or name in entries:
            raise ValueError(f"duplicate or recursive checksum entry: {name}")
        entries[name] = digest
    if list(entries) != sorted(entries):
        raise ValueError("checksum manifest entries are not sorted")
    return entries


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_text_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _metadata_version(content: str, label: str) -> str:
    versions = [
        line.removeprefix("Version: ")
        for line in content.splitlines()
        if line.startswith("Version: ")
    ]
    if len(versions) != 1:
        raise ValueError(f"{label} has invalid package metadata")
    return versions[0]


def _verify_wheel(path: Path, version: str) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) > MAX_WHEEL_MEMBERS or len(names) != len(set(names)):
            raise ValueError("wheel member count or uniqueness limit exceeded")
        total_size = 0
        for entry in entries:
            pure = PurePosixPath(entry.filename)
            if pure.is_absolute() or ".." in pure.parts:
                raise ValueError("wheel contains an unsafe path")
            if entry.file_size > MAX_WHEEL_FILE_BYTES:
                raise ValueError("wheel member size limit exceeded")
            total_size += entry.file_size
            mode = (entry.external_attr >> 16) & 0xFFFF
            kind = stat.S_IFMT(mode)
            if entry.is_dir():
                if kind not in (0, stat.S_IFDIR):
                    raise ValueError("wheel directory has a special file mode")
            elif kind not in (0, stat.S_IFREG):
                raise ValueError("wheel contains a symlink or special file mode")
        if total_size > MAX_WHEEL_TOTAL_BYTES:
            raise ValueError("wheel total size limit exceeded")
        metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
        entrypoints = [
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        ]
        if len(metadata) != 1 or len(entrypoints) != 1:
            raise ValueError("wheel metadata or entry points are missing")
        if _metadata_version(archive.read(metadata[0]).decode(), "wheel") != version:
            raise ValueError("wheel METADATA version does not match source")
        if (
            "release-gate = release_gate.cli:main"
            not in archive.read(entrypoints[0]).decode()
        ):
            raise ValueError("wheel does not expose the release-gate entry point")


def _verify_sdist(path: Path, version: str) -> None:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > MAX_SDIST_MEMBERS or len(members) != len(
            {member.name for member in members}
        ):
            raise ValueError("source distribution member count or uniqueness failed")
        total_size = 0
        for member in members:
            pure = PurePosixPath(member.name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("source distribution contains an unsafe path")
            if member.isfile():
                if member.size > MAX_SDIST_FILE_BYTES:
                    raise ValueError("source distribution member size limit exceeded")
                total_size += member.size
        if total_size > MAX_SDIST_TOTAL_BYTES:
            raise ValueError("source distribution total size limit exceeded")
        pkg_info = [member for member in members if member.name.endswith("/PKG-INFO")]
        if len(pkg_info) != 1:
            raise ValueError("source distribution PKG-INFO is missing")
        extracted = archive.extractfile(pkg_info[0])
        assert extracted is not None
        if _metadata_version(extracted.read().decode(), "sdist") != version:
            raise ValueError("source distribution version does not match source")


def _verify_skill_archive(
    path: Path,
    host: str,
    version: str,
    expected_config_schema: bytes,
    expected_observability_schema: bytes,
) -> None:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        expected = {
            "release-gate",
            "release-gate/SKILL.md",
            "release-gate/references",
            "release-gate/references/compatibility.json",
            "release-gate/references/config-v1.schema.json",
            "release-gate/references/gate-decisions-v1.schema.json",
            "release-gate/references/initialization.md",
        }
        if host == "codex":
            expected |= {
                "release-gate/agents",
                "release-gate/agents/openai.yaml",
            }
        expected_directories = {"release-gate", "release-gate/references"}
        if host == "codex":
            expected_directories.add("release-gate/agents")
        if (
            len(members) > MAX_SKILL_MEMBERS
            or len(names) != len(set(names))
            or set(names) != expected
        ):
            raise ValueError(f"{host} archive member set is not exact")
        total_size = 0
        for member in members:
            pure = PurePosixPath(member.name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or not pure.parts
                or pure.parts[0] != "release-gate"
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError(f"{host} archive contains an unsafe member")
            if member.name in expected_directories and not member.isdir():
                raise ValueError(f"{host} archive directory path has wrong type")
            if member.name not in expected_directories and not member.isfile():
                raise ValueError(f"{host} archive file path has wrong type")
            expected_mode = 0o755 if member.isdir() else 0o644
            if member.mode & 0o777 != expected_mode:
                raise ValueError(f"{host} archive member mode is not normalized")
            if member.isfile():
                if member.size > MAX_SKILL_FILE_BYTES:
                    raise ValueError(f"{host} archive member size limit exceeded")
                total_size += member.size
        if total_size > MAX_SKILL_TOTAL_BYTES:
            raise ValueError(f"{host} archive total size limit exceeded")
        compatibility = archive.extractfile(
            "release-gate/references/compatibility.json"
        )
        assert compatibility is not None
        if json.load(compatibility) != {
            "cli": {"name": "release-gate", "version": version}
        }:
            raise ValueError(f"{host} archive compatibility version does not match")
        config_schema = archive.extractfile(
            "release-gate/references/config-v1.schema.json"
        )
        assert config_schema is not None
        if config_schema.read() != expected_config_schema:
            raise ValueError(f"{host} archive config schema does not match the CLI")
        observability_schema = archive.extractfile(
            "release-gate/references/gate-decisions-v1.schema.json"
        )
        assert observability_schema is not None
        if observability_schema.read() != expected_observability_schema:
            raise ValueError(
                f"{host} archive observability schema does not match the CLI"
            )


def _verify_installed_cli(wheel: Path, version: str) -> None:
    with tempfile.TemporaryDirectory(prefix="release-gate-wheel-") as temporary:
        installed = Path(temporary) / "installed"
        installed.mkdir()
        with zipfile.ZipFile(wheel) as archive:
            # _verify_wheel has already rejected traversal and absolute paths.
            archive.extractall(installed)
        environment = os.environ.copy()
        existing_path = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = str(installed) + (
            os.pathsep + existing_path if existing_path else ""
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "from release_gate.cli import main; raise SystemExit(main())",
                "--version",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=temporary,
            env=environment,
        )
        if completed.returncode != 0:
            raise ValueError(
                "installed CLI version check failed: "
                + (completed.stderr.strip() or completed.stdout.strip())
            )
        if completed.stdout.strip() != f"release-gate {version}":
            raise ValueError("installed CLI version does not match source")


def verify_assets(
    root: Path,
    assets_dir: Path,
    expected_tag: str,
    *,
    check_installed_cli: bool = True,
) -> dict[str, str]:
    version = source_version(root)
    allowed_tags = {f"release-gate-v{version}-rc.1", f"release-gate-v{version}"}
    if expected_tag not in allowed_tags:
        raise ValueError("release tag does not match the source version")
    status = assets_dir.lstat()
    if not stat.S_ISDIR(status.st_mode) or assets_dir.is_symlink():
        raise ValueError("assets directory must be an ordinary directory")
    expected = expected_asset_names(version)
    actual = {path.name for path in assets_dir.iterdir()}
    if actual != expected | {"SHA256SUMS"}:
        raise ValueError(f"release asset set mismatch: {sorted(actual)}")
    manifest = parse_manifest(assets_dir / "SHA256SUMS")
    if set(manifest) != expected:
        raise ValueError("checksum manifest does not list the exact release asset set")
    for name, expected_hash in manifest.items():
        path = assets_dir / name
        item_status = path.lstat()
        if not stat.S_ISREG(item_status.st_mode) or path.is_symlink():
            raise ValueError(f"release asset must be a regular file: {name}")
        if _hash(path) != expected_hash:
            raise ValueError(f"release asset checksum mismatch: {name}")

    compatibility = json.loads(
        (root / "skills/release-gate/references/compatibility.json").read_text(
            encoding="utf-8"
        )
    )
    if compatibility != {"cli": {"name": "release-gate", "version": version}}:
        raise ValueError("canonical compatibility version does not match source")
    wheel = assets_dir / f"release_gate-{version}-py3-none-any.whl"
    expected_config_schema = _normalized_text_bytes(
        root / "src/release_gate/schemas/config-v1.schema.json"
    )
    expected_observability_schema = _normalized_text_bytes(
        root / "src/release_gate/schemas/gate-decisions-v1.schema.json"
    )
    _verify_wheel(wheel, version)
    _verify_sdist(assets_dir / f"release_gate-{version}.tar.gz", version)
    for host in HOSTS:
        _verify_skill_archive(
            assets_dir / f"release-gate-skill-{host}-{version}.tar.gz",
            host,
            version,
            expected_config_schema,
            expected_observability_schema,
        )
    if check_installed_cli:
        _verify_installed_cli(wheel, version)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--expected-tag", required=True)
    parser.add_argument("--skip-installed-cli-check", action="store_true")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = verify_assets(
        root,
        arguments.assets_dir.absolute(),
        arguments.expected_tag,
        check_installed_cli=not arguments.skip_installed_cli_check,
    )
    print(f"verified {len(manifest)} release assets for {arguments.expected_tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
