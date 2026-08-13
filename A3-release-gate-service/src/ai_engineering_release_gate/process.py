"""
Bounded external-command execution for authoritative gate controls.

Commands always execute with ``shell=False``. The process environment is
allow-listed and interactive Git credential prompts are disabled.

This is a process-control layer, not a complete security sandbox. Production
deployment must also use container isolation, non-root execution, resource
limits, managed identity, restricted networking, and repository-specific
command approval.
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
    EvidenceBudgetExceeded,
)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Normalized result of one deterministic process."""

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
        digest = hashlib.sha256()
        digest.update(str(self.exit_code).encode("utf-8"))
        digest.update(b"\0")
        digest.update(self.stdout.encode("utf-8", errors="replace"))
        digest.update(b"\0")
        digest.update(self.stderr.encode("utf-8", errors="replace"))
        return digest.hexdigest()


class GateBudgetTracker:
    """
    Track deterministic gate-tool calls and wall-clock runtime.

    Component 3 consumes zero LLM tokens. The shared EvidenceBudget is still
    respected for tool-call and runtime ceilings.
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
            raise EvidenceBudgetExceeded(
                "The deterministic gate runtime budget was exhausted."
            )
        return remaining

    def reserve_tool_call(self) -> None:
        with self._lock:
            if self._tool_calls >= self._maximum_tool_calls:
                raise EvidenceBudgetExceeded(
                    "The deterministic gate tool-call budget was exhausted."
                )
            self._tool_calls += 1


class CommandRunner:
    """Execute one bounded command without invoking a shell."""

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
        budget: GateBudgetTracker,
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
        if any("\x00" in item for item in arguments):
            raise CommandExecutionError(
                "Command arguments must not contain NUL bytes."
            )
        self._budget.reserve_tool_call()
        effective_timeout = min(
            timeout_seconds,
            self._budget.remaining_seconds(),
        )
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in self._PASSTHROUGH_ENVIRONMENT_NAMES
        }
        environment.update(
            {
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "PYTHONUNBUFFERED": "1",
            }
        )
        if extra_environment:
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
                f"Command exceeded {effective_timeout:.2f} seconds: "
                f"{self.format_command(arguments)}"
            ) from exc
        except OSError as exc:
            raise CommandExecutionError(
                f"Unable to execute {self.format_command(arguments)}: {exc}"
            ) from exc
        completed_at = time.monotonic()
        stdout, stdout_truncated = self._truncate(completed.stdout)
        stderr, stderr_truncated = self._truncate(completed.stderr)
        return CommandResult(
            arguments=tuple(arguments),
            cwd=cwd,
            exit_code=completed.returncode,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            started_monotonic=started,
            completed_monotonic=completed_at,
            output_truncated=stdout_truncated or stderr_truncated,
        )

    def _truncate(self, value: bytes) -> tuple[bytes, bool]:
        if len(value) <= self._maximum_captured_output_bytes:
            return value, False
        marker = b"\n...[output truncated by ReleaseGateService]...\n"
        retained = self._maximum_captured_output_bytes - len(marker)
        if retained <= 0:
            return marker[: self._maximum_captured_output_bytes], True
        return value[:retained] + marker, True

    @staticmethod
    def format_command(arguments: Sequence[str]) -> str:
        import shlex

        return shlex.join(arguments)
