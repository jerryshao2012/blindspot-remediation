"""
Idempotency support.

The in-memory implementation is suitable for tests and a single-process POC.

Production must use a durable store or broker-level mechanism because
in-memory state disappears on restart and is not shared across replicas.
"""

from __future__ import annotations

from threading import Lock

from .ports import IdempotencyStorePort


class InMemoryIdempotencyStore(IdempotencyStorePort):

    def __init__(self) -> None:
        self._processed: set[tuple[str, str]] = set()
        self._lock = Lock()

    def has_processed(
        self,
        *,
        provider: str,
        event_id: str,
    ) -> bool:
        with self._lock:
            return (provider, event_id) in self._processed

    def mark_processed(
        self,
        *,
        provider: str,
        event_id: str,
    ) -> None:
        with self._lock:
            self._processed.add((provider, event_id))
