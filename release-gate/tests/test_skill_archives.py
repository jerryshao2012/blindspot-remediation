from __future__ import annotations

import hashlib
import io
import os
import runpy
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

import pytest
import yaml

from release_gate import __version__

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "build_skill_archives.py"
HOSTS = ("copilot", "codex", "claude-code", "antigravity")
VERSION = __version__


def _lf(content: bytes) -> bytes:
    return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _build(output: Path) -> dict[str, bytes]:
    subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {path.name: path.read_bytes() for path in sorted(output.iterdir())}


def _minimal_builder_checkout(destination: Path, *, crlf: bool) -> None:
    sources = (
        Path("scripts/build_skill_archives.py"),
        Path("src/release_gate/__init__.py"),
        Path("src/release_gate/schemas/config-v1.schema.json"),
        Path("src/release_gate/schemas/gate-decisions-v1.schema.json"),
        Path("skills/release-gate/SKILL.md"),
        Path("skills/release-gate/agents/openai.yaml"),
        Path("skills/release-gate/references/compatibility.json"),
        Path("skills/release-gate/references/config-v1.schema.json"),
        Path("skills/release-gate/references/gate-decisions-v1.schema.json"),
        Path("skills/release-gate/references/initialization.md"),
    )
    for relative in sources:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = (ROOT / relative).read_bytes()
        if crlf:
            content = _lf(content).replace(b"\n", b"\r\n")
        target.write_bytes(content)


def _archive_members(blob: bytes) -> tuple[tarfile.TarFile, dict[str, tarfile.TarInfo]]:
    archive = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
    return archive, {member.name: member for member in archive.getmembers()}


def _skill_parts(
    archive: tarfile.TarFile, members: dict[str, tarfile.TarInfo]
) -> tuple[dict[str, object], bytes]:
    extracted = archive.extractfile(members["release-gate/SKILL.md"])
    assert extracted is not None
    content = extracted.read()
    _, frontmatter, body = content.split(b"---", 2)
    return yaml.safe_load(frontmatter), body


def test_builder_produces_exact_deterministic_archive_set(tmp_path: Path) -> None:
    first = _build(tmp_path / "first")
    second = _build(tmp_path / "second")
    expected = {f"release-gate-skill-{host}-{VERSION}.tar.gz" for host in HOSTS}
    assert set(first) == expected
    assert first == second
    assert {name: hashlib.sha256(blob).hexdigest() for name, blob in first.items()} == {
        name: hashlib.sha256(blob).hexdigest() for name, blob in second.items()
    }


def test_builder_is_checkout_line_ending_independent(tmp_path: Path) -> None:
    lf_root = tmp_path / "lf"
    crlf_root = tmp_path / "crlf"
    _minimal_builder_checkout(lf_root, crlf=False)
    _minimal_builder_checkout(crlf_root, crlf=True)
    outputs: list[dict[str, bytes]] = []
    for root in (lf_root, crlf_root):
        output = root / "dist"
        subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "build_skill_archives.py"),
                "--output-dir",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(
            {path.name: path.read_bytes() for path in sorted(output.iterdir())}
        )
    assert outputs[0] == outputs[1]


def test_builder_refuses_destination_symlink_without_touching_target(
    tmp_path: Path,
) -> None:
    output = tmp_path / "dist"
    output.mkdir()
    victim = tmp_path / "victim"
    victim.write_bytes(b"user data")
    destination = output / f"release-gate-skill-copilot-{VERSION}.tar.gz"
    try:
        destination.symlink_to(victim)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert victim.read_bytes() == b"user data"
    assert destination.is_symlink()


def test_source_swap_to_symlink_is_refused_without_reading_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"approved source\n")
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"must not be read\n")
    probe = tmp_path / "probe"
    try:
        probe.symlink_to(victim)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")
    probe.unlink()

    namespace = runpy.run_path(str(SCRIPT), run_name="skill_archive_test")
    reader = namespace["_read_regular"]
    assert callable(reader)
    real_open = os.open
    real_read_bytes = Path.read_bytes
    swapped = False

    def swap_source() -> None:
        nonlocal swapped
        if swapped:
            return
        swapped = True
        source.rename(tmp_path / "original.txt")
        source.symlink_to(victim)

    def swapping_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        if Path(path) == source:
            swap_source()
        return real_open(path, flags, *args, **kwargs)

    def swapping_read_bytes(path: Path) -> bytes:
        if path == source:
            swap_source()
        return real_read_bytes(path)

    monkeypatch.setattr(os, "open", swapping_open)
    monkeypatch.setattr(Path, "read_bytes", swapping_read_bytes)
    with pytest.raises((OSError, ValueError)):
        reader(source)
    assert victim.read_bytes() == b"must not be read\n"


def test_builder_safely_replaces_existing_regular_archives(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    first = _build(output)
    for path in output.iterdir():
        path.write_bytes(b"stale regular archive")
    second = _build(output)
    assert second == first


def test_archives_are_safe_normalized_and_have_expected_files(tmp_path: Path) -> None:
    archives = _build(tmp_path / "dist")
    canonical_compatibility = _lf(
        (
            ROOT / "skills" / "release-gate" / "references" / "compatibility.json"
        ).read_bytes()
    )
    canonical_schema = (
        ROOT / "src" / "release_gate" / "schemas" / "config-v1.schema.json"
    ).read_bytes()
    canonical_observability_schema = (
        ROOT
        / "src"
        / "release_gate"
        / "schemas"
        / "gate-decisions-v1.schema.json"
    ).read_bytes()
    canonical_initialization = _lf(
        (
            ROOT / "skills" / "release-gate" / "references" / "initialization.md"
        ).read_bytes()
    )
    for host in HOSTS:
        name = f"release-gate-skill-{host}-{VERSION}.tar.gz"
        archive, members = _archive_members(archives[name])
        paths = set(members)
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
            expected |= {"release-gate/agents", "release-gate/agents/openai.yaml"}
        assert paths == expected
        for member in members.values():
            path = PurePosixPath(member.name)
            assert not path.is_absolute()
            assert ".." not in path.parts
            assert not member.issym() and not member.islnk()
            assert member.mtime == 0
            assert member.uid == member.gid == 0
            assert member.uname == member.gname == ""
            assert member.mode == (0o755 if member.isdir() else 0o644)
        compatibility = archive.extractfile(
            members["release-gate/references/compatibility.json"]
        )
        assert compatibility is not None
        assert compatibility.read() == canonical_compatibility
        schema = archive.extractfile(
            members["release-gate/references/config-v1.schema.json"]
        )
        assert schema is not None
        assert schema.read() == canonical_schema
        observability_schema = archive.extractfile(
            members["release-gate/references/gate-decisions-v1.schema.json"]
        )
        assert observability_schema is not None
        assert observability_schema.read() == canonical_observability_schema
        initialization = archive.extractfile(
            members["release-gate/references/initialization.md"]
        )
        assert initialization is not None
        assert initialization.read() == canonical_initialization
        archive.close()


def test_adapter_metadata_and_body_are_exact(tmp_path: Path) -> None:
    archives = _build(tmp_path / "dist")
    bodies: dict[str, bytes] = {}
    expected_description = (
        "Use only when explicitly invoked by the user to report its version, "
        "initialize, validate, or run Release Gate. Do not invoke implicitly."
    )
    for host in HOSTS:
        archive, members = _archive_members(
            archives[f"release-gate-skill-{host}-{VERSION}.tar.gz"]
        )
        metadata, body = _skill_parts(archive, members)
        bodies[host] = body
        portable = {"name", "description"}
        assert metadata["name"] == "release-gate"
        assert metadata["description"] == expected_description
        if host in {"copilot", "claude-code"}:
            assert set(metadata) == portable | {
                "argument-hint",
                "user-invocable",
                "disable-model-invocation",
            }
            assert metadata["argument-hint"] == (
                "<--version|init|validate|run> [options]"
            )
            assert metadata["user-invocable"] is True
            assert metadata["disable-model-invocation"] is True
        else:
            assert set(metadata) == portable
        archive.close()
    assert len({hashlib.sha256(body).digest() for body in bodies.values()}) == 1


def test_frontmatter_serializer_quotes_yaml_special_scalars() -> None:
    namespace = runpy.run_path(str(SCRIPT), run_name="skill_archive_test")
    serializer = namespace["_skill_bytes"]
    assert callable(serializer)
    description = "Explicit: #release [gate] {safe} true"
    content = serializer(
        {"name": "release-gate", "description": description}, b"\nBody\n", "copilot"
    )
    _, frontmatter, body = content.split(b"---", 2)
    metadata = yaml.safe_load(frontmatter)
    assert list(metadata) == [
        "name",
        "description",
        "argument-hint",
        "user-invocable",
        "disable-model-invocation",
    ]
    assert metadata["description"] == description
    assert body == b"\nBody\n"
    with pytest.raises(ValueError, match="must be strings"):
        serializer({"name": "release-gate", "description": True}, body, "codex")


def test_codex_archive_disables_implicit_invocation(tmp_path: Path) -> None:
    archives = _build(tmp_path / "dist")
    archive, members = _archive_members(
        archives[f"release-gate-skill-codex-{VERSION}.tar.gz"]
    )
    extracted = archive.extractfile(members["release-gate/agents/openai.yaml"])
    assert extracted is not None
    content = extracted.read()
    assert content == _lf(
        (ROOT / "skills" / "release-gate" / "agents" / "openai.yaml").read_bytes()
    )
    metadata = yaml.safe_load(content)
    assert metadata["policy"] == {"allow_implicit_invocation": False}
    assert "$release-gate" in metadata["interface"]["default_prompt"]
    archive.close()
