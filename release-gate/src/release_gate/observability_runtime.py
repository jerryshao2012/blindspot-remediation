"""Best-effort, non-gating publication of Release Gate observability reports."""

from __future__ import annotations

import os
import secrets
import stat
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Self, cast

from release_gate.evidence import EvidenceBudgetExhausted, EvidenceRun
from release_gate.observability import (
    WarningCategory,
    build_report,
    render_html,
    render_json,
)

_NAMESPACE = "_observability"
_LOCK_NAME = ".refresh.lock"
_DATA_NAME = "gate-decisions-v1.json"
_DASHBOARD_NAME = "index.html"
_SNAPSHOT_NAME = "observability/gate-decisions.html"
_MAX_SNAPSHOT_BYTES = 512 * 1024
_LOCAL_LOCKS: dict[tuple[int, int], tuple[threading.Lock, int]] = {}
_LOCAL_LOCKS_GUARD = threading.Lock()


class ObservabilityWarning(StrEnum):
    """Closed, non-gating diagnostics returned from publication."""

    LOCK_BUSY = "OBSERVABILITY_LOCK_BUSY"
    PATH_UNSAFE = "OBSERVABILITY_PATH_UNSAFE"
    BUDGET_EXHAUSTED = "OBSERVABILITY_BUDGET_EXHAUSTED"
    HISTORY_INVALID = "OBSERVABILITY_HISTORY_INVALID"
    PUBLISH_FAILED = "OBSERVABILITY_PUBLISH_FAILED"


@dataclass(frozen=True, slots=True)
class ObservabilityResult:
    snapshot_path: Path | None = None
    dashboard_path: Path | None = None
    data_path: Path | None = None
    warnings: tuple[ObservabilityWarning, ...] = ()

    @property
    def warning_codes(self) -> tuple[str, ...]:
        return tuple(warning.value for warning in self.warnings)

    def with_warning(self, warning: ObservabilityWarning) -> Self:
        return self.__class__(
            self.snapshot_path,
            self.dashboard_path,
            self.data_path,
            tuple(sorted({*self.warnings, warning}, key=str)),
        )


@dataclass(frozen=True, slots=True)
class _FileSnapshot:
    identity: tuple[int, int]
    size: int


@dataclass(frozen=True, slots=True)
class _TargetSnapshot:
    exists: bool
    file: _FileSnapshot | None


@dataclass(frozen=True, slots=True)
class _StagedFile:
    name: str
    file: _FileSnapshot


@dataclass(frozen=True, slots=True)
class _StagedPath:
    path: Path
    file: _FileSnapshot


@dataclass(slots=True)
class RefreshSession:
    """A cooperative lock held over a run's snapshot, finalization and refresh."""

    root: Path
    pending_result: Mapping[str, Any]
    namespace: Path | None = None
    _root_fd: int | None = None
    _root_identity: tuple[int, int] | None = None
    _namespace_identity: tuple[int, int] | None = None
    _namespace_fd: int | None = None
    _local_lock: threading.Lock | None = None
    _local_identity: tuple[int, int] | None = None
    _lock_fd: int | None = None
    _result: ObservabilityResult = field(default_factory=ObservabilityResult)

    @property
    def locked(self) -> bool:
        return self._lock_fd is not None

    @property
    def result(self) -> ObservabilityResult:
        return self._result

    @property
    def warnings(self) -> tuple[ObservabilityWarning, ...]:
        return self._result.warnings

    @classmethod
    def acquire(
        cls,
        root: Path,
        pending_result: Mapping[str, Any],
        *,
        timeout_seconds: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
        wait: Callable[[float], None] = time.sleep,
    ) -> Self:
        session = cls(root=root, pending_result=pending_result)
        if _uses_windows_backend():
            return cast(
                Self,
                _acquire_windows(session, timeout_seconds, clock, wait),
            )
        descriptor: int | None = None
        try:
            session._root_fd = _open_directory(root)
            if session._root_fd is None:
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            opened_namespace = _open_namespace_at(session._root_fd, root)
            if opened_namespace is None:
                session.close()
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            namespace, session._namespace_fd = opened_namespace
            session.namespace = namespace
            session._namespace_identity = _directory_identity(namespace)
            if session._namespace_identity is None:
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            descriptor = _open_lock_at(session._namespace_fd)
            if descriptor is None:
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            deadline = clock() + max(0.0, timeout_seconds)
            session._local_lock = _local_lock(session._namespace_identity)
            session._local_identity = session._namespace_identity
            while not session._local_lock.acquire(blocking=False):
                if clock() >= deadline:
                    _close_quietly(descriptor)
                    descriptor = None
                    session._local_lock = None
                    session._local_identity = None
                    return session._warn(ObservabilityWarning.LOCK_BUSY)
                wait(min(0.05, max(0.0, deadline - clock())))
            while not _try_lock(descriptor):
                if clock() >= deadline:
                    if not _close_quietly(descriptor):
                        session._warn(ObservabilityWarning.PUBLISH_FAILED)
                    descriptor = None
                    if session._local_lock is not None:
                        session._local_lock.release()
                        _release_local(session._local_identity)
                        session._local_lock = None
                        session._local_identity = None
                    return session._warn(ObservabilityWarning.LOCK_BUSY)
                wait(min(0.05, max(0.0, deadline - clock())))
            session._lock_fd = descriptor
            descriptor = None
            return session
        except Exception:
            if descriptor is not None and not _close_quietly(descriptor):
                session._warn(ObservabilityWarning.PUBLISH_FAILED)
            if session._namespace_fd is not None:
                _close_quietly(session._namespace_fd)
                session._namespace_fd = None
            if session._root_fd is not None:
                _close_quietly(session._root_fd)
                session._root_fd = None
            if session._local_lock is not None:
                session._local_lock.release()
                _release_local(session._local_identity)
                session._local_lock = None
                session._local_identity = None
            return session._warn(ObservabilityWarning.PATH_UNSAFE)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._lock_fd is not None:
            try:
                _unlock(self._lock_fd)
            except Exception:
                self._warn(ObservabilityWarning.PUBLISH_FAILED)
            finally:
                if not _close_quietly(self._lock_fd):
                    self._warn(ObservabilityWarning.PUBLISH_FAILED)
                self._lock_fd = None
        if self._namespace_fd is not None:
            if not _close_quietly(self._namespace_fd):
                self._warn(ObservabilityWarning.PUBLISH_FAILED)
            self._namespace_fd = None
        if self._root_fd is not None:
            if not _close_quietly(self._root_fd):
                self._warn(ObservabilityWarning.PUBLISH_FAILED)
            self._root_fd = None
        if self._local_lock is not None:
            try:
                self._local_lock.release()
            except Exception:
                self._warn(ObservabilityWarning.PUBLISH_FAILED)
            self._local_lock = None
            _release_local(self._local_identity)
            self._local_identity = None

    def write_snapshot(self, evidence: EvidenceRun) -> ObservabilityResult:
        """Add a bounded, verified per-run HTML artifact while the lock is held."""

        if not self.locked:
            return self._result
        if not self._safe_namespace():
            return self._warn(ObservabilityWarning.PATH_UNSAFE).result
        try:
            report = self._report(include_pending=True)
            payload = render_html(report)
            path = evidence.try_write_optional_artifact(
                _SNAPSHOT_NAME,
                payload,
                "text/html",
                maximum_bytes=_MAX_SNAPSHOT_BYTES,
            )
            if path is None:
                return self._warn(ObservabilityWarning.BUDGET_EXHAUSTED).result
            self._result = ObservabilityResult(
                path,
                self._result.dashboard_path,
                self._result.data_path,
                self._result.warnings,
            )
        except EvidenceBudgetExhausted:
            self._warn(ObservabilityWarning.BUDGET_EXHAUSTED)
        except Exception:
            self._warn(ObservabilityWarning.PUBLISH_FAILED)
        return self._result

    def publish(self) -> ObservabilityResult:
        """Rescan completed runs and replace each stable target independently."""

        if not self.locked or not self._safe_namespace():
            return self._warn(ObservabilityWarning.PATH_UNSAFE).result
        assert self.namespace is not None
        if _uses_windows_backend():
            return _publish_windows(self)
        assert self._namespace_fd is not None
        try:
            report = self._report(include_pending=False)
            if WarningCategory.CACHE_INVALID.value in report["diagnostics"]["warnings"]:
                self._warn(ObservabilityWarning.HISTORY_INVALID)
            payloads = (
                (_DATA_NAME, render_json(report)),
                (_DASHBOARD_NAME, render_html(report)),
            )
            paths: dict[str, Path] = {}
            for name, payload in payloads:
                before = _safe_target_snapshot_at(self._namespace_fd, name)
                if before is None:
                    self._warn(ObservabilityWarning.PATH_UNSAFE)
                    continue
                temporary = _stage_at(self._namespace_fd, payload)
                try:
                    if (
                        not self._safe_namespace()
                        or not _same_staged_file_at(self._namespace_fd, temporary)
                        or _safe_target_snapshot_at(self._namespace_fd, name) != before
                    ):
                        self._warn(ObservabilityWarning.PATH_UNSAFE)
                        continue
                    os.replace(
                        temporary.name,
                        name,
                        src_dir_fd=self._namespace_fd,
                        dst_dir_fd=self._namespace_fd,
                    )
                    after = _safe_target_snapshot_at(self._namespace_fd, name)
                    if (
                        after is None
                        or not after.exists
                        or after.file != temporary.file
                    ):
                        self._warn(ObservabilityWarning.PUBLISH_FAILED)
                        continue
                    _fsync_directory_fd(self._namespace_fd)
                    paths[name] = self.namespace / name
                except Exception:
                    self._warn(ObservabilityWarning.PUBLISH_FAILED)
                finally:
                    try:
                        os.unlink(temporary.name, dir_fd=self._namespace_fd)
                    except (FileNotFoundError, OSError):
                        pass
            self._result = ObservabilityResult(
                self._result.snapshot_path,
                paths.get(_DASHBOARD_NAME),
                paths.get(_DATA_NAME),
                self._result.warnings,
            )
        except Exception:
            self._warn(ObservabilityWarning.PUBLISH_FAILED)
        return self._result

    def _report(self, *, include_pending: bool) -> dict[str, Any]:
        assert self.namespace is not None
        cache = self.namespace / _DATA_NAME
        return build_report(
            self.root,
            self.pending_result if include_pending else None,
            cache=cache if cache.exists() else None,
            exclude_run_id=str(self.pending_result.get("run_id"))
            if include_pending
            else None,
        )

    def _safe_namespace(self) -> bool:
        namespace_is_safe = (
            self.namespace is not None
            and self._namespace_identity is not None
            and _directory_identity(self.namespace) == self._namespace_identity
        )
        if not namespace_is_safe:
            return False
        return self._root_identity is None or (
            _directory_identity(self.root) == self._root_identity
            and self.namespace == self.root / _NAMESPACE
        )

    def _warn(self, warning: ObservabilityWarning) -> Self:
        self._result = self._result.with_warning(warning)
        return self

    def record_warning(self, warning: ObservabilityWarning) -> None:
        """Record an integration-boundary failure without affecting the gate."""

        self._warn(warning)


def _prepare_namespace_path(
    root: Path,
) -> tuple[Path, tuple[int, int], tuple[int, int]] | None:
    """Create and pin the Windows namespace using path-safe revalidation."""

    root_identity = _directory_identity(root)
    if root_identity is None:
        return None
    try:
        entries = list(root.iterdir())
    except Exception:
        return None
    if _directory_identity(root) != root_identity:
        return None
    matches = [entry for entry in entries if entry.name.casefold() == _NAMESPACE]
    if len(matches) > 1 or (matches and matches[0].name != _NAMESPACE):
        return None
    namespace = root / _NAMESPACE
    if not matches:
        if _directory_identity(root) != root_identity:
            return None
        try:
            namespace.mkdir(mode=0o700)
        except (FileExistsError, OSError):
            return None
    namespace_identity = _directory_identity(namespace)
    if (
        namespace_identity is None
        or _directory_identity(root) != root_identity
        or namespace.parent != root
    ):
        return None
    return namespace, root_identity, namespace_identity


def _open_namespace_at(root_fd: int, root: Path) -> tuple[Path, int] | None:
    """Create/open the reserved namespace without reopening the root pathname."""

    try:
        entries = list(os.scandir(root_fd))
    except OSError:
        return None
    matches = [entry.name for entry in entries if entry.name.casefold() == _NAMESPACE]
    if len(matches) > 1 or (matches and matches[0] != _NAMESPACE):
        return None
    if not matches:
        try:
            os.mkdir(_NAMESPACE, mode=0o700, dir_fd=root_fd)
        except OSError:
            return None
    try:
        inspected = os.stat(_NAMESPACE, dir_fd=root_fd, follow_symlinks=False)
        namespace_fd = os.open(
            _NAMESPACE,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_fd,
        )
    except OSError:
        return None
    opened = os.fstat(namespace_fd)
    if (
        not _safe_directory(inspected)
        or not _safe_directory(opened)
        or (inspected.st_dev, inspected.st_ino) != (opened.st_dev, opened.st_ino)
    ):
        _close_quietly(namespace_fd)
        return None
    return root / _NAMESPACE, namespace_fd


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except OSError:
        return None


def _safe_directory(metadata: os.stat_result | None) -> bool:
    return (
        metadata is not None
        and stat.S_ISDIR(metadata.st_mode)
        and not _reparse(metadata)
    )


def _safe_file(metadata: os.stat_result | None) -> bool:
    return (
        metadata is not None
        and stat.S_ISREG(metadata.st_mode)
        and not _reparse(metadata)
    )


def _reparse(metadata: os.stat_result) -> bool:
    attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(getattr(metadata, "st_file_attributes", 0) & attribute)


def _directory_identity(path: Path) -> tuple[int, int] | None:
    metadata = _lstat(path)
    if not _safe_directory(metadata):
        return None
    assert metadata is not None
    return (metadata.st_dev, metadata.st_ino)


def _open_directory(path: Path) -> int | None:
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError:
        return None
    if not _safe_directory(os.fstat(descriptor)):
        _close_quietly(descriptor)
        return None
    return descriptor


def _open_lock_at(directory_fd: int) -> int | None:
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(_LOCK_NAME, flags, 0o600, dir_fd=directory_fd)
    except OSError:
        return None
    try:
        opened = os.fstat(descriptor)
        at_path = os.stat(_LOCK_NAME, dir_fd=directory_fd, follow_symlinks=False)
    except OSError:
        os.close(descriptor)
        return None
    if not _safe_file(opened) or opened.st_nlink != 1 or not _safe_file(at_path):
        os.close(descriptor)
        return None
    assert at_path is not None
    if (opened.st_dev, opened.st_ino) != (at_path.st_dev, at_path.st_ino):
        os.close(descriptor)
        return None
    try:
        os.ftruncate(descriptor, 1)
    except OSError:
        os.close(descriptor)
        return None
    return descriptor


def _try_lock(descriptor: int) -> bool:
    if os.name == "nt":
        import msvcrt

        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
            return True
        except OSError:
            return False
    import fcntl

    try:
        fcntl.lockf(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB, 1, 0, os.SEEK_SET)
        return True
    except OSError:
        return False


def _unlock(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
    else:
        import fcntl

        fcntl.lockf(descriptor, fcntl.LOCK_UN, 1, 0, os.SEEK_SET)


def _safe_target_snapshot_at(
    directory_fd: int, name: str
) -> _TargetSnapshot | None:
    try:
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return _TargetSnapshot(False, None)
    except OSError:
        return None
    if not _safe_file(metadata):
        return None
    return _TargetSnapshot(True, _file_snapshot(metadata))


def _stage_at(directory_fd: int, payload: bytes) -> _StagedFile:
    name = f".release-gate-{secrets.token_hex(12)}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(name, dir_fd=directory_fd)
        except OSError:
            pass
        raise
    metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if not _safe_file(metadata):
        os.unlink(name, dir_fd=directory_fd)
        raise OSError("staged observability file is unsafe")
    return _StagedFile(name, _file_snapshot(metadata))


def _same_staged_file_at(directory_fd: int, staged: _StagedFile) -> bool:
    try:
        metadata = os.stat(staged.name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError:
        return False
    return (
        _safe_file(metadata)
        and metadata is not None
        and _file_snapshot(metadata) == staged.file
    )


def _file_snapshot(metadata: os.stat_result) -> _FileSnapshot:
    return _FileSnapshot((metadata.st_dev, metadata.st_ino), metadata.st_size)


def _fsync_directory_fd(descriptor: int) -> None:
    os.fsync(descriptor)


def _close_quietly(descriptor: int) -> bool:
    try:
        os.close(descriptor)
    except Exception:
        return False
    return True


def _local_lock(identity: tuple[int, int]) -> threading.Lock:
    with _LOCAL_LOCKS_GUARD:
        lock, references = _LOCAL_LOCKS.get(identity, (threading.Lock(), 0))
        _LOCAL_LOCKS[identity] = (lock, references + 1)
        return lock


def _release_local(identity: tuple[int, int] | None) -> None:
    if identity is None:
        return
    with _LOCAL_LOCKS_GUARD:
        lock, references = _LOCAL_LOCKS.get(identity, (threading.Lock(), 0))
        if references <= 1:
            _LOCAL_LOCKS.pop(identity, None)
        else:
            _LOCAL_LOCKS[identity] = (lock, references - 1)


def _uses_windows_backend() -> bool:
    return os.name == "nt"


def _acquire_windows(
    session: RefreshSession,
    timeout_seconds: float,
    clock: Callable[[], float],
    wait: Callable[[float], None],
) -> RefreshSession:
    """Path backend for Windows hosts, where Python lacks ``dir_fd`` support."""

    prepared = _prepare_namespace_path(session.root)
    if prepared is None:
        return session._warn(ObservabilityWarning.PATH_UNSAFE)
    namespace, root_identity, namespace_identity = prepared
    session.namespace = namespace
    session._root_identity = root_identity
    session._namespace_identity = namespace_identity
    descriptor = _open_lock_path(namespace / _LOCK_NAME, session._safe_namespace)
    if descriptor is None:
        return session._warn(ObservabilityWarning.PATH_UNSAFE)
    local_acquired = False
    try:
        session._local_identity = namespace_identity
        session._local_lock = _local_lock(namespace_identity)
        deadline = clock() + max(0.0, timeout_seconds)
        assert session._local_lock is not None
        while not session._local_lock.acquire(blocking=False):
            if clock() >= deadline:
                return _failed_windows_acquire(
                    session, descriptor, False, ObservabilityWarning.LOCK_BUSY
                )
            wait(min(0.05, max(0.0, deadline - clock())))
        local_acquired = True
        while not _try_lock(descriptor):
            if clock() >= deadline:
                return _failed_windows_acquire(
                    session, descriptor, True, ObservabilityWarning.LOCK_BUSY
                )
            wait(min(0.05, max(0.0, deadline - clock())))
        if not session._safe_namespace() or not _same_open_file_path(
            descriptor, namespace / _LOCK_NAME
        ):
            return _failed_windows_acquire(
                session, descriptor, True, ObservabilityWarning.PATH_UNSAFE
            )
        session._lock_fd = descriptor
        return session
    except Exception:
        return _failed_windows_acquire(
            session,
            descriptor,
            local_acquired,
            ObservabilityWarning.PATH_UNSAFE,
        )


def _failed_windows_acquire(
    session: RefreshSession,
    descriptor: int,
    local_acquired: bool,
    warning: ObservabilityWarning,
) -> RefreshSession:
    if not _close_quietly(descriptor):
        session._warn(ObservabilityWarning.PUBLISH_FAILED)
    if local_acquired and session._local_lock is not None:
        try:
            session._local_lock.release()
        except Exception:
            session._warn(ObservabilityWarning.PUBLISH_FAILED)
    _release_local(session._local_identity)
    session._local_lock = None
    session._local_identity = None
    return session._warn(warning)


def _open_lock_path(path: Path, parent_is_safe: Callable[[], bool]) -> int | None:
    descriptor: int | None = None
    try:
        try:
            before = path.lstat()
        except FileNotFoundError:
            before = None
        except OSError:
            return None
        if before is not None and (
            not _safe_file(before) or not _single_link(before)
        ):
            return None
        if not parent_is_safe():
            return None
        flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        if before is None:
            flags |= os.O_CREAT | os.O_EXCL
        descriptor = os.open(path, flags, 0o600)
        opened = os.fstat(descriptor)
        at_path = path.lstat()
        if (
            not _safe_file(opened)
            or not _single_link(opened)
            or not _safe_file(at_path)
            or not _single_link(at_path)
            or _file_snapshot(opened).identity != _file_snapshot(at_path).identity
            or (
                before is not None
                and _file_snapshot(before).identity
                != _file_snapshot(opened).identity
            )
            or not parent_is_safe()
        ):
            return None
        os.ftruncate(descriptor, 1)
        if not parent_is_safe() or not _same_open_file_path(descriptor, path):
            return None
        result = descriptor
        descriptor = None
        return result
    except Exception:
        return None
    finally:
        if descriptor is not None:
            _close_quietly(descriptor)


def _same_open_file_path(descriptor: int, path: Path) -> bool:
    try:
        opened = os.fstat(descriptor)
        at_path = path.lstat()
    except OSError:
        return False
    return (
        _safe_file(opened)
        and _single_link(opened)
        and _safe_file(at_path)
        and _single_link(at_path)
        and _file_snapshot(opened).identity == _file_snapshot(at_path).identity
    )


def _single_link(metadata: os.stat_result) -> bool:
    links = getattr(metadata, "st_nlink", None)
    return links is None or links == 1


def _stage_path(session: RefreshSession, payload: bytes) -> _StagedPath | None:
    """Create a pinned staged file and validate it before writing any bytes."""

    if session.namespace is None or not session._safe_namespace():
        return None
    path = session.namespace / f".release-gate-{secrets.token_hex(12)}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    opened_identity: tuple[int, int] | None = None
    completed = False
    try:
        if not session._safe_namespace():
            return None
        descriptor = os.open(path, flags, 0o600)
        opened = os.fstat(descriptor)
        at_path = path.lstat()
        if (
            not _safe_file(opened)
            or not _single_link(opened)
            or not _safe_file(at_path)
            or not _single_link(at_path)
            or _file_snapshot(opened).identity != _file_snapshot(at_path).identity
            or not session._safe_namespace()
        ):
            return None
        opened_identity = _file_snapshot(opened).identity
        stream = os.fdopen(descriptor, "wb")
        descriptor = None
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        after = path.lstat()
        if (
            not _safe_file(after)
            or not _single_link(after)
            or _file_snapshot(after).identity != opened_identity
            or after.st_size != len(payload)
            or not session._safe_namespace()
        ):
            return None
        completed = True
        return _StagedPath(path, _file_snapshot(after))
    except OSError:
        return None
    finally:
        if descriptor is not None:
            _close_quietly(descriptor)
        if (
            not completed
            and opened_identity is not None
            and session._safe_namespace()
            and _path_has_identity(path, opened_identity)
        ):
            try:
                path.unlink()
            except OSError:
                pass


def _path_has_identity(path: Path, identity: tuple[int, int]) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return (
        _safe_file(metadata)
        and _single_link(metadata)
        and _file_snapshot(metadata).identity == identity
    )


def _same_staged_path(session: RefreshSession, staged: _StagedPath) -> bool:
    return session._safe_namespace() and _path_has_identity(
        staged.path, staged.file.identity
    )


def _remove_staged_path(session: RefreshSession, staged: _StagedPath) -> None:
    if not _same_staged_path(session, staged):
        return
    try:
        staged.path.unlink()
    except OSError:
        pass


def _fsync_directory_path(session: RefreshSession) -> None:
    if session.namespace is None or not session._safe_namespace():
        return
    descriptor: int | None = None
    try:
        descriptor = os.open(
            session.namespace,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        opened = os.fstat(descriptor)
        if (
            _safe_directory(opened)
            and session._safe_namespace()
            and _directory_identity(session.namespace)
            == session._namespace_identity
        ):
            os.fsync(descriptor)
    except OSError:
        pass
    finally:
        if descriptor is not None:
            _close_quietly(descriptor)


def _publish_windows(session: RefreshSession) -> ObservabilityResult:
    assert session.namespace is not None
    try:
        report = session._report(include_pending=False)
        if WarningCategory.CACHE_INVALID.value in report["diagnostics"]["warnings"]:
            session._warn(ObservabilityWarning.HISTORY_INVALID)
        paths: dict[str, Path] = {}
        payloads = (
            (_DATA_NAME, render_json(report)),
            (_DASHBOARD_NAME, render_html(report)),
        )
        for name, payload in payloads:
            target = session.namespace / name
            before = _safe_target_snapshot_path(target)
            if before is None or not session._safe_namespace():
                session._warn(ObservabilityWarning.PATH_UNSAFE)
                continue
            staged = _stage_path(session, payload)
            if staged is None:
                session._warn(ObservabilityWarning.PATH_UNSAFE)
                continue
            try:
                if (
                    not _same_staged_path(session, staged)
                    or _safe_target_snapshot_path(target) != before
                ):
                    session._warn(ObservabilityWarning.PATH_UNSAFE)
                    continue
                os.replace(staged.path, target)
                after = _safe_target_snapshot_path(target)
                if (
                    after is None
                    or not after.exists
                    or after.file != staged.file
                    or not session._safe_namespace()
                ):
                    session._warn(ObservabilityWarning.PUBLISH_FAILED)
                    continue
                _fsync_directory_path(session)
                paths[name] = target
            except OSError:
                session._warn(ObservabilityWarning.PUBLISH_FAILED)
            finally:
                _remove_staged_path(session, staged)
        session._result = ObservabilityResult(
            session.result.snapshot_path,
            paths.get(_DASHBOARD_NAME),
            paths.get(_DATA_NAME),
            session.result.warnings,
        )
    except Exception:
        session._warn(ObservabilityWarning.PUBLISH_FAILED)
    return session.result


def _safe_target_snapshot_path(path: Path) -> _TargetSnapshot | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return _TargetSnapshot(False, None)
    except OSError:
        return None
    if not _safe_file(metadata) or not _single_link(metadata):
        return None
    return _TargetSnapshot(True, _file_snapshot(metadata))
