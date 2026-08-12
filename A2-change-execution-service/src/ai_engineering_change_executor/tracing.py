"""
Structured execution tracing.

The trace is evidence about what ChangeExecutionService attempted. It is not a
substitute for the independent release-gate evidence package.

Raw process output can contain source code, customer information, or secrets.
This implementation applies basic redaction and output limits. Production use
should add organization-specific data classification and telemetry controls.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from .process import CommandResult

_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]+"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(password|passwd|secret|api[_-]?key|token)"
            r"\s*[:=]\s*([^\s,;]+)"
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)(https?://[^/\s:@]+:)[^@\s]+(@)"
        ),
        r"\1[REDACTED]\2",
    ),
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_text(value: str) -> str:
    """Apply conservative redaction to diagnostic text."""
    redacted = value
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class ExecutionTraceRecorder:
    """Thread-safe in-memory trace recorder for one execution."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._events: list[dict[str, Any]] = []
        self._sequence = 0
        self._lock = Lock()

    def record(
        self,
        event_type: str,
        message: str,
        **details: Any,
    ) -> None:
        with self._lock:
            self._sequence += 1
            self._events.append(
                {
                    "sequence": self._sequence,
                    "timestamp": utc_now_iso(),
                    "event_type": event_type,
                    "message": redact_text(message),
                    "details": self._redact_value(details),
                }
            )

    def record_command(
        self,
        *,
        purpose: str,
        result: CommandResult,
    ) -> None:
        self.record(
            "command_completed",
            f"Command completed for {purpose}.",
            purpose=purpose,
            arguments=list(result.arguments),
            cwd=str(result.cwd),
            exit_code=result.exit_code,
            duration_seconds=round(result.duration_seconds, 6),
            output_truncated=result.output_truncated,
            output_fingerprint=result.output_fingerprint(),
            stdout=redact_text(result.stdout),
            stderr=redact_text(result.stderr),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "run_id": self._run_id,
            "trace_format_version": "1.0.0",
            "events": list(self._events),
        }

    @classmethod
    def _redact_value(cls, value: Any) -> Any:
        if isinstance(value, str):
            return redact_text(value)
        if isinstance(value, dict):
            return {
                str(key): cls._redact_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls._redact_value(item) for item in value]
        return value
