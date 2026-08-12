"""
Correlation repository.

The POC implementation is in memory.

The domain interface is intentionally independent of the future persistence
choice.
"""

from __future__ import annotations

from threading import Lock

from .models import (
    EngineeringRunReference,
    PullRequestReference,
    TaskRequest,
)
from .ports import CorrelationStorePort


class InMemoryCorrelationStore(CorrelationStorePort):

    def __init__(self) -> None:
        self._runs: dict[
            str,
            tuple[EngineeringRunReference, TaskRequest],
        ] = {}

        self._pull_requests: dict[
            str,
            PullRequestReference,
        ] = {}

        self._lock = Lock()

    def bind_run(
        self,
        *,
        run: EngineeringRunReference,
        request: TaskRequest,
    ) -> None:
        with self._lock:
            self._runs[run.run_id] = (run, request)

    def bind_pull_request(
        self,
        *,
        run_id: str,
        pull_request: PullRequestReference,
    ) -> None:
        with self._lock:
            self._pull_requests[run_id] = pull_request

    def get_pull_request(
        self,
        *,
        run_id: str,
    ) -> PullRequestReference | None:
        with self._lock:
            return self._pull_requests.get(run_id)
