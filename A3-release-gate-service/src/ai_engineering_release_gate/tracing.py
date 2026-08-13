"""Structured and redacted release-gate tracing."""

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
        re.compile(r"(?i)(https?://[^/\s:@]+:)[^@\s]+(@)"),
        r"\1[REDACTED]\2",
    ),
)


def redact_text(value: str) -> str:
    result = value
    for pattern, replacement in _REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class GateTraceRecorder:
    """Thread-safe trace for one release-gate run."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._sequence = 0
        self._events: list[dict[str, Any]] = []
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
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_type": event_type,
                    "message": redact_text(message),
                    "details": self._redact(details),
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
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "run_id": self._run_id,
            "trace_format_version": "1.0.0",
            "events": list(self._events),
        }

    @classmethod
    def _redact(cls, value: Any) -> Any:
        if isinstance(value, str):
            return redact_text(value)
        if isinstance(value, dict):
            return {
                str(key): cls._redact(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls._redact(item) for item in value]
        return value
