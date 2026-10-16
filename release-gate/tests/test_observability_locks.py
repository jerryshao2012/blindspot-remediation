from __future__ import annotations

import os
from pathlib import Path

import pytest

from release_gate import observability_locks


def test_posix_lock_round_trip(tmp_path: Path) -> None:
    lock_path = tmp_path / "refresh.lock"
    with lock_path.open("w+") as stream:
        descriptor = stream.fileno()
        assert observability_locks.try_lock(descriptor, lambda *_: None)
        observability_locks.unlock(descriptor, lambda *_: None)


@pytest.mark.skipif(os.name == "nt", reason="POSIX lock backend")
def test_posix_lock_failure_is_reported_for_invalid_descriptor() -> None:
    assert not observability_locks.try_lock(-1, lambda *_: None)


def test_windows_dispatch_uses_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, bool]] = []
    monkeypatch.setattr(observability_locks.os, "name", "nt")

    def windows_lock(descriptor: int, lock: bool) -> None:
        calls.append((descriptor, lock))

    assert observability_locks.try_lock(7, windows_lock)
    observability_locks.unlock(7, windows_lock)
    assert calls == [(7, True), (7, False)]


def test_windows_lock_failure_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(observability_locks.os, "name", "nt")

    def windows_lock(_: int, __: bool) -> None:
        raise OSError("lock failed")

    assert not observability_locks.try_lock(7, windows_lock)


def test_runtime_windows_callback_accepts_dispatch_arguments() -> None:
    import inspect

    from release_gate import observability_runtime

    inspect.signature(observability_runtime._windows_file_lock).bind(7, True)
