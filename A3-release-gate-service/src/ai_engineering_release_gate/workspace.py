"""
Clean-room candidate reconstruction.

The gate clones the exact base commit and applies the immutable normalized patch
from Component 2. The executor workspace and executor-local check results are
not reused.

After patch application, the gate stages the candidate and records its Git tree
identifier. Deterministic controls may create ignored build output, but they may
not alter tracked candidate source or the staged tree.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Iterable

from .errors import (
    PatchValidationError,
    RepositoryError,
    ScopeViolationError,
    WorkspaceContaminationError,
)
from .process import CommandResult, CommandRunner
from .tracing import GateTraceRecorder


class GateWorkspace:
    """Manage one clean repository clone for authoritative assurance."""

    def __init__(
        self,
        *,
        root: Path,
        git_executable: str,
        command_runner: CommandRunner,
        trace: GateTraceRecorder,
    ) -> None:
        self._root = root
        self._repository_path = root / "repository"
        self._git = git_executable
        self._runner = command_runner
        self._trace = trace
        self._candidate_tree: str | None = None

    @property
    def repository_path(self) -> Path:
        return self._repository_path

    @property
    def candidate_tree(self) -> str:
        if self._candidate_tree is None:
            raise RepositoryError(
                "Candidate tree is unavailable before patch reconstruction."
            )
        return self._candidate_tree

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
        self._require_success(
            fetch,
            "Unable to fetch the requested base commit.",
        )
        checkout = self._run_git(
            ["checkout", "--detach", base_commit],
            cwd=self._repository_path,
            purpose="checkout base commit",
            timeout_seconds=300,
        )
        self._require_success(
            checkout,
            "Unable to check out the requested base commit.",
        )
        actual = self._git_output(["rev-parse", "HEAD"], "resolve base commit")
        if actual.lower() != base_commit.lower():
            raise RepositoryError(
                f"Checked-out commit {actual} does not match {base_commit}."
            )
        self._trace.record(
            "workspace_initialized",
            "Clean gate workspace initialized.",
            base_commit=actual,
            repository_path=str(self._repository_path),
        )

    def reconstruct_candidate(self, patch_path: Path) -> list[str]:
        check = self._run_git(
            [
                "apply",
                "--check",
                "--whitespace=error-all",
                str(patch_path),
            ],
            cwd=self._repository_path,
            purpose="validate candidate patch",
            timeout_seconds=300,
        )
        if not check.succeeded:
            raise PatchValidationError(
                "Candidate patch cannot be applied to the requested base commit. "
                f"Git reported: {self._diagnostic(check)}"
            )
        apply_result = self._run_git(
            [
                "apply",
                "--whitespace=error-all",
                str(patch_path),
            ],
            cwd=self._repository_path,
            purpose="apply candidate patch",
            timeout_seconds=300,
        )
        if not apply_result.succeeded:
            raise PatchValidationError(
                "Candidate patch validation succeeded, but application failed. "
                f"Git reported: {self._diagnostic(apply_result)}"
            )
        add = self._run_git(
            ["add", "--all"],
            cwd=self._repository_path,
            purpose="stage reconstructed candidate",
            timeout_seconds=300,
        )
        self._require_success(add, "Unable to stage reconstructed candidate.")
        diff_check = self._run_git(
            ["diff", "--cached", "--check"],
            cwd=self._repository_path,
            purpose="validate reconstructed candidate diff",
            timeout_seconds=300,
        )
        if not diff_check.succeeded:
            raise PatchValidationError(
                "Candidate contains conflict markers or whitespace errors. "
                f"Git reported: {self._diagnostic(diff_check)}"
            )
        changed_files = self.changed_files()
        if not changed_files:
            raise PatchValidationError(
                "Candidate patch produced no staged code change."
            )
        self._candidate_tree = self._git_output(
            ["write-tree"],
            "calculate candidate tree",
        )
        self._trace.record(
            "candidate_reconstructed",
            "Candidate was reconstructed in a clean workspace.",
            changed_files=changed_files,
            candidate_tree=self._candidate_tree,
        )
        return changed_files

    def validate_scope(
        self,
        *,
        changed_files: Iterable[str],
        permitted_paths: list[str],
        prohibited_paths: list[str],
    ) -> None:
        violations: list[str] = []
        for changed_file in changed_files:
            normalized = changed_file.replace("\\", "/")
            permitted = any(
                self._matches(normalized, pattern)
                for pattern in permitted_paths
            )
            prohibited = any(
                self._matches(normalized, pattern)
                for pattern in prohibited_paths
            )
            if not permitted or prohibited:
                violations.append(normalized)
        if violations:
            raise ScopeViolationError(
                "Candidate contains unauthorized path changes: "
                + ", ".join(sorted(violations))
            )
        self._trace.record(
            "scope_validated",
            "Candidate path scope passed authoritative validation.",
            changed_files=sorted(changed_files),
            permitted_paths=permitted_paths,
            prohibited_paths=prohibited_paths,
        )

    def assert_candidate_not_contaminated(self) -> None:
        """
        Verify that a control did not alter tracked source or the staged tree.

        Ignored coverage data, caches, and build output are permitted. Tracked
        source modifications are not.
        """
        working_tree = self._run_git(
            ["diff", "--quiet"],
            cwd=self._repository_path,
            purpose="detect tracked working-tree mutation",
            timeout_seconds=120,
        )
        if working_tree.exit_code == 1:
            modified = self._git_output(
                ["diff", "--name-only"],
                "list control-modified tracked files",
            )
            raise WorkspaceContaminationError(
                "A gate control modified tracked candidate files: "
                f"{modified or 'unknown files'}."
            )
        if working_tree.exit_code not in {0, 1}:
            raise RepositoryError(
                "Unable to verify working-tree integrity. "
                f"Git reported: {self._diagnostic(working_tree)}"
            )
        current_tree = self._git_output(
            ["write-tree"],
            "recalculate candidate tree",
        )
        if current_tree != self.candidate_tree:
            raise WorkspaceContaminationError(
                "A gate control modified the staged candidate tree."
            )

    def changed_files(self) -> list[str]:
        output = self._git_output(
            ["diff", "--cached", "--name-only", "-z"],
            "list reconstructed candidate files",
        )
        return sorted(item for item in output.split("\0") if item)

    def _git_output(self, arguments: list[str], purpose: str) -> str:
        result = self._run_git(
            arguments,
            cwd=self._repository_path,
            purpose=purpose,
            timeout_seconds=120,
        )
        self._require_success(result, f"Unable to {purpose}.")
        return result.stdout.strip()

    def _run_git(
        self,
        arguments: list[str],
        *,
        cwd: Path,
        purpose: str,
        timeout_seconds: float,
    ) -> CommandResult:
        result = self._runner.run(
            [self._git, *arguments],
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        self._trace.record_command(purpose=purpose, result=result)
        return result

    @staticmethod
    def _matches(file_path: str, pattern: str) -> bool:
        normalized_pattern = pattern.replace("\\", "/")
        return (
            file_path == normalized_pattern
            or PurePosixPath(file_path).match(normalized_pattern)
        )

    @staticmethod
    def _diagnostic(result: CommandResult) -> str:
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
            raise RepositoryError(f"{message} {cls._diagnostic(result)}")
