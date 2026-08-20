#!/usr/bin/env python3
"""Build deterministic, host-specific Release Gate skill archives."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import stat
import tarfile
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

import yaml

HOSTS = ("copilot", "codex", "claude-code", "antigravity")
COMMAND_METADATA = (
    'argument-hint: "<--version|init|validate|run> [options]"\n'
    "user-invocable: true\n"
    "disable-model-invocation: true\n"
)
MAX_SOURCE_BYTES = 1024 * 1024


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _is_regular_non_reparse(status: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(status, "st_file_attributes", 0)
    return stat.S_ISREG(status.st_mode) and not attributes & reparse_flag


def _identity(status: os.stat_result) -> tuple[int, int]:
    return (status.st_dev, status.st_ino)


def _change_signature(status: os.stat_result) -> tuple[int, int, int]:
    return (status.st_size, status.st_mtime_ns, status.st_ctime_ns)


def _read_bounded(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    remaining = MAX_SOURCE_BYTES + 1
    while remaining:
        chunk = os.read(descriptor, min(remaining, 64 * 1024))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_regular(path: Path) -> bytes:
    observed = os.lstat(path)
    if not _is_regular_non_reparse(observed):
        raise ValueError(f"archive source must be a regular file: {path}")
    if observed.st_size > MAX_SOURCE_BYTES:
        raise ValueError(f"archive source exceeds 1 MiB: {path}")

    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not _is_regular_non_reparse(opened) or _identity(opened) != _identity(
            observed
        ):
            raise ValueError(f"archive source changed before reading: {path}")
        data = _read_bounded(descriptor)
        if len(data) > MAX_SOURCE_BYTES:
            raise ValueError(f"archive source exceeds 1 MiB: {path}")
        os.lseek(descriptor, 0, os.SEEK_SET)
        confirmation = _read_bounded(descriptor)
        final = os.fstat(descriptor)
        if (
            confirmation != data
            or _identity(final) != _identity(opened)
            or _change_signature(final) != _change_signature(opened)
            or final.st_size != len(data)
        ):
            raise ValueError(f"archive source changed while reading: {path}")
    finally:
        os.close(descriptor)

    current = os.lstat(path)
    if (
        not _is_regular_non_reparse(current)
        or _identity(current) != _identity(opened)
        or _change_signature(current) != _change_signature(opened)
    ):
        raise ValueError(f"archive source changed while reading: {path}")
    return data


def _read_normalized_text(path: Path) -> bytes:
    """Return strict UTF-8 text with checkout-independent LF line endings."""

    text = _read_regular(path).decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _source_version(root: Path) -> str:
    source = _read_normalized_text(
        root / "src" / "release_gate" / "__init__.py"
    ).decode("utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']$', source, re.M)
    if match is None:
        raise ValueError("could not read release_gate.__version__")
    return match.group(1)


def _canonical_skill(skill_root: Path) -> tuple[dict[str, object], bytes]:
    content = _read_normalized_text(skill_root / "SKILL.md")
    parts = content.split(b"---", 2)
    if len(parts) != 3 or parts[0] != b"":
        raise ValueError("canonical SKILL.md must have YAML frontmatter")
    metadata = yaml.safe_load(parts[1])
    if not isinstance(metadata, dict) or set(metadata) != {"name", "description"}:
        raise ValueError("canonical frontmatter must contain name and description")
    return metadata, parts[2]


def _skill_bytes(metadata: Mapping[str, object], body: bytes, host: str) -> bytes:
    name = metadata["name"]
    description = metadata["description"]
    if not isinstance(name, str) or not isinstance(description, str):
        raise ValueError("canonical name and description must be strings")
    portable = "---\n"
    portable += f"name: {json.dumps(name, ensure_ascii=False)}\n"
    portable += f"description: {json.dumps(description, ensure_ascii=False)}\n"
    if host in {"copilot", "claude-code"}:
        portable += COMMAND_METADATA
    return portable.encode("utf-8") + b"---" + body


def _validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or path.parts[0] != "release-gate":
        raise ValueError(f"unsafe archive member: {name}")


def _tar_info(name: str, *, directory: bool, size: int = 0) -> tarfile.TarInfo:
    _validate_member_name(name)
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE if directory else tarfile.REGTYPE
    info.mode = 0o755 if directory else 0o644
    info.size = 0 if directory else size
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def _archive_bytes(files: Mapping[str, bytes]) -> bytes:
    directories = {"release-gate"}
    for name in files:
        parent = PurePosixPath(name).parent
        while str(parent) != ".":
            directories.add(str(parent))
            parent = parent.parent

    compressed = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=compressed, compresslevel=9, mtime=0
    ) as gzip_file:
        with tarfile.open(
            fileobj=gzip_file, mode="w", format=tarfile.USTAR_FORMAT
        ) as tar:
            for name in sorted(directories | set(files)):
                if name in directories:
                    tar.addfile(_tar_info(name, directory=True))
                else:
                    payload = files[name]
                    tar.addfile(
                        _tar_info(name, directory=False, size=len(payload)),
                        io.BytesIO(payload),
                    )
    return compressed.getvalue()


def _destination_snapshot(path: Path) -> tuple[object, ...] | None:
    try:
        observed = os.lstat(path)
    except FileNotFoundError:
        return None
    if not _is_regular_non_reparse(observed):
        raise ValueError(f"archive destination must be a regular file: {path}")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not _is_regular_non_reparse(opened) or _identity(opened) != _identity(
            observed
        ):
            raise ValueError(f"archive destination changed during inspection: {path}")
        digest = hashlib.sha256()
        while chunk := os.read(descriptor, 64 * 1024):
            digest.update(chunk)
        final = os.fstat(descriptor)
        if (
            _identity(final) != _identity(opened)
            or final.st_size != opened.st_size
            or final.st_mtime_ns != opened.st_mtime_ns
            or final.st_ctime_ns != opened.st_ctime_ns
        ):
            raise ValueError(f"archive destination changed during inspection: {path}")
    finally:
        os.close(descriptor)
    current = os.lstat(path)
    if not _is_regular_non_reparse(current) or _identity(current) != _identity(opened):
        raise ValueError(f"archive destination changed during inspection: {path}")
    return (
        *_identity(opened),
        opened.st_size,
        opened.st_mtime_ns,
        opened.st_ctime_ns,
        digest.digest(),
    )


def _write_archive(destination: Path, payload: bytes) -> None:
    before = _destination_snapshot(destination)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    temporary_status = os.fstat(descriptor)
    if not _is_regular_non_reparse(temporary_status):
        os.close(descriptor)
        raise ValueError("temporary archive is not a regular file")
    temporary_identity = _identity(temporary_status)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            temporary_status = os.fstat(stream.fileno())
            if (
                not _is_regular_non_reparse(temporary_status)
                or _identity(temporary_status) != temporary_identity
            ):
                raise ValueError("temporary archive changed while writing")

        if _destination_snapshot(destination) != before:
            raise ValueError(
                f"archive destination changed before replacement: {destination}"
            )
        staged = os.lstat(temporary)
        if (
            not _is_regular_non_reparse(staged)
            or _identity(staged) != temporary_identity
        ):
            raise ValueError("temporary archive changed before replacement")
        os.replace(temporary, destination)
        published = os.lstat(destination)
        if (
            not _is_regular_non_reparse(published)
            or _identity(published) != temporary_identity
        ):
            raise ValueError("archive replacement could not be verified")
    finally:
        try:
            staged = os.lstat(temporary)
        except FileNotFoundError:
            pass
        else:
            if _identity(staged) == temporary_identity:
                os.unlink(temporary)


def build_archives(root: Path, output_dir: Path) -> list[Path]:
    skill_root = root / "skills" / "release-gate"
    for directory in (skill_root, skill_root / "agents", skill_root / "references"):
        info = directory.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"archive source must be a directory: {directory}")

    version = _source_version(root)
    compatibility_bytes = _read_normalized_text(
        skill_root / "references" / "compatibility.json"
    )
    compatibility = json.loads(compatibility_bytes)
    expected = {"cli": {"name": "release-gate", "version": version}}
    if compatibility != expected:
        raise ValueError("compatibility.json does not match the source version")

    config_schema = _read_normalized_text(
        skill_root / "references" / "config-v1.schema.json"
    )
    canonical_config_schema = _read_normalized_text(
        root / "src" / "release_gate" / "schemas" / "config-v1.schema.json"
    )
    if config_schema != canonical_config_schema:
        raise ValueError("bundled config schema does not match the CLI schema")
    observability_schema = _read_normalized_text(
        skill_root / "references" / "gate-decisions-v1.schema.json"
    )
    canonical_observability_schema = _read_normalized_text(
        root / "src" / "release_gate" / "schemas" / "gate-decisions-v1.schema.json"
    )
    if observability_schema != canonical_observability_schema:
        raise ValueError("bundled observability schema does not match the CLI schema")
    initialization = _read_normalized_text(
        skill_root / "references" / "initialization.md"
    )

    metadata, body = _canonical_skill(skill_root)
    openai = _read_normalized_text(skill_root / "agents" / "openai.yaml")
    openai_metadata = yaml.safe_load(openai)
    if not isinstance(openai_metadata, dict) or set(openai_metadata) != {
        "interface",
        "policy",
    }:
        raise ValueError("Codex metadata must contain interface and policy")
    if openai_metadata["policy"] != {"allow_implicit_invocation": False}:
        raise ValueError("Codex metadata must disable implicit invocation")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_status = os.lstat(output_dir)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        stat.S_ISLNK(output_status.st_mode)
        or not stat.S_ISDIR(output_status.st_mode)
        or getattr(output_status, "st_file_attributes", 0) & reparse_flag
    ):
        raise ValueError("output directory must be an ordinary directory")
    built: list[Path] = []
    for host in HOSTS:
        files = {
            "release-gate/SKILL.md": _skill_bytes(metadata, body, host),
            "release-gate/references/compatibility.json": compatibility_bytes,
            "release-gate/references/config-v1.schema.json": config_schema,
            (
                "release-gate/references/gate-decisions-v1.schema.json"
            ): observability_schema,
            "release-gate/references/initialization.md": initialization,
        }
        if host == "codex":
            files["release-gate/agents/openai.yaml"] = openai
        destination = output_dir / f"release-gate-skill-{host}-{version}.tar.gz"
        _write_archive(destination, _archive_bytes(files))
        built.append(destination)
    return built


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for path in build_archives(root, _parse_arguments().output_dir.absolute()):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
