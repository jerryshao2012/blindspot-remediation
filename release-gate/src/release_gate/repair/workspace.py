"""Isolated repair workspace management and candidate patch export."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pathspec import PathSpec

from release_gate.git import (
    _base_git_environment,
    _git_binary,
    _parse_name_status,
    capture_candidate,
)
from release_gate.models import Scope
from release_gate.repair.models import FinalApproval, RepairAttempt, sha256_bytes


class RepairWorkspaceError(RuntimeError):
    """Failure occurred in repair workspace lifecycle or boundary validation."""


@dataclass(frozen=True, slots=True)
class ExportedCandidate:
    """A verified candidate state extracted from the repair workspace."""

    candidate_tree: str
    patch: bytes
    patch_sha256: str
    changed_paths: tuple[str, ...]


def compute_approved_paths(
    changed_paths: Sequence[str],
    scope: Scope | None,
    extra_paths: Sequence[str] = (),
) -> tuple[str, ...]:
    """Compute strictly allowed edit paths for the repair worker."""

    candidates = list(dict.fromkeys((*changed_paths, *extra_paths)))
    if scope is None:
        return tuple(candidates)

    allowed_spec = PathSpec.from_lines("gitwildmatch", scope.allowed_paths)
    forbidden_spec = PathSpec.from_lines("gitwildmatch", scope.forbidden_paths)
    review_spec = PathSpec.from_lines("gitwildmatch", scope.review_required_paths)

    approved: list[str] = []
    for path in candidates:
        if not allowed_spec.match_file(path):
            continue
        if forbidden_spec.match_file(path):
            continue
        if review_spec.match_file(path):
            continue
        approved.append(path)

    return tuple(approved)


class RepairWorkspace:
    """Disposable clone workspace for making and testing repair attempts."""

    def __init__(
        self,
        repository_path: Path,
        base_commit: str,
        base_tree: str,
        approved_paths: tuple[str, ...],
        temp_root: Path,
        workspace_path: Path,
    ) -> None:
        self.repository_path = repository_path
        self.base_commit = base_commit
        self.base_tree = base_tree
        self.approved_paths = approved_paths
        self.temp_root = temp_root
        self.workspace_path = workspace_path
        self.seen_trees: set[str] = set()
        self.seen_patches: set[str] = set()

    @classmethod
    def create(
        cls,
        repository_path: Path,
        *,
        base_commit: str,
        initial_patch: bytes,
        approved_paths: Sequence[str],
        parent: Path | None = None,
    ) -> RepairWorkspace:
        git_bin = _git_binary()
        temp_dir = Path(
            tempfile.mkdtemp(prefix="release-gate-repair-ws-", dir=parent)
        ).resolve(strict=True)
        ws_path = temp_dir / "worktree"
        env = _base_git_environment()

        try:
            # Clone cleanly without hardlinks or checking out yet
            subprocess.run(
                [
                    git_bin,
                    "-c",
                    "protocol.file.allow=always",
                    "clone",
                    "--no-hardlinks",
                    "--no-checkout",
                    "--quiet",
                    str(repository_path),
                    str(ws_path),
                ],
                check=True,
                env=env,
                capture_output=True,
            )
            # Detach checkout to base commit
            subprocess.run(
                [
                    git_bin,
                    "-C",
                    str(ws_path),
                    "checkout",
                    "--detach",
                    "--force",
                    base_commit,
                ],
                check=True,
                env=env,
                capture_output=True,
            )
            base_tree = (
                subprocess.run(
                    [
                        git_bin,
                        "-C",
                        str(ws_path),
                        "rev-parse",
                        f"{base_commit}^{{tree}}",
                    ],
                    check=True,
                    env=env,
                    capture_output=True,
                )
                .stdout.decode("ascii")
                .strip()
            )

            # Apply candidate C0 patch
            subprocess.run(
                [
                    git_bin,
                    "-C",
                    str(ws_path),
                    "apply",
                    "--binary",
                    "--index",
                    "--whitespace=nowarn",
                    "-",
                ],
                input=initial_patch,
                check=True,
                env=env,
                capture_output=True,
            )

            # Write-tree for C0
            c0_tree = (
                subprocess.run(
                    [git_bin, "-C", str(ws_path), "write-tree"],
                    check=True,
                    env=env,
                    capture_output=True,
                )
                .stdout.decode("ascii")
                .strip()
            )
            c0_patch_digest = sha256_bytes(initial_patch)

            instance = cls(
                repository_path=repository_path,
                base_commit=base_commit,
                base_tree=base_tree,
                approved_paths=tuple(approved_paths),
                temp_root=temp_dir,
                workspace_path=ws_path,
            )
            instance.record_attempt(c0_tree, c0_patch_digest)
            return instance

        except Exception as error:
            shutil.rmtree(temp_dir, ignore_errors=True)
            if isinstance(error, RepairWorkspaceError):
                raise
            raise RepairWorkspaceError(
                f"failed to initialize repair workspace: {error}"
            ) from error

    def record_attempt(self, candidate_tree: str, patch_sha256: str) -> None:
        self.seen_trees.add(candidate_tree)
        self.seen_patches.add(patch_sha256)

    def export_candidate(self) -> ExportedCandidate:
        git_bin = _git_binary()
        env = _base_git_environment()

        try:
            # Stage all changes in the workspace
            subprocess.run(
                [git_bin, "-C", str(self.workspace_path), "add", "-A", "--", "."],
                check=True,
                env=env,
                capture_output=True,
            )
            candidate_tree = (
                subprocess.run(
                    [git_bin, "-C", str(self.workspace_path), "write-tree"],
                    check=True,
                    env=env,
                    capture_output=True,
                )
                .stdout.decode("ascii")
                .strip()
            )

            if candidate_tree in self.seen_trees:
                raise RepairWorkspaceError(
                    "candidate tree is unchanged or repeated from a prior attempt"
                )

            patch = subprocess.run(
                [
                    git_bin,
                    "-C",
                    str(self.workspace_path),
                    "diff-tree",
                    "--no-commit-id",
                    "--binary",
                    "--full-index",
                    "--no-color",
                    "--no-ext-diff",
                    "--find-renames",
                    "-r",
                    "-p",
                    self.base_tree,
                    candidate_tree,
                ],
                check=True,
                env=env,
                capture_output=True,
            ).stdout

            patch_sha256 = sha256_bytes(patch)
            if patch_sha256 in self.seen_patches:
                raise RepairWorkspaceError(
                    "candidate patch digest is repeated from a prior attempt"
                )

            names_raw = subprocess.run(
                [
                    git_bin,
                    "-C",
                    str(self.workspace_path),
                    "diff-tree",
                    "--no-commit-id",
                    "--name-status",
                    "--find-renames",
                    "-r",
                    "-z",
                    self.base_tree,
                    candidate_tree,
                ],
                check=True,
                env=env,
                capture_output=True,
            ).stdout

            changed_paths = _parse_name_status(names_raw)

            # Enforce path boundaries
            approved_set = set(self.approved_paths)
            unapproved = [p for p in changed_paths if p not in approved_set]
            if unapproved:
                raise RepairWorkspaceError(
                    f"edits outside approved paths detected: {', '.join(unapproved)}"
                )

            return ExportedCandidate(
                candidate_tree=candidate_tree,
                patch=patch,
                patch_sha256=patch_sha256,
                changed_paths=changed_paths,
            )

        except subprocess.CalledProcessError as error:
            raise RepairWorkspaceError(
                f"failed to export candidate from workspace: {error}"
            ) from error

    def cleanup(self) -> None:
        if self.temp_root.exists():
            shutil.rmtree(self.temp_root, ignore_errors=True)


def apply_candidate_to_source(
    repo_path: Path,
    *,
    base_commit: str,
    c0_attempt: RepairAttempt,
    passing_attempt: RepairAttempt,
    original_patch: bytes,
    final_patch: bytes,
    final_approval: FinalApproval,
) -> None:
    """Apply passing candidate patch safely to the source repository."""

    if final_approval.final_candidate_tree != passing_attempt.candidate_tree:
        raise RepairWorkspaceError("approval candidate tree mismatch")
    if final_approval.final_patch_digest != passing_attempt.patch_digest:
        raise RepairWorkspaceError("approval patch digest mismatch")
    if sha256_bytes(final_patch) != passing_attempt.patch_digest:
        raise RepairWorkspaceError("passing patch digest mismatch")

    # 1. Recapture source candidate to ensure worktree unchanged from C0
    try:
        current_capture = capture_candidate(repo_path, base=base_commit)
    except Exception as error:
        raise RepairWorkspaceError(
            f"source_changed: failed to recapture source worktree: {error}"
        ) from error

    if (
        current_capture.candidate_tree != c0_attempt.candidate_tree
        or current_capture.patch_sha256 != c0_attempt.patch_digest
    ):
        raise RepairWorkspaceError(
            "source_changed: source worktree has changed since repair started"
        )

    # Apply only working-tree patches: the developer's real index remains untouched.
    git_bin = _git_binary()
    env = _base_git_environment()
    reverted_original = False
    applied_final = False

    try:
        subprocess.run(
            [
                git_bin,
                "-C",
                str(repo_path),
                "apply",
                "--reverse",
                "--whitespace=nowarn",
                "-",
            ],
            input=original_patch,
            check=True,
            env=env,
            capture_output=True,
        )
        reverted_original = True
        if final_patch:
            subprocess.run(
                [
                    git_bin,
                    "-C",
                    str(repo_path),
                    "apply",
                    "--whitespace=nowarn",
                    "-",
                ],
                input=final_patch,
                check=True,
                env=env,
                capture_output=True,
            )
            applied_final = True

        # Recapture and verify post-apply tree matches passing candidate
        post_capture = capture_candidate(repo_path, base=base_commit, allow_empty=True)
        if (
            post_capture.candidate_tree != passing_attempt.candidate_tree
            or post_capture.patch_sha256 != passing_attempt.patch_digest
        ):
            raise RepairWorkspaceError(
                "rollback_failed: post-apply candidate tree mismatch"
            )

    except Exception as error:
        try:
            if applied_final:
                subprocess.run(
                    [
                        git_bin,
                        "-C",
                        str(repo_path),
                        "apply",
                        "--reverse",
                        "--whitespace=nowarn",
                        "-",
                    ],
                    input=final_patch,
                    check=True,
                    env=env,
                    capture_output=True,
                )
            if reverted_original:
                subprocess.run(
                    [
                        git_bin,
                        "-C",
                        str(repo_path),
                        "apply",
                        "--whitespace=nowarn",
                        "-",
                    ],
                    input=original_patch,
                    check=True,
                    env=env,
                    capture_output=True,
                )
        except subprocess.CalledProcessError as rollback_error:
            raise RepairWorkspaceError(
                "rollback_failed: unable to restore source candidate"
            ) from rollback_error
        if isinstance(error, RepairWorkspaceError):
            raise
        raise RepairWorkspaceError(
            f"failed to apply candidate to source: {error}"
        ) from error
