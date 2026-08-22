"""Disposable, independent base and candidate Git workspaces."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from release_gate.git import CandidateCapture


class WorkspaceError(RuntimeError):
    """A clean workspace could not be reconstructed safely."""


@dataclass(frozen=True, slots=True)
class WorkspacePair:
    root: Path
    base: Path
    candidate: Path


@contextmanager
def clean_workspaces(
    capture: CandidateCapture, *, parent: str | Path | None = None
) -> Iterator[WorkspacePair]:
    """Yield verified independent clones and remove them on every exit path."""

    parent_path = _validate_parent(capture, parent)
    with tempfile.TemporaryDirectory(
        prefix="release-gate-workspaces-", dir=parent_path
    ) as temporary:
        root = Path(temporary).resolve(strict=True)
        _require_disjoint(root, capture)
        base = root / "base"
        candidate = root / "candidate"
        if hashlib.sha256(capture.patch).hexdigest() != capture.patch_sha256:
            raise WorkspaceError("candidate patch digest mismatch")
        _clone(capture, base)
        _clone(capture, candidate)
        _verify_base(capture, base)
        _apply_candidate(capture, candidate)
        yield WorkspacePair(root=root, base=base, candidate=candidate)


def _validate_parent(
    capture: CandidateCapture, parent: str | Path | None
) -> Path | None:
    if parent is None:
        return None
    requested = Path(parent)
    try:
        resolved = requested.resolve(strict=True)
    except OSError as error:
        raise WorkspaceError(f"workspace parent does not exist: {requested}") from error
    if not resolved.is_dir():
        raise WorkspaceError(f"workspace parent is not a directory: {resolved}")
    for protected in (
        capture.repository,
        capture.git_dir,
        capture.git_common_dir,
    ):
        if _is_within(resolved, protected):
            raise WorkspaceError(
                f"workspace parent overlaps protected source path: {resolved}"
            )
    return resolved


def _require_disjoint(root: Path, capture: CandidateCapture) -> None:
    protected = (
        capture.repository.resolve(strict=True),
        capture.git_dir.resolve(strict=True),
        capture.git_common_dir.resolve(strict=True),
    )
    for path in protected:
        if _is_within(root, path) or _is_within(path, root):
            raise WorkspaceError(
                f"workspace root overlaps protected source path: {path}"
            )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _clone(capture: CandidateCapture, destination: Path) -> None:
    try:
        _run(
            None,
            "-c",
            "protocol.file.allow=always",
            "clone",
            "--no-hardlinks",
            "--no-checkout",
            "--quiet",
            str(capture.repository),
            str(destination),
        )
        _run(destination, "checkout", "--detach", "--force", capture.base_commit)
    except subprocess.CalledProcessError as error:
        raise WorkspaceError("failed to clone and check out the base commit") from error


def _verify_base(capture: CandidateCapture, base: Path) -> None:
    try:
        actual = _run(base, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    except (subprocess.CalledProcessError, UnicodeDecodeError) as error:
        raise WorkspaceError("failed to verify the base workspace tree") from error
    if actual != capture.base_tree:
        raise WorkspaceError(
            f"base workspace tree mismatch: expected {capture.base_tree}, got {actual}"
        )


def _apply_candidate(capture: CandidateCapture, candidate: Path) -> None:
    try:
        if capture.patch:
            _run(
                candidate,
                "apply",
                "--binary",
                "--index",
                "--whitespace=nowarn",
                "-",
                input_bytes=capture.patch,
            )
        actual = _run(candidate, "write-tree").decode("ascii").strip()
    except (subprocess.CalledProcessError, UnicodeDecodeError) as error:
        raise WorkspaceError("candidate patch could not be applied safely") from error
    if actual != capture.candidate_tree:
        raise WorkspaceError(
            "candidate patch tree mismatch: "
            f"expected {capture.candidate_tree}, got {actual}"
        )


def _run(
    repository: Path | None,
    *arguments: str,
    input_bytes: bytes | None = None,
) -> bytes:
    command = [_git_binary()]
    if repository is not None:
        command.extend(("-C", str(repository)))
    command.extend(arguments)
    return subprocess.run(
        command,
        input=input_bytes,
        capture_output=True,
        env=_git_environment(),
        check=True,
    ).stdout


def _git_binary() -> str:
    binary = shutil.which("git")
    if binary is None:
        raise WorkspaceError("Git executable is unavailable")
    return binary


def _git_environment() -> dict[str, str]:
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
