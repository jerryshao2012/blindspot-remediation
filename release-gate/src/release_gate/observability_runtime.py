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
from typing import Any, Self

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
_LOCAL_LOCKS: dict[tuple[int, int], threading.Lock] = {}
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


@dataclass(slots=True)
class RefreshSession:
    """A cooperative lock held over a run's snapshot, finalization and refresh."""

    root: Path
    pending_result: Mapping[str, Any]
    namespace: Path | None = None
    _namespace_identity: tuple[int, int] | None = None
    _namespace_fd: int | None = None
    _local_lock: threading.Lock | None = None
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
        descriptor: int | None = None
        try:
            namespace = _safe_namespace(root)
            if namespace is None:
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            session.namespace = namespace
            session._namespace_identity = _directory_identity(namespace)
            if session._namespace_identity is None:
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            session._namespace_fd = _open_directory(namespace)
            if session._namespace_fd is None:
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            descriptor = _open_lock_at(session._namespace_fd)
            if descriptor is None:
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            deadline = clock() + max(0.0, timeout_seconds)
            session._local_lock = _local_lock(session._namespace_identity)
            while not session._local_lock.acquire(blocking=False):
                if clock() >= deadline:
                    _close_quietly(descriptor)
                    descriptor = None
                    session._local_lock = None
                    return session._warn(ObservabilityWarning.LOCK_BUSY)
                wait(min(0.05, max(0.0, deadline - clock())))
            while not _try_lock(descriptor):
                if clock() >= deadline:
                    if not _close_quietly(descriptor):
                        session._warn(ObservabilityWarning.PUBLISH_FAILED)
                    descriptor = None
                    if session._local_lock is not None:
                        session._local_lock.release()
                        session._local_lock = None
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
            if session._local_lock is not None:
                session._local_lock.release()
                session._local_lock = None
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
        if self._local_lock is not None:
            try:
                self._local_lock.release()
            except Exception:
                self._warn(ObservabilityWarning.PUBLISH_FAILED)
            self._local_lock = None

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
        return (
            self.namespace is not None
            and self._namespace_identity is not None
            and _directory_identity(self.namespace) == self._namespace_identity
        )

    def _warn(self, warning: ObservabilityWarning) -> Self:
        self._result = self._result.with_warning(warning)
        return self

    def record_warning(self, warning: ObservabilityWarning) -> None:
        """Record an integration-boundary failure without affecting the gate."""

        self._warn(warning)


def _safe_namespace(root: Path) -> Path | None:
    metadata = _lstat(root)
    if not _safe_directory(metadata):
        return None
    try:
        entries = list(root.iterdir())
    except OSError:
        return None
    matches = [entry for entry in entries if entry.name.casefold() == _NAMESPACE]
    if len(matches) > 1 or (matches and matches[0].name != _NAMESPACE):
        return None
    namespace = root / _NAMESPACE
    if not matches:
        try:
            namespace.mkdir(mode=0o700)
        except (FileExistsError, OSError):
            return None
    return namespace if _safe_directory(_lstat(namespace)) else None


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
        return _LOCAL_LOCKS.setdefault(identity, threading.Lock())
