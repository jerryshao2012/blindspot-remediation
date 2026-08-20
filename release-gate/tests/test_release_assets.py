from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from release_gate import __version__

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build_release_assets.py"
VERIFY_SCRIPT = ROOT / "scripts" / "verify_release_assets.py"
RC_TAG = f"release-gate-v{__version__}-rc.1"


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "release_asset_verifier", VERIFY_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_parser_rejects_unsafe_and_duplicate_paths(tmp_path: Path) -> None:
    verifier = _load_verifier()
    parse_manifest = verifier.parse_manifest
    for content in (
        "0" * 64 + "  ../wheel.whl\n",
        "0" * 64 + "  nested/wheel.whl\n",
        ("0" * 64 + "  wheel.whl\n") * 2,
        "not-a-digest  wheel.whl\n",
    ):
        manifest = tmp_path / "SHA256SUMS"
        manifest.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            parse_manifest(manifest)


def test_verifier_rejects_version_or_archive_name_mismatch(tmp_path: Path) -> None:
    verifier = _load_verifier()
    expected_asset_names = verifier.expected_asset_names
    names = expected_asset_names(__version__)
    assert f"release_gate-{__version__}-py3-none-any.whl" in names
    assert f"release_gate-{__version__}.tar.gz" in names
    assert f"release-gate-skill-codex-{__version__}.tar.gz" in names
    with pytest.raises(ValueError):
        expected_asset_names("0.2.0/../unsafe")


def test_release_builder_is_deterministic_and_self_verifying(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    for destination in (first, second):
        subprocess.run(
            [
                sys.executable,
                str(BUILD_SCRIPT),
                "--output-dir",
                str(destination),
                "--tag",
                RC_TAG,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(VERIFY_SCRIPT),
                "--assets-dir",
                str(destination),
                "--expected-tag",
                RC_TAG,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    first_bytes = {path.name: path.read_bytes() for path in sorted(first.iterdir())}
    second_bytes = {path.name: path.read_bytes() for path in sorted(second.iterdir())}
    assert first_bytes == second_bytes
    manifest_lines = first_bytes["SHA256SUMS"].decode().splitlines()
    assert manifest_lines == sorted(
        manifest_lines, key=lambda line: line.split("  ", 1)[1]
    )
    for line in manifest_lines:
        digest, name = line.split("  ", 1)
        assert hashlib.sha256(first_bytes[name]).hexdigest() == digest


def test_skill_archive_rejects_extra_and_special_members(tmp_path: Path) -> None:
    verifier = _load_verifier()
    archive_path = tmp_path / "skill.tar.gz"
    compatibility = json.dumps(
        {"cli": {"name": "release-gate", "version": __version__}}
    ).encode()
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, payload in (
            ("release-gate/SKILL.md", b"skill"),
            ("release-gate/references/compatibility.json", compatibility),
            ("release-gate/extra.txt", b"extra"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(payload))
        device = tarfile.TarInfo("release-gate/device")
        device.type = tarfile.CHRTYPE
        archive.addfile(device)
    with pytest.raises(ValueError):
        verifier._verify_skill_archive(
            archive_path,
            "copilot",
            __version__,
            (ROOT / "src/release_gate/schemas/config-v1.schema.json").read_bytes(),
            (
                ROOT / "src/release_gate/schemas/gate-decisions-v1.schema.json"
            ).read_bytes(),
        )


def test_skill_archive_rejects_exact_names_with_swapped_path_types(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    archive_path = tmp_path / "swapped-types.tar.gz"
    compatibility = json.dumps(
        {"cli": {"name": "release-gate", "version": __version__}}
    ).encode()
    with tarfile.open(archive_path, "w:gz") as archive:
        root_file = tarfile.TarInfo("release-gate")
        root_file.mode = 0o644
        root_file.size = 1
        archive.addfile(root_file, io.BytesIO(b"x"))
        for directory in ("release-gate/references",):
            info = tarfile.TarInfo(directory)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            archive.addfile(info)
        for name, payload in (
            ("release-gate/SKILL.md", b"skill"),
            ("release-gate/references/compatibility.json", compatibility),
            (
                "release-gate/references/config-v1.schema.json",
                (ROOT / "src/release_gate/schemas/config-v1.schema.json").read_bytes(),
            ),
            (
                "release-gate/references/gate-decisions-v1.schema.json",
                (
                    ROOT / "src/release_gate/schemas/gate-decisions-v1.schema.json"
                ).read_bytes(),
            ),
            ("release-gate/references/initialization.md", b"reference"),
        ):
            info = tarfile.TarInfo(name)
            info.mode = 0o644
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    with pytest.raises(ValueError, match="type"):
        verifier._verify_skill_archive(
            archive_path,
            "copilot",
            __version__,
            (ROOT / "src/release_gate/schemas/config-v1.schema.json").read_bytes(),
            (
                ROOT / "src/release_gate/schemas/gate-decisions-v1.schema.json"
            ).read_bytes(),
        )


def test_skill_archive_rejects_observability_schema_mismatch(tmp_path: Path) -> None:
    verifier = _load_verifier()
    output = tmp_path / "assets"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_skill_archives.py"),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )
    archive_path = output / f"release-gate-skill-copilot-{__version__}.tar.gz"
    with pytest.raises(ValueError, match="observability schema"):
        verifier._verify_skill_archive(
            archive_path,
            "copilot",
            __version__,
            (ROOT / "src/release_gate/schemas/config-v1.schema.json").read_bytes(),
            b"not the canonical observability schema",
        )


def test_sdist_rejects_fifo_and_oversize_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = _load_verifier()
    fifo_archive = tmp_path / "fifo.tar.gz"
    with tarfile.open(fifo_archive, "w:gz") as archive:
        fifo = tarfile.TarInfo("release_gate-0.2.0/fifo")
        fifo.type = tarfile.FIFOTYPE
        archive.addfile(fifo)
    with pytest.raises(ValueError):
        verifier._verify_sdist(fifo_archive, __version__)

    monkeypatch.setattr(verifier, "MAX_SDIST_FILE_BYTES", 1)
    oversized = tmp_path / "oversized.tar.gz"
    with tarfile.open(oversized, "w:gz") as archive:
        info = tarfile.TarInfo("release_gate-0.2.0/PKG-INFO")
        payload = b"Version: 0.2.0\n"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    with pytest.raises(ValueError, match="size"):
        verifier._verify_sdist(oversized, __version__)


def test_wheel_rejects_symlink_mode_and_oversize_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = _load_verifier()
    symlink_wheel = tmp_path / "symlink.whl"
    with zipfile.ZipFile(symlink_wheel, "w") as archive:
        info = zipfile.ZipInfo("release_gate/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "target")
    with pytest.raises(ValueError):
        verifier._verify_wheel(symlink_wheel, __version__)

    monkeypatch.setattr(verifier, "MAX_WHEEL_FILE_BYTES", 1)
    oversized = tmp_path / "oversized.whl"
    with zipfile.ZipFile(oversized, "w") as archive:
        archive.writestr("release_gate/module.py", "large")
    with pytest.raises(ValueError, match="size"):
        verifier._verify_wheel(oversized, __version__)
