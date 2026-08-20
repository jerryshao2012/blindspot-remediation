from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def _summary(run_id: str) -> dict[str, object]:
    return {
        "version": 1,
        "run_id": run_id,
        "verdict": "PASS",
        "exit_code": 0,
        "reason_codes": [],
        "started_at": "2026-08-19T00:00:00Z",
        "finished_at": "2026-08-19T00:00:01Z",
        "duration_ms": 1000,
        "base_commit": "a" * 40,
        "candidate_tree": "b" * 40,
        "patch_sha256": "c" * 64,
        "config_sha256": "d" * 64,
        "scope": {
            "status": "PASS", "reason_codes": [], "changed_paths": [],
            "outside_allowed_paths": [], "forbidden_paths": [],
            "review_required_paths": [],
        },
        "checks": [],
        "manifest_path": "manifest.json",
    }


def test_refresh_creates_pinned_namespace_and_publishes_matching_renderers(
    tmp_path: Path,
) -> None:
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    root.mkdir()
    with RefreshSession.acquire(root, _summary("run-one")) as session:
        assert session.locked
        assert session.namespace == root / "_observability"
        result = session.publish()

    assert result.data_path == root / "_observability/gate-decisions-v1.json"
    assert result.dashboard_path == root / "_observability/index.html"
    data = json.loads(result.data_path.read_bytes())
    assert data["generation_id"].encode() in result.dashboard_path.read_bytes()
    assert not (root / "_observability/.refresh.lock").is_symlink()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not portable")
def test_refresh_rejects_casefold_and_symlink_namespace(tmp_path: Path) -> None:
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()
    (root / "_OBSERVABILITY").mkdir()
    result = RefreshSession.acquire(root, _summary("run-one"))
    assert ObservabilityWarning.PATH_UNSAFE in result.warnings

    (root / "_OBSERVABILITY").rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "_observability").symlink_to(outside, target_is_directory=True)
    result = RefreshSession.acquire(root, _summary("run-one"))
    assert ObservabilityWarning.PATH_UNSAFE in result.warnings


@pytest.mark.skipif(os.name == "nt", reason="POSIX record-lock behavior")
def test_refresh_lock_busy_is_a_non_gating_outcome(tmp_path: Path) -> None:
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    namespace = root / "_observability"
    namespace.mkdir(parents=True)
    lock = namespace / ".refresh.lock"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl, os, sys, time; fd = os.open(sys.argv[1], "
                "os.O_RDWR | os.O_CREAT); fcntl.lockf(fd, fcntl.LOCK_EX, 1, 0); "
                "print('ready', flush=True); time.sleep(5)"
            ),
            str(lock),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline() == "ready\n"
        second = RefreshSession.acquire(root, _summary("second"), timeout_seconds=0)
        assert ObservabilityWarning.LOCK_BUSY in second.warnings
        assert not second.locked
    finally:
        holder.terminate()
        holder.wait()


@pytest.mark.skipif(os.name == "nt", reason="POSIX record-lock behavior")
def test_refresh_uses_a_one_byte_record_lock_visible_to_another_process(
    tmp_path: Path,
) -> None:
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    root.mkdir()
    with RefreshSession.acquire(root, _summary("first")) as session:
        assert session.locked
        contender = subprocess.run(
            [
                sys.executable,
                "-c",
                "import fcntl, os, sys; fd = os.open(sys.argv[1], os.O_RDWR); "
                "fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 1, 0);",
                str(root / "_observability/.refresh.lock"),
            ],
            capture_output=True,
            check=False,
        )
    assert contender.returncode != 0


@pytest.mark.skipif(os.name == "nt", reason="POSIX record-lock behavior")
def test_refresh_contends_with_a_standard_one_byte_record_lock(tmp_path: Path) -> None:
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    namespace = root / "_observability"
    namespace.mkdir(parents=True)
    lock = namespace / ".refresh.lock"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl, os, sys, time; fd = os.open(sys.argv[1], "
                "os.O_RDWR | os.O_CREAT); fcntl.lockf(fd, fcntl.LOCK_EX, 1, 0); "
                "print('ready', flush=True); time.sleep(5)"
            ),
            str(lock),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline() == "ready\n"
        contender = RefreshSession.acquire(
            root, _summary("contender"), timeout_seconds=0
        )
        assert not contender.locked
    finally:
        holder.terminate()
        holder.wait()


def test_stale_or_corrupt_cache_is_recovered_by_rescan(tmp_path: Path) -> None:
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    namespace = root / "_observability"
    namespace.mkdir(parents=True)
    (namespace / "gate-decisions-v1.json").write_text("not json", encoding="utf-8")
    with RefreshSession.acquire(root, _summary("run-one")) as session:
        result = session.publish()
    assert json.loads(result.data_path.read_bytes())["source_runs"] == []
    assert "OBSERVABILITY_HISTORY_INVALID" in result.warning_codes


def test_partial_replace_failure_leaves_the_other_file_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    root.mkdir()
    original = runtime.os.replace
    calls = 0

    def fail_second(
        source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        target: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        **kwargs: object,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("replace denied")
        original(source, target, **kwargs)

    monkeypatch.setattr(runtime.os, "replace", fail_second)
    with RefreshSession.acquire(root, _summary("run-one")) as session:
        result = session.publish()
    assert "OBSERVABILITY_PUBLISH_FAILED" in result.warning_codes
    assert result.data_path is not None or result.dashboard_path is not None


def test_swapped_staged_file_is_never_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setattr(runtime, "_same_staged_file_at", lambda *_: False)
    with RefreshSession.acquire(root, _summary("run-one")) as session:
        result = session.publish()
    assert "OBSERVABILITY_PATH_UNSAFE" in result.warning_codes
    assert not (root / "_observability/gate-decisions-v1.json").exists()


def test_target_lstat_error_is_unsafe_and_never_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    namespace = root / "_observability"
    namespace.mkdir(parents=True)
    target = namespace / "gate-decisions-v1.json"
    target.write_bytes(b"owned")
    original_stat = runtime.os.stat
    replaced: list[object] = []

    def denied(path: object, *args: object, **kwargs: object) -> os.stat_result:
        if path == "gate-decisions-v1.json" and kwargs.get("dir_fd") is not None:
            raise PermissionError("denied")
        return original_stat(path, *args, **kwargs)

    def replace(_: object, destination: object) -> None:
        replaced.append(destination)

    monkeypatch.setattr(runtime.os, "stat", denied)
    monkeypatch.setattr(runtime.os, "replace", replace)
    with RefreshSession.acquire(root, _summary("run-one")) as session:
        result = session.publish()
    assert "gate-decisions-v1.json" not in replaced
    assert target.read_bytes() == b"owned"
    assert "OBSERVABILITY_PATH_UNSAFE" in result.warning_codes


def test_cleanup_exception_is_converted_to_a_publication_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    root.mkdir()
    session = RefreshSession.acquire(root, _summary("run-one"))
    monkeypatch.setattr(
        runtime,
        "_unlock",
        lambda _: (_ for _ in ()).throw(RuntimeError("unlock failed")),
    )
    session.close()
    assert "OBSERVABILITY_PUBLISH_FAILED" in session.result.warning_codes


@pytest.mark.skipif(os.name == "nt", reason="hard-link setup is POSIX-specific")
def test_hard_linked_lock_is_not_truncated_or_locked(tmp_path: Path) -> None:
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    namespace = root / "_observability"
    namespace.mkdir(parents=True)
    outside = tmp_path / "outside-lock"
    outside.write_bytes(b"do-not-truncate")
    os.link(outside, namespace / ".refresh.lock")
    session = RefreshSession.acquire(root, _summary("run-one"))
    assert not session.locked
    assert outside.read_bytes() == b"do-not-truncate"
    assert ObservabilityWarning.PATH_UNSAFE in session.warnings


def test_lock_busy_does_not_add_path_unsafe_warning(tmp_path: Path) -> None:
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()
    session = RefreshSession(root, _summary("run-one"))
    assert session.write_snapshot(object()) == session.result  # type: ignore[arg-type]
    session._result = session.result.with_warning(ObservabilityWarning.LOCK_BUSY)
    snapshot = session.write_snapshot(object())  # type: ignore[arg-type]
    assert snapshot.warnings == (ObservabilityWarning.LOCK_BUSY,)


@pytest.mark.skipif(os.name == "nt", reason="symlink replacement is POSIX-specific")
def test_namespace_swap_after_stage_cannot_redirect_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    namespace = root / "_observability"
    namespace.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    original_stage = runtime._stage_at

    def swap(directory_fd: int, payload: bytes) -> object:
        staged = original_stage(directory_fd, payload)
        namespace.rename(root / "saved-namespace")
        namespace.symlink_to(outside, target_is_directory=True)
        return staged

    monkeypatch.setattr(runtime, "_stage_at", swap)
    with RefreshSession.acquire(root, _summary("run-one")) as session:
        result = session.publish()
    assert "OBSERVABILITY_PATH_UNSAFE" in result.warning_codes
    assert not list(outside.iterdir())


@pytest.mark.skipif(os.name == "nt", reason="symlink replacement is POSIX-specific")
def test_root_swap_before_acquisition_never_touches_outside_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()
    outside = tmp_path / "outside"
    namespace = outside / "_observability"
    namespace.mkdir(parents=True)
    lock = namespace / ".refresh.lock"
    lock.write_bytes(b"outside-owned")
    original_open = runtime._open_directory

    def swap(path: Path) -> int | None:
        if path == root:
            root.rename(tmp_path / "saved-root")
            root.symlink_to(outside, target_is_directory=True)
        return original_open(path)

    monkeypatch.setattr(runtime, "_open_directory", swap)
    session = RefreshSession.acquire(root, _summary("run-one"))
    assert not session.locked
    assert lock.read_bytes() == b"outside-owned"
    assert ObservabilityWarning.PATH_UNSAFE in session.warnings


def test_pending_incomplete_run_is_excluded_from_snapshot_diagnostics(
    tmp_path: Path,
) -> None:
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    pending = root / "run-one"
    pending.mkdir(parents=True)
    (pending / ".incomplete").write_bytes(b"")
    with RefreshSession.acquire(root, _summary("run-one")) as session:
        report = session._report(include_pending=True)
    assert report["diagnostics"]["skipped_runs"] == 0
    assert "INCOMPLETE_RUN" not in report["diagnostics"]["warnings"]


def test_windows_backend_dispatch_avoids_descriptor_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability as observability
    import release_gate.observability_runtime as runtime
    from release_gate.evidence import EvidenceRun
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setattr(runtime, "_uses_windows_backend", lambda: True, raising=False)
    monkeypatch.setattr(observability, "_uses_dir_fd", lambda: False)

    def descriptor_operation(*_: object, **__: object) -> Any:
        raise AssertionError("the Windows backend must not use dir_fd operations")

    monkeypatch.setattr(runtime, "_open_directory", descriptor_operation)
    monkeypatch.setattr(runtime, "_open_namespace_at", descriptor_operation)
    monkeypatch.setattr(runtime, "_open_lock_at", descriptor_operation)
    monkeypatch.setattr(runtime, "_stage_at", descriptor_operation)

    evidence = EvidenceRun.create(
        root,
        "windows-run",
        total_bytes=8 * 1024 * 1024,
        patch=b"",
        effective_config=b"{}",
    )
    with RefreshSession.acquire(root, _summary("windows-run")) as session:
        assert session.locked
        snapshot = session.write_snapshot(evidence)
        result = session.publish()

    assert snapshot.snapshot_path == (
        root / "windows-run/observability/gate-decisions.html"
    )
    assert b"windows-run" in snapshot.snapshot_path.read_bytes()
    assert result.data_path is not None
    assert result.dashboard_path is not None
    data = json.loads(result.data_path.read_bytes())
    assert data["source_runs"] == []
    assert data["generation_id"].encode() in result.dashboard_path.read_bytes()


def test_windows_lock_wait_reuses_acquired_local_mutex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    root.mkdir()
    attempts = iter((False, True))
    lock_attempts = 0

    def try_lock(_: int) -> bool:
        nonlocal lock_attempts
        lock_attempts += 1
        return next(attempts)

    elapsed = 0.0

    def clock() -> float:
        return elapsed

    def wait(_: float) -> None:
        nonlocal elapsed
        elapsed += 0.1

    monkeypatch.setattr(runtime, "_try_lock", try_lock)
    monkeypatch.setattr(runtime, "_unlock", lambda _: None)
    session = runtime._acquire_windows(
        RefreshSession(root, _summary("windows-run")),
        1.0,
        clock,
        wait,
    )
    try:
        assert session.locked
        assert lock_attempts == 2
    finally:
        session.close()


def test_windows_lock_open_closes_descriptor_when_validation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime

    closed: list[int] = []
    monkeypatch.setattr(runtime.os, "open", lambda *_args, **_kwargs: 73)
    monkeypatch.setattr(
        runtime.os,
        "fstat",
        lambda _: (_ for _ in ()).throw(PermissionError("denied")),
    )
    monkeypatch.setattr(
        runtime, "_close_quietly", lambda descriptor: not closed.append(descriptor)
    )

    assert runtime._open_lock_path(tmp_path / ".refresh.lock", lambda: True) is None
    assert closed == [73]


def test_windows_lock_open_contains_parent_validation_failure(
    tmp_path: Path,
) -> None:
    import release_gate.observability_runtime as runtime

    lock = tmp_path / ".refresh.lock"
    checks = 0

    def parent_is_safe() -> bool:
        nonlocal checks
        checks += 1
        if checks == 2:
            raise RuntimeError("identity check failed")
        return True

    assert runtime._open_lock_path(lock, parent_is_safe) is None
    descriptor = os.open(lock, os.O_RDWR)
    try:
        assert runtime._try_lock(descriptor)
        runtime._unlock(descriptor)
    finally:
        os.close(descriptor)


def test_windows_root_swap_before_lock_open_does_not_touch_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()
    saved = tmp_path / "saved-evidence"
    replacement_lock = root / "_observability/.refresh.lock"
    original = runtime._open_lock_path
    swapped = False

    def swap_then_open(path: Path, parent_is_safe: object) -> int | None:
        nonlocal swapped
        if not swapped:
            swapped = True
            root.rename(saved)
            replacement_lock.parent.mkdir(parents=True)
            replacement_lock.write_bytes(b"outside-owned")
        assert callable(parent_is_safe)
        return original(path, parent_is_safe)

    monkeypatch.setattr(runtime, "_open_lock_path", swap_then_open)
    session = runtime._acquire_windows(
        RefreshSession(root, _summary("windows-run")),
        0.0,
        lambda: 0.0,
        lambda _: None,
    )

    assert not session.locked
    assert session.warnings == (ObservabilityWarning.PATH_UNSAFE,)
    assert replacement_lock.read_bytes() == b"outside-owned"


@pytest.mark.skipif(
    os.name == "nt", reason="Windows open handles already deny staged-file renames"
)
def test_windows_stage_validates_open_descriptor_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    root.mkdir()
    session = runtime._acquire_windows(
        RefreshSession(root, _summary("windows-run")),
        0.0,
        lambda: 0.0,
        lambda _: None,
    )
    assert session.namespace is not None
    staged = session.namespace / ".release-gate-fixed"
    displaced = session.namespace / ".release-gate-displaced"
    original_open = runtime.os.open

    def substitute_after_open(
        path: object, flags: int, mode: int = 0o777, **kwargs: object
    ) -> int:
        descriptor = original_open(path, flags, mode, **kwargs)
        if Path(path) == staged:
            staged.rename(displaced)
            staged.write_bytes(b"attacker")
        return descriptor

    monkeypatch.setattr(runtime.secrets, "token_hex", lambda _: "fixed")
    monkeypatch.setattr(runtime.os, "open", substitute_after_open)
    try:
        assert runtime._stage_path(session, b"trusted") is None
        assert staged.read_bytes() == b"attacker"
        assert displaced.read_bytes() == b""
    finally:
        session.close()


@pytest.mark.skipif(
    os.name == "nt", reason="Windows open lock handles already deny namespace renames"
)
def test_windows_namespace_swap_before_stage_does_not_touch_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()
    session = runtime._acquire_windows(
        RefreshSession(root, _summary("windows-run")),
        0.0,
        lambda: 0.0,
        lambda _: None,
    )
    assert session.namespace is not None
    saved = root / "saved-observability"
    replacement_target = session.namespace / "gate-decisions-v1.json"
    original = runtime._stage_path
    swapped = False

    def swap_then_stage(
        current: RefreshSession, payload: bytes
    ) -> runtime._StagedPath | None:
        nonlocal swapped
        if not swapped:
            swapped = True
            assert current.namespace is not None
            current.namespace.rename(saved)
            current.namespace.mkdir()
            replacement_target.write_bytes(b"outside-owned")
        return original(current, payload)

    monkeypatch.setattr(runtime, "_stage_path", swap_then_stage)
    result = runtime._publish_windows(session)
    session.close()

    assert ObservabilityWarning.PATH_UNSAFE in result.warnings
    assert replacement_target.read_bytes() == b"outside-owned"


def test_windows_target_substitution_is_not_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()
    outside = tmp_path / "outside-owned"
    outside.write_bytes(b"outside-owned")
    session = runtime._acquire_windows(
        RefreshSession(root, _summary("windows-run")),
        0.0,
        lambda: 0.0,
        lambda _: None,
    )
    assert session.namespace is not None
    target = session.namespace / "gate-decisions-v1.json"
    original = runtime._safe_target_snapshot_path
    inspected = False

    def substitute_after_snapshot(path: Path) -> runtime._TargetSnapshot | None:
        nonlocal inspected
        snapshot = original(path)
        if path == target and not inspected:
            inspected = True
            os.link(outside, target)
        return snapshot

    monkeypatch.setattr(
        runtime, "_safe_target_snapshot_path", substitute_after_snapshot
    )
    result = runtime._publish_windows(session)
    session.close()

    assert ObservabilityWarning.PATH_UNSAFE in result.warnings
    assert outside.read_bytes() == b"outside-owned"
    assert target.read_bytes() == b"outside-owned"


def test_windows_lock_failure_releases_local_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setattr(runtime, "_try_lock", lambda _: False)
    session = runtime._acquire_windows(
        RefreshSession(root, _summary("windows-run")),
        0.0,
        lambda: 0.0,
        lambda _: None,
    )

    assert session.warnings == (ObservabilityWarning.LOCK_BUSY,)
    assert session._local_lock is None
    assert session._local_identity is None
    identity = runtime._directory_identity(root / "_observability")
    assert identity not in runtime._LOCAL_LOCKS


def test_windows_deadline_setup_failure_closes_lock_and_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()

    session = runtime._acquire_windows(
        RefreshSession(root, _summary("windows-run")),
        1.0,
        lambda: (_ for _ in ()).throw(RuntimeError("clock failed")),
        lambda _: None,
    )

    assert session.warnings == (ObservabilityWarning.PATH_UNSAFE,)
    assert session._local_lock is None
    assert session._local_identity is None
    identity = runtime._directory_identity(root / "_observability")
    assert identity not in runtime._LOCAL_LOCKS
    lock = root / "_observability/.refresh.lock"
    descriptor = os.open(lock, os.O_RDWR)
    try:
        assert runtime._try_lock(descriptor)
        runtime._unlock(descriptor)
    finally:
        os.close(descriptor)


def test_real_local_contention_has_exact_lock_busy_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setattr(runtime, "_uses_windows_backend", lambda: True)
    first = RefreshSession.acquire(root, _summary("first"))
    try:
        assert first.locked
        second = RefreshSession.acquire(root, _summary("second"), timeout_seconds=0)
        assert not second.locked
        assert second.warnings == (ObservabilityWarning.LOCK_BUSY,)
    finally:
        first.close()

    with RefreshSession.acquire(root, _summary("third")) as third:
        assert third.locked
