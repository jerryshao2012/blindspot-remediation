"""Bounded diagnostic trace construction."""

from __future__ import annotations

import json
from typing import Any


class TraceError(ValueError):
    """A trace event violates its closed size contract."""


class TraceRecorder:
    """Collect chronological bounded events with a reserved terminal slot."""

    def __init__(self, *, max_events: int = 2048, max_event_bytes: int = 500) -> None:
        if max_events < 1 or max_event_bytes < 2:
            raise ValueError("trace bounds must be positive")
        self._max_events = max_events
        self._max_event_bytes = max_event_bytes
        self._events: list[dict[str, Any]] = []
        self._dropped = 0

    def add(self, event: str, **fields: Any) -> None:
        item: dict[str, Any] = {"event": event, **fields}
        if len(_canonical(item)) > self._max_event_bytes:
            raise TraceError("trace event exceeds the per-event limit")
        if len(self._events) >= self._max_events - 1:
            self._dropped += 1
            return
        self._events.append(item)

    def finish(self, *, reason_codes: tuple[str, ...] = ()) -> bytes:
        summary: dict[str, Any] = {
            "event": "summary",
            "dropped_events": self._dropped,
            "reason_codes": list(sorted(set(reason_codes))),
        }
        if len(_canonical(summary)) > self._max_event_bytes:
            raise TraceError("terminal trace event exceeds the per-event limit")
        return _canonical([*self._events, summary]) + b"\n"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
