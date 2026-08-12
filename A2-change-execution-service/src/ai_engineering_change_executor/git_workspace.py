"""
Isolated Git workspace and candidate-commit creation.

The workspace is a disposable clone checked out at the exact base commit from
TaskRunRequest. The supplied patch is checked for applicability before it is
applied.

The executor does not push, merge, or modify the source repository.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Iterable

from ai_engineering_contracts import TaskRunRequest

from .errors import (
    EmptyPatchError,
    PatchValidationError,
    RepositoryError,
    ScopeViolationError,
    WorkspaceMutationError,
)
from .models import GitIdentity
from .process import CommandResult, CommandRunner
from .tracing import ExecutionTraceRecorder


class GitWorkspace:
    """Manage one disposable repository clone."""

    def __init__(
        self,
        *,
        root: Path,
        git_executable: str,
        command_runner: CommandRunner,
        trace: ExecutionTraceRecorder,
    ) -> None:
        self._root = root
        self._repository_path = root / "repository"
        self._git = git_executable
        self._runner = command_runner
        self._trace = trace

    @property
    def repository_path(self) -> Path:
        return self._repository_path

    def initialize(
        self,
        *,
        repository_url: str,
        base_commit: str,
    ) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        clone = self._run_git(
            [
                "clone",
                "--no-checkout",
                "--filter=blob:none",
                repository_url,
                str(self._repository_path),
            ],
            cwd=self._root,
            purpose="clone repository",
            timeout_seconds=600,
        )
        self._require_success(clone, "Repository clone failed.")
        # Fetching the exact object after clone supports repositories whose
        # default clone does not include the requested historical commit.
        fetch = self._run_git(
            [
                "fetch",
                "--no-tags",
                "--force",
                "origin",
                base_commit,
            ],
            cwd=self._repository_path,
            purpose="fetch base commit",
            timeout_seconds=600,
        )
        self._require_success(fetch, "Unable to fetch the requested base commit.")
        checkout = self._run_git(
            [
                "checkout",
                "--detach",
                base_commit,
            ],
            cwd=self._repository_path,
            purpose="checkout base commit",
            timeout_seconds=300,
        )
        self._require_success(
            checkout,
            "Unable to check out the requested base commit.",
        )
        actual = self.current_commit()
        if actual.lower() != base_commit.lower():
            raise RepositoryError(
                f"Checked-out commit {actual} does not match requested "
                f"base commit {base_commit}."
            )
        self._trace.record(
            "workspace_initialized",
            "Repository workspace initialized at the requested base commit.",
            repository_path=str(self._repository_path),
            base_commit=actual,
        )

    def apply_patch(self, patch_path: Path) -> list[str]:
        """
        Validate, apply, and stage the supplied patch.

        Staging immediately after patch application gives Git a reliable view of
        modified, deleted, renamed, binary, and newly created files.
        """
        check = self._run_git(
            [
                "apply",
                "--check",
                "--whitespace=error-all",
                str(patch_path),
            ],
            cwd=self._repository_path,
            purpose="validate patch applicability",
            timeout_seconds=300,
        )
        if not check.succeeded:
            raise PatchValidationError(
                "The patch cannot be cleanly applied to the requested base commit. "
                f"Git reported: {self._diagnostic_message(check)}"
            )
        apply_result = self._run_git(
            [
                "apply",
                "--whitespace=error-all",
                str(patch_path),
            ],
            cwd=self._repository_path,
            purpose="apply patch",
            timeout_seconds=300,
        )
        if not apply_result.succeeded:
            raise PatchValidationError(
                "Patch validation succeeded, but patch application failed. "
                f"Git reported: {self._diagnostic_message(apply_result)}"
            )
        add = self._run_git(
            ["add", "--all"],
            cwd=self._repository_path,
            purpose="stage candidate changes",
            timeout_seconds=300,
        )
        self._require_success(add, "Unable to stage candidate changes.")
        staged_check = self._run_git(
            ["diff", "--cached", "--check"],
            cwd=self._repository_path,
            purpose="check staged patch integrity",
            timeout_seconds=300,
        )
        if not staged_check.succeeded:
            raise PatchValidationError(
                "The staged candidate contains conflict markers or whitespace "
                f"errors. Git reported: {self._diagnostic_message(staged_check)}"
            )
        changed_files = self.staged_changed_files()
        if not changed_files:
            raise EmptyPatchError(
                "The supplied patch produced no staged repository change."
            )
        self._trace.record(
            "patch_applied",
            "The supplied patch was applied and staged.",
            changed_files=changed_files,
        )
        return changed_files

    def validate_scope(
        self,
        *,
        changed_files: Iterable[str],
        task: TaskRunRequest,
    ) -> None:
        violations: list[str] = []
        for file_path in changed_files:
            normalized = file_path.replace("\\", "/")
            permitted = any(
                self._matches(normalized, pattern)
                for pattern in task.permitted_paths
            )
            prohibited = any(
                self._matches(normalized, pattern)
                for pattern in task.prohibited_paths
            )
            if not permitted or prohibited:
                violations.append(normalized)
        if violations:
            raise ScopeViolationError(
                "The candidate modifies paths outside the permitted scope: "
                + ", ".join(sorted(violations))
            )
        self._trace.record(
            "scope_validated",
            "All candidate paths are within the task's permitted scope.",
            changed_files=sorted(changed_files),
            permitted_paths=task.permitted_paths,
            prohibited_paths=task.prohibited_paths,
        )

    def assert_checks_did_not_mutate_staged_candidate(self) -> None:
        """
        Ensure checks did not modify tracked files after the candidate was staged.

        Generated ignored files such as caches or compiled outputs are tolerated.
        A check that rewrites a tracked source file is rejected because the staged
        candidate and checked working tree would no longer represent the same code.
        """
        result = self._run_git(
            ["diff", "--quiet"],
            cwd=self._repository_path,
            purpose="detect tracked workspace mutation by checks",
            timeout_seconds=120,
        )
        if result.exit_code == 0:
            return
        if result.exit_code == 1:
            details = self._run_git(
                ["diff", "--name-only"],
                cwd=self._repository_path,
                purpose="list files modified by checks",
                timeout_seconds=120,
            )
            raise WorkspaceMutationError(
                "A local check modified tracked files after the candidate patch "
                f"was staged: {details.stdout.strip() or 'unknown files'}."
            )
        raise RepositoryError(
            "Unable to determine whether local checks mutated tracked files. "
            f"Git reported: {self._diagnostic_message(result)}"
        )

    def create_candidate_commit(
        self,
        *,
        message: str,
        identity: GitIdentity,
    ) -> str:
        commit = self._run_git(
            [
                "-c",
                f"user.name={identity.name}",
                "-c",
                f"user.email={identity.email}",
                "commit",
                "--no-gpg-sign",
                "--no-verify",
                "-m",
                message,
            ],
            cwd=self._repository_path,
            purpose="create local candidate commit",
            timeout_seconds=300,
        )
        self._require_success(commit, "Unable to create the candidate commit.")
        candidate_commit = self.current_commit()
        self._trace.record(
            "candidate_commit_created",
            "A local immutable candidate commit was created.",
            candidate_commit=candidate_commit,
        )
        return candidate_commit

    def export_candidate_patch(
        self,
        *,
        base_commit: str,
        candidate_commit: str,
    ) -> bytes:
        result = self._run_git(
            [
                "diff",
                "--binary",
                "--full-index",
                base_commit,
                candidate_commit,
            ],
            cwd=self._repository_path,
            purpose="export normalized candidate patch",
            timeout_seconds=300,
        )
        self._require_success(result, "Unable to export the candidate patch.")
        content = result.stdout.encode("utf-8")
        if not content:
            raise EmptyPatchError(
                "Candidate commit was created, but the normalized patch is empty."
            )
        return content

    def staged_changed_files(self) -> list[str]:
        result = self._run_git(
            [
                "diff",
                "--cached",
                "--name-only",
                "-z",
            ],
            cwd=self._repository_path,
            purpose="list staged changed files",
            timeout_seconds=120,
        )
        self._require_success(result, "Unable to list staged changed files.")
        return sorted(
            item
            for item in result.stdout.split("\0")
            if item
        )

    def current_commit(self) -> str:
        result = self._run_git(
            ["rev-parse", "HEAD"],
            cwd=self._repository_path,
            purpose="resolve current commit",
            timeout_seconds=120,
        )
        self._require_success(result, "Unable to resolve the current commit.")
        return result.stdout.strip()

    def _run_git(
        self,
        git_arguments: list[str],
        *,
        cwd: Path,
        purpose: str,
        timeout_seconds: float,
    ) -> CommandResult:
        result = self._runner.run(
            [self._git, *git_arguments],
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        self._trace.record_command(purpose=purpose, result=result)
        return result

    @staticmethod
    def _matches(file_path: str, pattern: str) -> bool:
        """
        Match a repository path against a task-scope pattern.

        PurePosixPath.match supports common Git-style patterns including ``*``
        and ``**``. A direct equality check ensures literal root-level files are
        handled predictably.
        """
        normalized_pattern = pattern.replace("\\", "/")
        return (
            file_path == normalized_pattern
            or PurePosixPath(file_path).match(normalized_pattern)
        )

    @staticmethod
    def _diagnostic_message(result: CommandResult) -> str:
        return (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit code {result.exit_code}"
        )

    @classmethod
    def _require_success(
        cls,
        result: CommandResult,
        message: str,
    ) -> None:
        if not result.succeeded:
            raise RepositoryError(
                f"{message} {cls._diagnostic_message(result)}"
            )
