"""
Safe external-command execution.

The executor uses the installed Git executable and configured build/test tools.
Commands are always passed as argument arrays with ``shell=False``.

The process environment is allow-listed to reduce accidental secret leakage.
This is a POC safety measure, not a complete operating-system sandbox. The
production Azure deployment should additionally use container isolation,
managed identity, egress restrictions, resource limits, and a non-root user.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Mapping, Sequence

from .errors import (
    CommandExecutionError,
    CommandTimeoutError,
    ExecutionBudgetExceeded,
)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Normalized result from one external process."""

    arguments: tuple[str, ...]
    cwd: Path
    exit_code: int
    stdout: str
    stderr: str
    started_monotonic: float
    completed_monotonic: float
    output_truncated: bool

    @property
    def duration_seconds(self) -> float:
        return self.completed_monotonic - self.started_monotonic

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0

    def output_fingerprint(self) -> str:
        """Fingerprint stdout, stderr, and exit code without storing raw bytes."""
        digest = hashlib.sha256()
        digest.update(str(self.exit_code).encode("utf-8"))
        digest.update(b"\0")
        digest.update(self.stdout.encode("utf-8", errors="replace"))
        digest.update(b"\0")
        digest.update(self.stderr.encode("utf-8", errors="replace"))
        return digest.hexdigest()


class ExecutionBudgetTracker:
    """
    Tracks deterministic tool calls and wall-clock runtime.

    LLM and token budgets are not consumed by this component because the initial
    executor is deliberately non-AI.
    """

    def __init__(
        self,
        *,
        maximum_tool_calls: int,
        maximum_runtime_seconds: int,
    ) -> None:
        self._maximum_tool_calls = maximum_tool_calls
        self._deadline = time.monotonic() + maximum_runtime_seconds
        self._tool_calls = 0
        self._lock = Lock()

    @property
    def tool_calls(self) -> int:
        return self._tool_calls

    def remaining_seconds(self) -> float:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise ExecutionBudgetExceeded(
                "The deterministic execution runtime budget was exhausted."
            )
        return remaining

    def reserve_tool_call(self) -> None:
        with self._lock:
            if self._tool_calls >= self._maximum_tool_calls:
                raise ExecutionBudgetExceeded(
                    "The deterministic tool-call budget was exhausted."
                )
            self._tool_calls += 1


class CommandRunner:
    """
    Execute commands without a shell under a bounded environment.

    Output is capped before decoding to prevent an unexpectedly noisy command
    from consuming excessive memory or producing huge trace artifacts.
    """

    _PASSTHROUGH_ENVIRONMENT_NAMES = {
        "PATH",
        "HOME",
        "USERPROFILE",
        "SYSTEMROOT",
        "WINDIR",
        "TMP",
        "TEMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
    }

    def __init__(
        self,
        *,
        budget: ExecutionBudgetTracker,
        maximum_captured_output_bytes: int,
    ) -> None:
        self._budget = budget
        self._maximum_captured_output_bytes = maximum_captured_output_bytes

    def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path,
        timeout_seconds: float,
        extra_environment: Mapping[str, str] | None = None,
        input_bytes: bytes | None = None,
    ) -> CommandResult:
        if not arguments:
            raise CommandExecutionError("Cannot execute an empty command.")
        if any("\x00" in argument for argument in arguments):
            raise CommandExecutionError(
                "Command arguments must not contain NUL bytes."
            )
        self._budget.reserve_tool_call()
        remaining = self._budget.remaining_seconds()
        effective_timeout = min(timeout_seconds, remaining)
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in self._PASSTHROUGH_ENVIRONMENT_NAMES
        }
        # Disable interactive credential prompts. A failed authentication should
        # fail immediately rather than leaving a job waiting indefinitely.
        environment.update(
            {
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "PYTHONUNBUFFERED": "1",
            }
        )
        if extra_environment is not None:
            environment.update(extra_environment)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                list(arguments),
                cwd=cwd,
                env=environment,
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                check=False,
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise CommandTimeoutError(
                f"Command timed out after {effective_timeout:.2f} seconds: "
                f"{self.format_command(arguments)}"
            ) from exc
        except OSError as exc:
            raise CommandExecutionError(
                f"Unable to execute command "
                f"{self.format_command(arguments)}: {exc}"
            ) from exc
        completed_at = time.monotonic()
        stdout_bytes, stdout_truncated = self._truncate(completed.stdout)
        stderr_bytes, stderr_truncated = self._truncate(completed.stderr)
        return CommandResult(
            arguments=tuple(arguments),
            cwd=cwd,
            exit_code=completed.returncode,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            started_monotonic=started,
            completed_monotonic=completed_at,
            output_truncated=stdout_truncated or stderr_truncated,
        )

    def _truncate(self, value: bytes) -> tuple[bytes, bool]:
        if len(value) <= self._maximum_captured_output_bytes:
            return value, False
        marker = (
            b"\n...[output truncated by ChangeExecutionService]...\n"
        )
        retained = self._maximum_captured_output_bytes - len(marker)
        if retained <= 0:
            return marker[: self._maximum_captured_output_bytes], True
        return value[:retained] + marker, True

    @staticmethod
    def format_command(arguments: Sequence[str]) -> str:
        """
        Return a diagnostic representation of an argument array.

        This is intended for logs and exceptions. It is not passed to a shell.
        """
        import shlex

        return shlex.join(arguments)
