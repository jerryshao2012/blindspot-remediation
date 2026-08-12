"""
Public ChangeExecutionService façade.

The implementation performs the following deterministic workflow:

    validate request
        ↓
    verify patch integrity
        ↓
    create disposable repository clone
        ↓
    check and apply patch
        ↓
    stage changes and validate path scope
        ↓
    run configured local checks
        ↓
    ensure checks did not mutate tracked source
        ↓
    create local candidate commit
        ↓
    export normalized candidate patch
        ↓
    store immutable artifacts
        ↓
    return ExecutionResult

A failed local check does not prevent a candidate from being produced. Local
checks are executor feedback rather than release authority. The release gate
will decide how failed checks affect release eligibility.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ai_engineering_contracts import (
    ArtifactKind,
    CheckResult,
    CheckStatus,
    ExecutionResult,
    ExecutionStatus,
    TokenUsage,
)

from .artifacts import LocalArtifactLoader, LocalArtifactStore
from .errors import (
    ChangeExecutorError,
    ExecutionBudgetExceeded,
)
from .git_workspace import GitWorkspace
from .models import (
    ExecutorSettings,
    LocalCheckSpec,
    ManualPatchExecutionRequest,
)
from .process import CommandRunner, ExecutionBudgetTracker
from .tracing import ExecutionTraceRecorder


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChangeExecutionService:
    """
    Produce an immutable candidate patch from a manually authored patch.

    Responsibilities
    ----------------
    * Validate and load the input patch.
    * Prepare an isolated repository workspace.
    * Enforce the requested file scope.
    * Run bounded local checks.
    * Create a local candidate commit.
    * Record immutable execution artifacts and provenance.

    Explicit non-responsibilities
    -----------------------------
    * Generate code with an LLM.
    * Assert that local checks are authoritative release evidence.
    * Read hidden benchmark oracles.
    * Issue a release decision.
    * Push, merge, deploy, or modify the remote repository.
    """

    EXECUTOR_VERSION = "0.1.0"

    def __init__(
        self,
        *,
        settings: ExecutorSettings,
        artifact_loader: LocalArtifactLoader | None = None,
        artifact_store: LocalArtifactStore | None = None,
    ) -> None:
        self._settings = settings
        self._artifact_loader = artifact_loader or LocalArtifactLoader()
        self._artifact_store = artifact_store or LocalArtifactStore(
            settings.artifact_root
        )

    async def execute(
        self,
        request: ManualPatchExecutionRequest,
    ) -> ExecutionResult:
        """
        Execute one deterministic patch application.

        The method is asynchronous to preserve the public interface expected by
        later Azure and LLM-enabled implementations. The current subprocess work
        is synchronous because one Container Apps Job handles one bounded task.
        """
        started_at = utc_now()
        trace = ExecutionTraceRecorder(request.task.run_id)
        trace.record(
            "execution_started",
            "Deterministic manual-patch execution started.",
            executor_version=self.EXECUTOR_VERSION,
            task_type=request.task.task_type,
            task_package_version=request.task.task_package_version,
            base_commit=request.task.base_commit,
        )
        candidate_commit: str | None = None
        changed_files: list[str] = []
        local_check_results: list[CheckResult] = []
        budget = ExecutionBudgetTracker(
            maximum_tool_calls=request.task.execution_budget.maximum_tool_calls,
            maximum_runtime_seconds=(
                request.task.execution_budget.maximum_runtime_seconds
            ),
        )
        runner = CommandRunner(
            budget=budget,
            maximum_captured_output_bytes=(
                self._settings.maximum_captured_output_bytes
            ),
        )
        try:
            patch_bytes = self._artifact_loader.read_bytes(
                request.patch_artifact
            )
            trace.record(
                "patch_loaded",
                "The input patch was loaded and its SHA-256 digest was verified.",
                patch_artifact_id=request.patch_artifact.artifact_id,
                patch_size_bytes=len(patch_bytes),
                patch_sha256=request.patch_artifact.sha256,
            )
            with tempfile.TemporaryDirectory(
                prefix=f"change-executor-{request.task.run_id}-"
            ) as temporary_directory:
                workspace_root = Path(temporary_directory)
                input_patch_path = workspace_root / "input.patch"
                input_patch_path.write_bytes(patch_bytes)
                workspace = GitWorkspace(
                    root=workspace_root / "workspace",
                    git_executable=self._settings.git_executable,
                    command_runner=runner,
                    trace=trace,
                )
                workspace.initialize(
                    repository_url=request.task.repository_url,
                    base_commit=request.task.base_commit,
                )
                changed_files = workspace.apply_patch(input_patch_path)
                workspace.validate_scope(
                    changed_files=changed_files,
                    task=request.task,
                )
                check_specs = self._combine_checks(
                    configured=self._settings.local_checks,
                    additional=request.additional_checks,
                )
                local_check_results = self._run_local_checks(
                    checks=check_specs,
                    repository_path=workspace.repository_path,
                    runner=runner,
                    trace=trace,
                )
                workspace.assert_checks_did_not_mutate_staged_candidate()
                candidate_commit = workspace.create_candidate_commit(
                    message=request.commit_message,
                    identity=self._settings.git_identity,
                )
                normalized_patch = workspace.export_candidate_patch(
                    base_commit=request.task.base_commit,
                    candidate_commit=candidate_commit,
                )
                patch_artifact = self._artifact_store.store_bytes(
                    run_id=request.task.run_id,
                    filename="candidate.patch",
                    kind=ArtifactKind.PATCH,
                    media_type="text/x-diff",
                    content=normalized_patch,
                    metadata={
                        "base_commit": request.task.base_commit,
                        "candidate_commit": candidate_commit,
                        "executor_version": self.EXECUTOR_VERSION,
                    },
                )
                trace.record(
                    "execution_completed",
                    "The deterministic executor produced a candidate commit.",
                    candidate_commit=candidate_commit,
                    changed_files=changed_files,
                    local_check_summary=self._summarize_checks(
                        local_check_results
                    ),
                    deterministic_tool_calls=budget.tool_calls,
                )
                trace_artifact = self._store_trace(
                    run_id=request.task.run_id,
                    trace=trace,
                )
                return ExecutionResult(
                    run_id=request.task.run_id,
                    executor_version=self.EXECUTOR_VERSION,
                    status=ExecutionStatus.COMPLETED,
                    base_commit=request.task.base_commit,
                    candidate_commit=candidate_commit,
                    patch_artifact=patch_artifact,
                    changed_files=changed_files,
                    local_check_results=local_check_results,
                    model_configuration=None,
                    token_usage=TokenUsage(),
                    tool_usage=[],
                    execution_trace=trace_artifact,
                    started_at=started_at,
                    completed_at=utc_now(),
                    metadata={
                        "execution_mode": "deterministic_manual_patch",
                        "deterministic_tool_calls": str(budget.tool_calls),
                    },
                )
        except ExecutionBudgetExceeded as exc:
            trace.record(
                "execution_budget_exhausted",
                str(exc),
                deterministic_tool_calls=budget.tool_calls,
            )
            trace_artifact = self._store_trace(
                run_id=request.task.run_id,
                trace=trace,
            )
            return ExecutionResult(
                run_id=request.task.run_id,
                executor_version=self.EXECUTOR_VERSION,
                status=ExecutionStatus.BUDGET_EXHAUSTED,
                base_commit=request.task.base_commit,
                candidate_commit=None,
                patch_artifact=None,
                changed_files=changed_files,
                local_check_results=local_check_results,
                model_configuration=None,
                token_usage=TokenUsage(),
                tool_usage=[],
                execution_trace=trace_artifact,
                started_at=started_at,
                completed_at=utc_now(),
                incomplete_reason=str(exc),
                metadata={
                    "execution_mode": "deterministic_manual_patch",
                    "deterministic_tool_calls": str(budget.tool_calls),
                },
            )
        except ChangeExecutorError as exc:
            trace.record(
                "execution_failed",
                str(exc),
                exception_type=type(exc).__name__,
                deterministic_tool_calls=budget.tool_calls,
            )
            trace_artifact = self._store_trace(
                run_id=request.task.run_id,
                trace=trace,
            )
            return ExecutionResult(
                run_id=request.task.run_id,
                executor_version=self.EXECUTOR_VERSION,
                status=ExecutionStatus.FAILED,
                base_commit=request.task.base_commit,
                candidate_commit=None,
                patch_artifact=None,
                changed_files=changed_files,
                local_check_results=local_check_results,
                model_configuration=None,
                token_usage=TokenUsage(),
                tool_usage=[],
                execution_trace=trace_artifact,
                started_at=started_at,
                completed_at=utc_now(),
                failure_reason=f"{type(exc).__name__}: {exc}",
                metadata={
                    "execution_mode": "deterministic_manual_patch",
                    "deterministic_tool_calls": str(budget.tool_calls),
                },
            )
        except Exception as exc:
            # Unexpected exceptions are converted into an explicit failed result
            # so an Azure job can always emit a machine-readable outcome. The full
            # exception type and redacted message are retained in the trace.
            trace.record(
                "unexpected_execution_failure",
                str(exc),
                exception_type=type(exc).__name__,
                deterministic_tool_calls=budget.tool_calls,
            )
            trace_artifact = self._store_trace(
                run_id=request.task.run_id,
                trace=trace,
            )
            return ExecutionResult(
                run_id=request.task.run_id,
                executor_version=self.EXECUTOR_VERSION,
                status=ExecutionStatus.FAILED,
                base_commit=request.task.base_commit,
                candidate_commit=None,
                patch_artifact=None,
                changed_files=changed_files,
                local_check_results=local_check_results,
                model_configuration=None,
                token_usage=TokenUsage(),
                tool_usage=[],
                execution_trace=trace_artifact,
                started_at=started_at,
                completed_at=utc_now(),
                failure_reason=(
                    f"Unexpected {type(exc).__name__}: {exc}"
                ),
                metadata={
                    "execution_mode": "deterministic_manual_patch",
                    "deterministic_tool_calls": str(budget.tool_calls),
                },
            )

    def _run_local_checks(
        self,
        *,
        checks: list[LocalCheckSpec],
        repository_path: Path,
        runner: CommandRunner,
        trace: ExecutionTraceRecorder,
    ) -> list[CheckResult]:
        results: list[CheckResult] = []
        for check in checks:
            started_at = utc_now()
            working_directory = (
                repository_path / check.working_directory
            ).resolve()
            try:
                working_directory.relative_to(repository_path.resolve())
            except ValueError as exc:
                raise ValueError(
                    f"Check {check.check_id!r} resolves outside the repository."
                ) from exc
            if not working_directory.exists():
                result = CheckResult(
                    check_id=check.check_id,
                    name=check.name,
                    status=CheckStatus.ERROR,
                    started_at=started_at,
                    completed_at=utc_now(),
                    command_name=check.command[0],
                    exit_code=None,
                    summary=(
                        f"Configured working directory does not exist: "
                        f"{check.working_directory}"
                    ),
                    metrics={
                        "required": 1.0 if check.required else 0.0,
                    },
                )
                results.append(result)
                trace.record(
                    "local_check_error",
                    result.summary,
                    check_id=check.check_id,
                )
                continue
            command_result = runner.run(
                check.command,
                cwd=working_directory,
                timeout_seconds=check.timeout_seconds,
                extra_environment=check.environment,
            )
            trace.record_command(
                purpose=f"local check {check.check_id}",
                result=command_result,
            )
            status = (
                CheckStatus.PASSED
                if command_result.succeeded
                else CheckStatus.FAILED
            )
            summary = self._build_check_summary(
                check=check,
                exit_code=command_result.exit_code,
                stdout=command_result.stdout,
                stderr=command_result.stderr,
            )
            results.append(
                CheckResult(
                    check_id=check.check_id,
                    name=check.name,
                    status=status,
                    started_at=started_at,
                    completed_at=utc_now(),
                    command_name=check.command[0],
                    exit_code=command_result.exit_code,
                    summary=summary,
                    metrics={
                        "duration_seconds": command_result.duration_seconds,
                        "required": 1.0 if check.required else 0.0,
                        "output_truncated": (
                            1.0 if command_result.output_truncated else 0.0
                        ),
                    },
                    is_authoritative_release_evidence=False,
                )
            )
        return results

    def _store_trace(
        self,
        *,
        run_id: str,
        trace: ExecutionTraceRecorder,
    ):
        return self._artifact_store.store_json(
            run_id=run_id,
            filename="execution-trace.json",
            kind=ArtifactKind.EXECUTION_TRACE,
            payload=trace.to_payload(),
            metadata={
                "executor_version": self.EXECUTOR_VERSION,
                "execution_mode": "deterministic_manual_patch",
            },
        )

    @staticmethod
    def _combine_checks(
        *,
        configured: list[LocalCheckSpec],
        additional: list[LocalCheckSpec],
    ) -> list[LocalCheckSpec]:
        combined = [*configured, *additional]
        identifiers = [item.check_id for item in combined]
        if len(identifiers) != len(set(identifiers)):
            duplicates = sorted(
                {
                    item
                    for item in identifiers
                    if identifiers.count(item) > 1
                }
            )
            raise ValueError(
                "Configured and request-specific checks contain duplicate IDs: "
                + ", ".join(duplicates)
            )
        return combined

    @staticmethod
    def _build_check_summary(
        *,
        check: LocalCheckSpec,
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> str:
        diagnostic = stderr.strip() or stdout.strip()
        if len(diagnostic) > 3_000:
            diagnostic = diagnostic[:3_000] + "\n...[summary truncated]"
        if exit_code == 0:
            base = f"Local check {check.check_id!r} passed."
        else:
            base = (
                f"Local check {check.check_id!r} failed with exit code "
                f"{exit_code}."
            )
        return f"{base}\n{diagnostic}" if diagnostic else base

    @staticmethod
    def _summarize_checks(
        checks: list[CheckResult],
    ) -> dict[str, int]:
        summary = {
            "passed": 0,
            "failed": 0,
            "warning": 0,
            "skipped": 0,
            "error": 0,
            "not_applicable": 0,
        }
        for result in checks:
            summary[result.status.value] += 1
        return summary
