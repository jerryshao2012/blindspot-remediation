"""Read-only source repository inspection and isolated candidate capture."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from release_gate.config import ConfigError, load_config_bytes
from release_gate.models import GateConfig


class CaptureError(ValueError):
    """Candidate input cannot be captured safely."""


@dataclass(frozen=True, slots=True)
class CandidateCapture:
    repository: Path
    git_dir: Path
    git_common_dir: Path
    base_commit: str
    base_tree: str
    candidate_tree: str
    patch: bytes
    patch_sha256: str
    changed_paths: tuple[str, ...]
    policy_changed: bool
    config: GateConfig


def capture_candidate(
    repository: str | Path, *, base: str = "HEAD", allow_empty: bool = False
) -> CandidateCapture:
    """Capture the complete current worktree against a peeled base commit."""

    requested = Path(repository)
    root = _repository_root(requested)
    git_dir = _absolute_git_path(root, "--git-dir")
    common_dir = _absolute_git_path(root, "--git-common-dir")
    source_objects = (common_dir / "objects").resolve(strict=True)
    _validate_supported_index(root)
    _validate_default_evidence_path(root)

    try:
        base_commit = (
            _source_git(
                root, "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"
            )
            .decode("ascii")
            .strip()
        )
    except (subprocess.CalledProcessError, UnicodeDecodeError) as error:
        raise CaptureError(f"base ref {base!r} does not resolve to a commit") from error
    base_tree = (
        _source_git(root, "rev-parse", f"{base_commit}^{{tree}}")
        .decode("ascii")
        .strip()
    )
    try:
        policy_bytes = _source_git(root, "show", f"{base_commit}:.release-gate.yaml")
    except subprocess.CalledProcessError as error:
        raise CaptureError("base policy .release-gate.yaml is missing") from error
    try:
        config = load_config_bytes(
            policy_bytes, source=f"{base_commit}:.release-gate.yaml"
        )
    except ConfigError as error:
        raise CaptureError(f"base policy is invalid: {error}") from error

    with tempfile.TemporaryDirectory(prefix="release-gate-capture-") as temporary:
        temp_root = Path(temporary)
        object_dir = temp_root / "objects"
        object_dir.mkdir(mode=0o700)
        index = temp_root / "index"
        environment = _capture_environment(
            root=root,
            git_dir=git_dir,
            index=index,
            object_dir=object_dir,
            source_objects=source_objects,
        )
        _capture_git(root, environment, "read-tree", base_commit)
        _capture_git(
            root,
            environment,
            "add",
            "-A",
            "--",
            ".",
        )
        candidate_tree = (
            _capture_git(root, environment, "write-tree").decode("ascii").strip()
        )
        if candidate_tree == base_tree and not allow_empty:
            raise CaptureError("empty candidate: working tree matches the base commit")
        patch = _capture_git(
            root,
            environment,
            "diff-tree",
            "--no-commit-id",
            "--binary",
            "--full-index",
            "--no-color",
            "--no-ext-diff",
            "--find-renames",
            "-r",
            "-p",
            base_tree,
            candidate_tree,
        )
        names = _capture_git(
            root,
            environment,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "--find-renames",
            "-r",
            "-z",
            base_tree,
            candidate_tree,
        )

    changed_paths = _parse_name_status(names)
    return CandidateCapture(
        repository=root,
        git_dir=git_dir,
        git_common_dir=common_dir,
        base_commit=base_commit,
        base_tree=base_tree,
        candidate_tree=candidate_tree,
        patch=patch,
        patch_sha256=hashlib.sha256(patch).hexdigest(),
        changed_paths=changed_paths,
        policy_changed=".release-gate.yaml" in changed_paths,
        config=config,
    )


def _repository_root(requested: Path) -> Path:
    git_binary = _git_binary()
    try:
        result = subprocess.run(
            [git_binary, "-C", str(requested), "rev-parse", "--show-toplevel"],
            capture_output=True,
            env=_base_git_environment(),
            check=True,
        ).stdout
        return Path(result.decode("utf-8").strip()).resolve(strict=True)
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as error:
        raise CaptureError(f"{requested}: not a supported Git worktree") from error


def _absolute_git_path(root: Path, option: str) -> Path:
    value = _source_git(root, "rev-parse", "--path-format=absolute", option)
    try:
        return Path(value.decode("utf-8").strip()).resolve(strict=True)
    except (OSError, UnicodeDecodeError) as error:
        raise CaptureError(f"unable to resolve Git metadata path {option}") from error


def _validate_supported_index(root: Path) -> None:
    if _source_git(root, "ls-files", "-u"):
        raise CaptureError("unmerged index entries are not supported")


def _validate_default_evidence_path(root: Path) -> None:
    current = root
    for component in (".release-gate", "runs"):
        current /= component
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            return
        except OSError as error:
            raise CaptureError(
                f"unable to inspect default evidence path: {current}"
            ) from error
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        file_attributes = getattr(metadata, "st_file_attributes", 0)
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or bool(file_attributes & reparse_flag)
        ):
            raise CaptureError(
                f"default evidence path is redirected or unsafe: {current}"
            )


def _base_git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
            "LANG": "C",
        }
    )
    return environment


def _capture_environment(
    *,
    root: Path,
    git_dir: Path,
    index: Path,
    object_dir: Path,
    source_objects: Path,
) -> dict[str, str]:
    environment = _base_git_environment()
    environment.update(
        {
            "GIT_DIR": str(git_dir),
            "GIT_WORK_TREE": str(root),
            "GIT_INDEX_FILE": str(index),
            "GIT_OBJECT_DIRECTORY": str(object_dir),
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": _quote_alternate(source_objects),
        }
    )
    return environment


def _quote_alternate(path: Path) -> str:
    value = str(path)
    if os.pathsep not in value and '"' not in value and "\\" not in value:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _git_binary() -> str:
    binary = shutil.which("git")
    if binary is None:
        raise CaptureError("Git executable is unavailable")
    return binary


def _source_git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        [_git_binary(), "-C", str(root), *arguments],
        capture_output=True,
        env=_base_git_environment(),
        check=True,
    ).stdout


def _capture_git(root: Path, environment: dict[str, str], *arguments: str) -> bytes:
    try:
        return subprocess.run(
            [_git_binary(), "-C", str(root), *arguments],
            capture_output=True,
            env=environment,
            check=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        operation = arguments[0] if arguments else "operation"
        raise CaptureError(
            f"Git candidate capture failed during {operation}"
        ) from error


def _parse_name_status(data: bytes) -> tuple[str, ...]:
    fields = data.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    changed: list[str] = []
    cursor = 0
    try:
        while cursor < len(fields):
            status_name = fields[cursor].decode("ascii")
            cursor += 1
            path_count = 2 if status_name.startswith(("R", "C")) else 1
            for _ in range(path_count):
                changed.append(fields[cursor].decode("utf-8"))
                cursor += 1
    except (IndexError, UnicodeDecodeError) as error:
        raise CaptureError("Git returned an unsupported changed path") from error
    return tuple(dict.fromkeys(changed))
