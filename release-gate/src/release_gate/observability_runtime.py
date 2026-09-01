"""Best-effort, non-gating publication of Release Gate observability reports."""

from __future__ import annotations

import hashlib
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
_LOCK_OFFSET = 0
_LOCAL_LOCKS: dict[tuple[int, int], tuple[threading.Lock, int]] = {}
_LOCAL_LOCKS_GUARD = threading.Lock()
_BUDGET_DIAGNOSTICS = frozenset(
    (
        WarningCategory.RUN_TOO_LARGE.value,
        WarningCategory.SCAN_LIMIT_REACHED.value,
    )
)


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
    descriptor: int
    payload: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class _StagedPath:
    path: Path
    file: _FileSnapshot
    descriptor: int
    payload: bytes
    sha256: str


@dataclass(slots=True)
class RefreshSession:
    """A cooperative lock held over a run's snapshot, finalization and refresh."""

    root: Path
    pending_result: Mapping[str, Any]
    namespace: Path | None = None
    _ancestor_fds: list[int] = field(default_factory=list)
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
        local_acquired = False
        try:
            session._root_fd = _open_directory(root)
            if session._root_fd is None:
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            opened_root = os.fstat(session._root_fd)
            session._root_identity = (opened_root.st_dev, opened_root.st_ino)
            if _directory_identity(root) != session._root_identity:
                raise OSError("observability root identity changed during acquisition")
            opened_namespace = _open_namespace_at(session._root_fd, root)
            if opened_namespace is None:
                session.close()
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            namespace, session._namespace_fd = opened_namespace
            session.namespace = namespace
            opened_namespace_metadata = os.fstat(session._namespace_fd)
            session._namespace_identity = (
                opened_namespace_metadata.st_dev,
                opened_namespace_metadata.st_ino,
            )
            if _directory_identity(namespace) != session._namespace_identity:
                raise OSError(
                    "observability namespace identity changed during acquisition"
                )
            descriptor = _open_lock_at(session._namespace_fd)
            if descriptor is None:
                session.close()
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
            deadline = clock() + max(0.0, timeout_seconds)
            session._local_lock = _local_lock(session._namespace_identity)
            session._local_identity = session._namespace_identity
            while not session._local_lock.acquire(blocking=False):
                if clock() >= deadline:
                    _close_quietly(descriptor)
                    descriptor = None
                    _release_local(session._local_identity)
                    session._local_lock = None
                    session._local_identity = None
                    session.close()
                    return session._warn(ObservabilityWarning.LOCK_BUSY)
                wait(min(0.05, max(0.0, deadline - clock())))
            local_acquired = True
            while not _try_lock(descriptor):
                if clock() >= deadline:
                    if not _close_quietly(descriptor):
                        session._warn(ObservabilityWarning.PUBLISH_FAILED)
                    descriptor = None
                    if session._local_lock is not None:
                        session._local_lock.release()
                        local_acquired = False
                        _release_local(session._local_identity)
                        session._local_lock = None
                        session._local_identity = None
                    session.close()
                    return session._warn(ObservabilityWarning.LOCK_BUSY)
                wait(min(0.05, max(0.0, deadline - clock())))
            if not _same_open_file_at(descriptor, session._namespace_fd, _LOCK_NAME):
                try:
                    _unlock(descriptor)
                except Exception:
                    session._warn(ObservabilityWarning.PUBLISH_FAILED)
                _close_quietly(descriptor)
                descriptor = None
                assert session._local_lock is not None
                session._local_lock.release()
                local_acquired = False
                _release_local(session._local_identity)
                session._local_lock = None
                session._local_identity = None
                session.close()
                return session._warn(ObservabilityWarning.PATH_UNSAFE)
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
            if local_acquired and session._local_lock is not None:
                try:
                    session._local_lock.release()
                except Exception:
                    session._warn(ObservabilityWarning.PUBLISH_FAILED)
            if session._local_lock is not None:
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
        while self._ancestor_fds:
            if not _close_quietly(self._ancestor_fds.pop()):
                self._warn(ObservabilityWarning.PUBLISH_FAILED)
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
            _record_report_warnings(self, report)
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
            _record_report_warnings(self, report)
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
                try:
                    temporary = _stage_at(self._namespace_fd, payload)
                except OSError:
                    self._warn(ObservabilityWarning.PATH_UNSAFE)
                    continue
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
                        or _read_staged_payload(temporary) != temporary.payload
                    ):
                        self._warn(ObservabilityWarning.PATH_UNSAFE)
                        if _restore_staged_file_at(self._namespace_fd, name, temporary):
                            _fsync_directory_fd(self._namespace_fd)
                            paths[name] = self.namespace / name
                        else:
                            self._warn(ObservabilityWarning.PUBLISH_FAILED)
                        continue
                    _fsync_directory_fd(self._namespace_fd)
                    paths[name] = self.namespace / name
                except Exception:
                    self._warn(ObservabilityWarning.PUBLISH_FAILED)
                finally:
                    _close_quietly(temporary.descriptor)
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
            and self._namespace_fd is not None
            and self._namespace_identity is not None
            and _directory_fd_identity(self._namespace_fd) == self._namespace_identity
            and _directory_identity(self.namespace) == self._namespace_identity
        )
        if not namespace_is_safe:
            return False
        scope_is_safe = (
            self._root_fd is not None
            and self._root_identity is not None
            and _directory_fd_identity(self._root_fd) == self._root_identity
            and all(
                _directory_fd_identity(descriptor) is not None
                for descriptor in self._ancestor_fds
            )
            and (
                _directory_identity(self.root) == self._root_identity
                and self.namespace == self.root / _NAMESPACE
            )
        )
        if not scope_is_safe:
            return False
        if self._lock_fd is None:
            return True
        assert self.namespace is not None
        assert self._namespace_fd is not None
        if _uses_windows_backend():
            return _same_open_file_path(
                self._lock_fd,
                self.namespace / _LOCK_NAME,
                self._namespace_fd,
            )
        return _same_open_file_at(self._lock_fd, self._namespace_fd, _LOCK_NAME)

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


def _record_report_warnings(session: RefreshSession, report: Mapping[str, Any]) -> None:
    diagnostics = report.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        session._warn(ObservabilityWarning.HISTORY_INVALID)
        return
    raw_warnings = diagnostics.get("warnings")
    warning_values = (
        {value for value in raw_warnings if isinstance(value, str)}
        if isinstance(raw_warnings, list)
        else set()
    )
    if warning_values & _BUDGET_DIAGNOSTICS:
        session._warn(ObservabilityWarning.BUDGET_EXHAUSTED)
    if warning_values - _BUDGET_DIAGNOSTICS:
        session._warn(ObservabilityWarning.HISTORY_INVALID)


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


def _directory_fd_identity(descriptor: int) -> tuple[int, int] | None:
    try:
        metadata = os.fstat(descriptor)
    except OSError:
        return None
    if not _safe_directory(metadata):
        return None
    return (metadata.st_dev, metadata.st_ino)


def _open_directory(path: Path) -> int | None:
    return _open_posix_directory_chain(path)


def _open_posix_directory_chain(path: Path) -> int | None:
    """Open an absolute directory by walking from a trusted root descriptor."""

    if not path.is_absolute() or not path.anchor:
        return None
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path.anchor,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        if not _safe_directory(os.fstat(descriptor)):
            return None
        for component in path.parts[1:]:
            if component in {"", ".", ".."} or not _exact_component(
                descriptor, component
            ):
                return None
            inspected = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
            if not _safe_directory(inspected):
                return None
            child: int | None = None
            try:
                child = os.open(
                    component,
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=descriptor,
                )
                opened = os.fstat(child)
                current = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
            except OSError:
                if child is not None:
                    _close_quietly(child)
                return None
            if (
                not _safe_directory(opened)
                or not _safe_directory(current)
                or (inspected.st_dev, inspected.st_ino)
                != (opened.st_dev, opened.st_ino)
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            ):
                assert child is not None
                _close_quietly(child)
                return None
            _close_quietly(descriptor)
            assert child is not None
            descriptor = child
        identity = _directory_fd_identity(descriptor)
        if identity is None or _directory_identity(path) != identity:
            return None
        result = descriptor
        descriptor = None
        return result
    except OSError:
        return None
    finally:
        if descriptor is not None:
            _close_quietly(descriptor)


def _exact_component(directory_fd: int, component: str) -> bool:
    try:
        with os.scandir(directory_fd) as entries:
            matches = [
                entry.name
                for entry in entries
                if entry.name.casefold() == component.casefold()
            ]
    except OSError:
        return False
    return matches == [component]


def _canonical_child_safe(directory_fd: int, name: str) -> bool:
    names = _directory_names(directory_fd)
    if names is None:
        return False
    matches = [entry for entry in names if entry.casefold() == name.casefold()]
    return matches in ([], [name])


def _canonical_child_available(directory_fd: int, name: str) -> bool:
    names = _directory_names(directory_fd)
    return names is not None and not any(
        entry.casefold() == name.casefold() for entry in names
    )


def _canonical_child_exact(directory_fd: int, name: str) -> bool:
    names = _directory_names(directory_fd)
    if names is None:
        return False
    return [entry for entry in names if entry.casefold() == name.casefold()] == [name]


def _directory_names(directory_fd: int) -> list[str] | None:
    if _uses_native_windows_paths():
        return _windows_directory_names_native(directory_fd)
    try:
        with os.scandir(directory_fd) as entries:
            return [entry.name for entry in entries]
    except OSError:
        return None


def _windows_directory_names_native(  # pragma: no cover - Windows CI
    directory_fd: int,
) -> list[str] | None:
    import ctypes
    from ctypes import wintypes

    class _IoStatusBlock(ctypes.Structure):
        _fields_ = (
            ("status", wintypes.LPVOID),
            ("information", ctypes.c_size_t),
        )

    ntdll = ctypes.WinDLL("ntdll")  # type: ignore[attr-defined]
    query = ntdll.NtQueryDirectoryFile
    query.argtypes = (
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.LPVOID,
        ctypes.POINTER(_IoStatusBlock),
        wintypes.LPVOID,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.BOOLEAN,
        wintypes.LPVOID,
        wintypes.BOOLEAN,
    )
    query.restype = wintypes.LONG
    names: list[str] = []
    restart = True
    while True:
        buffer = ctypes.create_string_buffer(64 * 1024)
        io_status = _IoStatusBlock()
        status = int(
            query(
                wintypes.HANDLE(_windows_handle_from_fd(directory_fd)),
                None,
                None,
                None,
                ctypes.byref(io_status),
                buffer,
                len(buffer),
                12,  # FileNamesInformation
                False,
                None,
                restart,
            )
        )
        restart = False
        if status & 0xFFFFFFFF == 0x80000006:  # STATUS_NO_MORE_FILES
            return names
        if status < 0:
            return None
        if not io_status.information:
            return names
        offset = 0
        while True:
            address = ctypes.addressof(buffer) + offset
            next_offset = int.from_bytes(ctypes.string_at(address, 4), "little")
            name_length = int.from_bytes(ctypes.string_at(address + 8, 4), "little")
            end = offset + 12 + name_length
            if end > len(buffer):
                return None
            try:
                name = ctypes.string_at(address + 12, name_length).decode("utf-16-le")
            except UnicodeDecodeError:
                return None
            names.append(name)
            if len(names) > 100_000:
                return None
            if next_offset == 0:
                break
            if next_offset < 12 or offset + next_offset >= len(buffer):
                return None
            offset += next_offset


def _open_lock_at(directory_fd: int) -> int | None:
    if not _canonical_child_safe(directory_fd, _LOCK_NAME):
        return None
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
    if (
        not _canonical_child_safe(directory_fd, _LOCK_NAME)
        or not _safe_file(opened)
        or opened.st_nlink != 1
        or not _safe_file(at_path)
    ):
        os.close(descriptor)
        return None
    assert at_path is not None
    if (opened.st_dev, opened.st_ino) != (at_path.st_dev, at_path.st_ino):
        os.close(descriptor)
        return None
    return descriptor


def _same_open_file_at(descriptor: int, directory_fd: int, name: str) -> bool:
    if not _canonical_child_exact(directory_fd, name):
        return False
    try:
        opened = os.fstat(descriptor)
        at_path = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError:
        return False
    return (
        _safe_file(opened)
        and opened.st_nlink == 1
        and _safe_file(at_path)
        and at_path.st_nlink == 1
        and _file_snapshot(opened).identity == _file_snapshot(at_path).identity
    )


def _try_lock(descriptor: int) -> bool:
    if os.name == "nt":
        return _try_lock_windows(descriptor)
    import fcntl

    try:
        fcntl.lockf(
            descriptor,
            fcntl.LOCK_EX | fcntl.LOCK_NB,
            1,
            _LOCK_OFFSET,
            os.SEEK_SET,
        )
        return True
    except OSError:
        return False


def _unlock(descriptor: int) -> None:
    if os.name == "nt":
        _unlock_windows(descriptor)
    else:
        import fcntl

        fcntl.lockf(descriptor, fcntl.LOCK_UN, 1, _LOCK_OFFSET, os.SEEK_SET)


def _try_lock_windows(descriptor: int) -> bool:  # pragma: no cover - Windows CI
    try:
        _windows_file_lock(descriptor, lock=True)
    except OSError:
        return False
    return True


def _unlock_windows(descriptor: int) -> None:  # pragma: no cover - Windows CI
    _windows_file_lock(descriptor, lock=False)


def _windows_file_lock(  # pragma: no cover - Windows CI
    descriptor: int, *, lock: bool
) -> None:
    import ctypes
    from ctypes import wintypes

    class _Overlapped(ctypes.Structure):
        _fields_ = (
            ("internal", ctypes.c_size_t),
            ("internal_high", ctypes.c_size_t),
            ("offset", wintypes.DWORD),
            ("offset_high", wintypes.DWORD),
            ("event", wintypes.HANDLE),
        )

    overlapped = _Overlapped()
    overlapped.offset = _LOCK_OFFSET & 0xFFFFFFFF
    overlapped.offset_high = (_LOCK_OFFSET >> 32) & 0xFFFFFFFF
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    handle = wintypes.HANDLE(_windows_handle_from_fd(descriptor))
    if lock:
        operation = kernel32.LockFileEx
        operation.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_Overlapped),
        )
        operation.restype = wintypes.BOOL
        succeeded = operation(
            handle,
            0x00000001 | 0x00000002,
            0,
            1,
            0,
            ctypes.byref(overlapped),
        )
    else:
        operation = kernel32.UnlockFileEx
        operation.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_Overlapped),
        )
        operation.restype = wintypes.BOOL
        succeeded = operation(handle, 0, 1, 0, ctypes.byref(overlapped))
    if not succeeded:
        raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]


def _safe_target_snapshot_at(directory_fd: int, name: str) -> _TargetSnapshot | None:
    if not _canonical_child_safe(directory_fd, name):
        return None
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
    if not _canonical_child_available(directory_fd, name):
        raise OSError("staged observability name collides")
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, 0o600, dir_fd=directory_fd)
    try:
        _write_descriptor(descriptor, payload)
        os.fsync(descriptor)
        opened = os.fstat(descriptor)
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not _canonical_child_exact(directory_fd, name)
            or not _safe_file(opened)
            or opened.st_nlink != 1
            or not _safe_file(metadata)
            or metadata.st_nlink != 1
            or _file_snapshot(opened) != _file_snapshot(metadata)
            or metadata.st_size != len(payload)
        ):
            raise OSError("staged observability file is unsafe")
        return _StagedFile(
            name,
            _file_snapshot(opened),
            descriptor,
            payload,
            hashlib.sha256(payload).hexdigest(),
        )
    except Exception:
        _close_quietly(descriptor)
        raise


def _same_staged_file_at(directory_fd: int, staged: _StagedFile) -> bool:
    if not _canonical_child_exact(directory_fd, staged.name):
        return False
    try:
        opened = os.fstat(staged.descriptor)
        metadata = os.stat(staged.name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError:
        return False
    return (
        _safe_file(opened)
        and opened.st_nlink == 1
        and _safe_file(metadata)
        and metadata is not None
        and metadata.st_nlink == 1
        and _file_snapshot(opened) == staged.file
        and _file_snapshot(metadata) == staged.file
    )


def _write_descriptor(descriptor: int, payload: bytes) -> None:
    os.lseek(descriptor, 0, os.SEEK_SET)
    view = memoryview(payload)
    written = 0
    while written < len(view):
        count = os.write(descriptor, view[written:])
        if count <= 0:
            raise OSError("short observability stage write")
        written += count


def _read_staged_payload(staged: _StagedFile | _StagedPath) -> bytes | None:
    try:
        metadata = os.fstat(staged.descriptor)
        if not _safe_file(metadata) or _file_snapshot(metadata) != staged.file:
            return None
        os.lseek(staged.descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = staged.file.size
        while remaining:
            chunk = os.read(staged.descriptor, min(remaining, 64 * 1024))
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if hashlib.sha256(payload).hexdigest() != staged.sha256:
            return None
        return payload if payload == staged.payload else None
    except OSError:
        return None


def _restore_staged_file_at(
    directory_fd: int, target: str, trusted: _StagedFile
) -> bool:
    if not _staged_descriptor_identity_matches(trusted):
        return False
    payload = trusted.payload
    recovery: _StagedFile | None = None
    try:
        recovery = _stage_at(directory_fd, payload)
        if not _same_staged_file_at(directory_fd, recovery):
            return False
        os.replace(
            recovery.name,
            target,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        installed = _safe_target_snapshot_at(directory_fd, target)
        return (
            installed is not None
            and installed.exists
            and installed.file == recovery.file
            and _read_staged_payload(recovery) == payload
        )
    except OSError:
        return False
    finally:
        if recovery is not None:
            _close_quietly(recovery.descriptor)


def _file_snapshot(metadata: os.stat_result) -> _FileSnapshot:
    return _FileSnapshot((metadata.st_dev, metadata.st_ino), metadata.st_size)


def _staged_descriptor_identity_matches(
    staged: _StagedFile | _StagedPath,
) -> bool:
    try:
        metadata = os.fstat(staged.descriptor)
    except OSError:
        return False
    return _safe_file(metadata) and _file_snapshot(metadata) == staged.file


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

    opened_root = _open_windows_directory_chain(session.root)
    if opened_root is None:
        return session._warn(ObservabilityWarning.PATH_UNSAFE)
    session._root_fd, session._ancestor_fds = opened_root
    session._root_identity = _directory_fd_identity(session._root_fd)
    if (
        session._root_identity is None
        or _directory_identity(session.root) != session._root_identity
    ):
        session.close()
        return session._warn(ObservabilityWarning.PATH_UNSAFE)
    prepared = _prepare_namespace_path(session.root)
    if prepared is None:
        session.close()
        return session._warn(ObservabilityWarning.PATH_UNSAFE)
    namespace, root_identity, namespace_identity = prepared
    if root_identity != session._root_identity:
        session.close()
        return session._warn(ObservabilityWarning.PATH_UNSAFE)
    session.namespace = namespace
    session._namespace_identity = namespace_identity
    session._namespace_fd = _open_windows_directory(namespace)
    if (
        session._namespace_fd is None
        or _directory_fd_identity(session._namespace_fd) != namespace_identity
        or not session._safe_namespace()
    ):
        session.close()
        return session._warn(ObservabilityWarning.PATH_UNSAFE)
    descriptor = _open_lock_path(
        namespace / _LOCK_NAME,
        session._safe_namespace,
        session._namespace_fd,
    )
    if descriptor is None:
        session.close()
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
            descriptor, namespace / _LOCK_NAME, session._namespace_fd
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
    session.close()
    return session._warn(warning)


def _open_windows_directory(path: Path) -> int | None:
    """Open a directory handle which prevents Windows path substitution."""

    inspected = _lstat(path)
    if not _safe_directory(inspected):
        return None
    descriptor: int | None = None
    try:
        if os.name == "nt":
            descriptor = _open_windows_directory_native(path)
        else:
            descriptor = os.open(
                path,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
        if descriptor is None:
            return None
        opened = os.fstat(descriptor)
        current = _lstat(path)
        if (
            not _safe_directory(opened)
            or not _safe_directory(current)
            or inspected is None
            or current is None
            or (inspected.st_dev, inspected.st_ino) != (opened.st_dev, opened.st_ino)
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
        ):
            return None
        result = descriptor
        descriptor = None
        return result
    except OSError:
        return None
    finally:
        if descriptor is not None:
            _close_quietly(descriptor)


def _open_windows_directory_chain(path: Path) -> tuple[int, list[int]] | None:
    """Pin every Windows ancestor before accepting the evidence root."""

    if os.name != "nt":
        descriptor = _open_posix_directory_chain(path)
        return (descriptor, []) if descriptor is not None else None
    if not path.is_absolute() or not path.anchor:
        return None
    pinned: list[int] = []
    completed = False
    try:
        current = Path(path.anchor)
        anchor = _open_windows_directory(current)
        if anchor is None:
            return None
        pinned.append(anchor)
        for component in path.parts[1:]:
            if component in {"", ".", ".."} or not _exact_path_component(
                current, component
            ):
                return None
            current = current / component
            child = _open_windows_directory(current)
            if child is None:
                return None
            pinned.append(child)
        final = pinned.pop()
        completed = True
        return final, pinned
    finally:
        if not completed:
            while pinned:
                _close_quietly(pinned.pop())


def _exact_path_component(parent: Path, component: str) -> bool:
    try:
        matches = [
            entry.name
            for entry in parent.iterdir()
            if entry.name.casefold() == component.casefold()
        ]
    except OSError:
        return False
    return matches == [component]


def _open_windows_directory_native(  # pragma: no cover - Windows CI
    path: Path,
) -> int | None:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    handle = create_file(
        str(path),
        0x0080 | 0x0001,  # FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY
        0x0001 | 0x0002,  # FILE_SHARE_READ | FILE_SHARE_WRITE; deny delete/rename
        None,
        3,  # OPEN_EXISTING
        0x02000000 | 0x00200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        return None
    try:
        open_osfhandle: Callable[[int, int], int]
        open_osfhandle = msvcrt.open_osfhandle  # type: ignore[attr-defined]
        return int(open_osfhandle(int(handle), os.O_RDONLY))
    except OSError:
        close_handle(handle)
        return None


def _open_lock_path(
    path: Path,
    parent_is_safe: Callable[[], bool],
    directory_fd: int | None = None,
) -> int | None:
    descriptor: int | None = None
    try:
        if not _canonical_child_safe_path(path, directory_fd):
            return None
        try:
            before = _windows_child_lstat(directory_fd, path)
        except FileNotFoundError:
            before = None
        except OSError:
            return None
        if before is not None and (not _safe_file(before) or not _single_link(before)):
            return None
        if not parent_is_safe():
            return None
        flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        if before is None:
            flags |= os.O_CREAT | os.O_EXCL
        descriptor = _open_windows_child(directory_fd, path, flags, 0o600)
        opened = os.fstat(descriptor)
        at_path = _windows_child_lstat(directory_fd, path)
        if (
            not _canonical_child_safe_path(path, directory_fd)
            or not _safe_file(opened)
            or not _single_link(opened)
            or not _safe_file(at_path)
            or not _single_link(at_path)
            or _file_snapshot(opened).identity != _file_snapshot(at_path).identity
            or (
                before is not None
                and _file_snapshot(before).identity != _file_snapshot(opened).identity
            )
            or not parent_is_safe()
        ):
            return None
        if not parent_is_safe() or not _same_open_file_path(
            descriptor, path, directory_fd
        ):
            return None
        result = descriptor
        descriptor = None
        return result
    except Exception:
        return None
    finally:
        if descriptor is not None:
            _close_quietly(descriptor)


def _same_open_file_path(
    descriptor: int, path: Path, directory_fd: int | None = None
) -> bool:
    if not _canonical_child_safe_path(path, directory_fd):
        return False
    try:
        opened = os.fstat(descriptor)
        at_path = _windows_child_lstat(directory_fd, path)
    except OSError:
        return False
    return (
        _safe_file(opened)
        and _single_link(opened)
        and _safe_file(at_path)
        and _single_link(at_path)
        and _file_snapshot(opened).identity == _file_snapshot(at_path).identity
    )


def _open_windows_child(
    directory_fd: int | None,
    path: Path,
    flags: int,
    mode: int,
    *,
    delete_access: bool = False,
) -> int:
    if _uses_native_windows_paths() and directory_fd is not None:
        return _open_windows_relative_native(
            directory_fd, path.name, flags, delete_access=delete_access
        )
    if directory_fd is None:
        return os.open(path, flags, mode)
    return os.open(path.name, flags, mode, dir_fd=directory_fd)


def _windows_child_lstat(directory_fd: int | None, path: Path) -> os.stat_result:
    if _uses_native_windows_paths() and directory_fd is not None:
        return _stat_windows_relative_native(directory_fd, path.name)
    if directory_fd is None:
        return path.lstat()
    return os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)


def _replace_windows_child(directory_fd: int, staged: _StagedPath, target: str) -> None:
    if _uses_native_windows_paths():
        _replace_windows_relative_native(directory_fd, staged, target)
        return
    os.replace(
        staged.path.name,
        target,
        src_dir_fd=directory_fd,
        dst_dir_fd=directory_fd,
    )


def _uses_native_windows_paths() -> bool:
    return os.name == "nt"


def _open_windows_relative_native(  # pragma: no cover - Windows CI
    directory_fd: int,
    name: str,
    flags: int,
    *,
    delete_access: bool = False,
) -> int:
    desired_access = 0x00100080  # SYNCHRONIZE | FILE_READ_ATTRIBUTES
    if flags & os.O_RDWR:
        desired_access |= 0x80000000 | 0x40000000  # GENERIC_READ | GENERIC_WRITE
    elif flags & os.O_WRONLY:
        desired_access |= 0x40000000  # GENERIC_WRITE
    else:
        desired_access |= 0x80000000  # GENERIC_READ
    if delete_access:
        desired_access |= 0x00010000  # DELETE
    disposition = 1  # FILE_OPEN
    if flags & os.O_CREAT:
        disposition = 2 if flags & os.O_EXCL else 3  # FILE_CREATE / FILE_OPEN_IF
    handle = _nt_create_relative_handle(
        directory_fd,
        name,
        desired_access=desired_access,
        share_access=0x0001 | 0x0002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
        disposition=disposition,
    )
    return _windows_fd_from_handle(handle, flags)


def _stat_windows_relative_native(  # pragma: no cover - Windows CI
    directory_fd: int, name: str
) -> os.stat_result:
    handle = _nt_create_relative_handle(
        directory_fd,
        name,
        desired_access=0x00100080,  # SYNCHRONIZE | FILE_READ_ATTRIBUTES
        share_access=0x0001 | 0x0002 | 0x0004,
        disposition=1,
    )
    descriptor = _windows_fd_from_handle(handle, os.O_RDONLY)
    try:
        return os.fstat(descriptor)
    finally:
        _close_quietly(descriptor)


def _windows_directory_path(directory_fd: int) -> str:  # pragma: no cover - Windows CI
    """Resolve the live path backing an open directory handle."""

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    get_final_path = kernel32.GetFinalPathNameByHandleW
    get_final_path.argtypes = (
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    get_final_path.restype = wintypes.DWORD
    handle = wintypes.HANDLE(_windows_handle_from_fd(directory_fd))
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_final_path(handle, buffer, len(buffer), 0)
    if length == 0 or length >= len(buffer):
        raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
    return buffer.value


def _replace_windows_relative_native(  # pragma: no cover - Windows CI
    directory_fd: int, staged: _StagedPath, target: str
) -> None:
    import ctypes
    from ctypes import wintypes

    opened = os.fstat(staged.descriptor)
    if (
        not _safe_file(opened)
        or not _single_link(opened)
        or _file_snapshot(opened) != staged.file
        or _read_staged_payload(staged) != staged.payload
    ):
        raise OSError("staged observability handle changed before rename")
    directory_path = _windows_directory_path(directory_fd)
    source_path = os.path.join(directory_path, staged.path.name)
    target_path = os.path.join(directory_path, target)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    move_file = kernel32.MoveFileExW
    move_file.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
    move_file.restype = wintypes.BOOL
    move_file_replace_existing = 0x1
    move_file_write_through = 0x8
    if not move_file(
        source_path,
        target_path,
        move_file_replace_existing | move_file_write_through,
    ):
        raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]


def _discard_windows_staged_handle(  # pragma: no cover - Windows CI
    descriptor: int, expected_identity: tuple[int, int]
) -> None:
    import ctypes
    from ctypes import wintypes

    try:
        metadata = os.fstat(descriptor)
        if (
            not _safe_file(metadata)
            or _file_snapshot(metadata).identity != expected_identity
        ):
            return

        class _FileDispositionInformation(ctypes.Structure):
            _fields_ = (("delete_file", wintypes.BOOLEAN),)

        information = _FileDispositionInformation(1)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        set_information = kernel32.SetFileInformationByHandle
        set_information.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        )
        set_information.restype = wintypes.BOOL
        if not set_information(
            wintypes.HANDLE(_windows_handle_from_fd(descriptor)),
            4,  # FileDispositionInfo
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
    except OSError:
        return


def _nt_create_relative_handle(  # pragma: no cover - Windows CI
    directory_fd: int,
    name: str,
    *,
    desired_access: int,
    share_access: int,
    disposition: int,
) -> int:
    import ctypes
    from ctypes import wintypes

    if not name or "\\" in name or "/" in name or name in {".", ".."}:
        raise OSError("unsafe Windows child name")

    class _UnicodeString(ctypes.Structure):
        _fields_ = (
            ("length", wintypes.USHORT),
            ("maximum_length", wintypes.USHORT),
            ("buffer", wintypes.LPWSTR),
        )

    class _ObjectAttributes(ctypes.Structure):
        _fields_ = (
            ("length", wintypes.ULONG),
            ("root_directory", wintypes.HANDLE),
            ("object_name", ctypes.POINTER(_UnicodeString)),
            ("attributes", wintypes.ULONG),
            ("security_descriptor", wintypes.LPVOID),
            ("security_quality_of_service", wintypes.LPVOID),
        )

    class _IoStatusBlock(ctypes.Structure):
        _fields_ = (
            ("status", wintypes.LPVOID),
            ("information", ctypes.c_size_t),
        )

    name_buffer = ctypes.create_unicode_buffer(name)
    length = len(name.encode("utf-16-le"))
    unicode_name = _UnicodeString(
        length, length + 2, ctypes.cast(name_buffer, wintypes.LPWSTR)
    )
    attributes = _ObjectAttributes(
        ctypes.sizeof(_ObjectAttributes),
        wintypes.HANDLE(_windows_handle_from_fd(directory_fd)),
        ctypes.pointer(unicode_name),
        0x40,  # OBJ_CASE_INSENSITIVE
        None,
        None,
    )
    io_status = _IoStatusBlock()
    result_handle = wintypes.HANDLE()
    ntdll = ctypes.WinDLL("ntdll")  # type: ignore[attr-defined]
    nt_create_file = ntdll.NtCreateFile
    nt_create_file.argtypes = (
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        ctypes.POINTER(_ObjectAttributes),
        ctypes.POINTER(_IoStatusBlock),
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    nt_create_file.restype = wintypes.LONG
    status = int(
        nt_create_file(
            ctypes.byref(result_handle),
            desired_access,
            ctypes.byref(attributes),
            ctypes.byref(io_status),
            None,
            0x80,  # FILE_ATTRIBUTE_NORMAL
            share_access,
            disposition,
            0x00000020 | 0x00000040 | 0x00200000,
            None,
            0,
        )
    )
    if status < 0:
        _raise_windows_status(status, name)
    if result_handle.value is None:
        raise OSError("NtCreateFile returned no handle")
    return int(result_handle.value)


def _windows_handle_from_fd(  # pragma: no cover - Windows CI
    descriptor: int,
) -> int:
    import msvcrt

    get_osfhandle: Callable[[int], int]
    get_osfhandle = msvcrt.get_osfhandle  # type: ignore[attr-defined]
    return int(get_osfhandle(descriptor))


def _windows_fd_from_handle(  # pragma: no cover - Windows CI
    handle: int, flags: int
) -> int:
    import msvcrt

    if flags & os.O_RDWR:
        descriptor_flags = os.O_RDWR
    elif flags & os.O_WRONLY:
        descriptor_flags = os.O_WRONLY
    else:
        descriptor_flags = os.O_RDONLY
    descriptor_flags |= getattr(os, "O_BINARY", 0)
    try:
        open_osfhandle: Callable[[int, int], int]
        open_osfhandle = msvcrt.open_osfhandle  # type: ignore[attr-defined]
        return int(open_osfhandle(handle, descriptor_flags))
    except Exception:
        _close_windows_handle(handle)
        raise


def _raise_windows_status(  # pragma: no cover - Windows CI
    status: int, name: str
) -> None:
    import ctypes
    from ctypes import wintypes

    ntdll = ctypes.WinDLL("ntdll")  # type: ignore[attr-defined]
    convert = ntdll.RtlNtStatusToDosError
    convert.argtypes = (wintypes.LONG,)
    convert.restype = wintypes.ULONG
    error = int(convert(status))
    if error in {2, 3}:
        raise FileNotFoundError(error, "Windows child does not exist", name)
    if error in {80, 183}:
        raise FileExistsError(error, "Windows child already exists", name)
    raise OSError(error, "Windows relative file operation failed", name)


def _close_windows_handle(  # pragma: no cover - Windows CI
    handle: int,
) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    close_handle(wintypes.HANDLE(handle))


def _single_link(metadata: os.stat_result) -> bool:
    links = getattr(metadata, "st_nlink", None)
    return links is None or links == 1


def _stage_path(session: RefreshSession, payload: bytes) -> _StagedPath | None:
    """Create a pinned staged file and validate it before writing any bytes."""

    if (
        session.namespace is None
        or session._namespace_fd is None
        or not session._safe_namespace()
    ):
        return None
    path = session.namespace / f".release-gate-{secrets.token_hex(12)}"
    if not _canonical_child_available(session._namespace_fd, path.name):
        return None
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    opened_identity: tuple[int, int] | None = None
    completed = False
    try:
        if not session._safe_namespace():
            return None
        descriptor = _open_windows_child(
            session._namespace_fd,
            path,
            flags,
            0o600,
            delete_access=True,
        )
        opened = os.fstat(descriptor)
        at_path = _windows_child_lstat(session._namespace_fd, path)
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
        _write_descriptor(descriptor, payload)
        os.fsync(descriptor)
        opened_after = os.fstat(descriptor)
        after = _windows_child_lstat(session._namespace_fd, path)
        if (
            not _canonical_child_exact(session._namespace_fd, path.name)
            or not _safe_file(opened_after)
            or not _single_link(opened_after)
            or not _safe_file(after)
            or not _single_link(after)
            or _file_snapshot(opened_after).identity != opened_identity
            or _file_snapshot(after).identity != opened_identity
            or _file_snapshot(opened_after) != _file_snapshot(after)
            or after.st_size != len(payload)
            or not session._safe_namespace()
        ):
            return None
        completed = True
        staged = _StagedPath(
            path,
            _file_snapshot(after),
            descriptor,
            payload,
            hashlib.sha256(payload).hexdigest(),
        )
        descriptor = None
        return staged
    except OSError:
        return None
    finally:
        if descriptor is not None:
            try:
                if (
                    not completed
                    and opened_identity is not None
                    and _uses_native_windows_paths()
                ):
                    _discard_windows_staged_handle(descriptor, opened_identity)
            finally:
                _close_quietly(descriptor)


def _path_has_identity(
    path: Path, identity: tuple[int, int], directory_fd: int | None = None
) -> bool:
    try:
        metadata = _windows_child_lstat(directory_fd, path)
    except OSError:
        return False
    return (
        _safe_file(metadata)
        and _single_link(metadata)
        and _file_snapshot(metadata).identity == identity
    )


def _same_staged_path(session: RefreshSession, staged: _StagedPath) -> bool:
    try:
        opened = os.fstat(staged.descriptor)
    except OSError:
        return False
    return (
        session._safe_namespace()
        and session._namespace_fd is not None
        and _canonical_child_exact(session._namespace_fd, staged.path.name)
        and _safe_file(opened)
        and _single_link(opened)
        and _file_snapshot(opened) == staged.file
        and _read_staged_payload(staged) == staged.payload
        and _path_has_identity(staged.path, staged.file.identity, session._namespace_fd)
    )


def _close_staged_path(staged: _StagedPath, *, installed: bool) -> None:
    try:
        if not installed and _uses_native_windows_paths():
            _discard_windows_staged_handle(staged.descriptor, staged.file.identity)
    finally:
        _close_quietly(staged.descriptor)


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
            and _directory_identity(session.namespace) == session._namespace_identity
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
        _record_report_warnings(session, report)
        paths: dict[str, Path] = {}
        payloads = (
            (_DATA_NAME, render_json(report)),
            (_DASHBOARD_NAME, render_html(report)),
        )
        for name, payload in payloads:
            target = session.namespace / name
            assert session._namespace_fd is not None
            before = _safe_target_snapshot_path(target, session._namespace_fd)
            if before is None or not session._safe_namespace():
                session._warn(ObservabilityWarning.PATH_UNSAFE)
                continue
            staged = _stage_path(session, payload)
            if staged is None:
                session._warn(ObservabilityWarning.PATH_UNSAFE)
                continue
            renamed = False
            try:
                if (
                    not _same_staged_path(session, staged)
                    or _safe_target_snapshot_path(target, session._namespace_fd)
                    != before
                ):
                    session._warn(ObservabilityWarning.PATH_UNSAFE)
                    continue
                _replace_windows_child(session._namespace_fd, staged, target.name)
                renamed = True
                after = _safe_target_snapshot_path(target, session._namespace_fd)
                if (
                    after is None
                    or not after.exists
                    or after.file != staged.file
                    or _read_staged_payload(staged) != staged.payload
                    or not session._safe_namespace()
                ):
                    session._warn(ObservabilityWarning.PATH_UNSAFE)
                    restored, repair_renamed = _restore_staged_path(
                        session, target, staged, installed=True
                    )
                    renamed = renamed or repair_renamed
                    if restored:
                        _fsync_directory_path(session)
                        paths[name] = target
                    else:
                        session._warn(ObservabilityWarning.PUBLISH_FAILED)
                    continue
                _fsync_directory_path(session)
                paths[name] = target
            except OSError:
                session._warn(ObservabilityWarning.PATH_UNSAFE)
                restored, repair_renamed = _restore_staged_path(
                    session, target, staged, installed=renamed
                )
                renamed = renamed or repair_renamed
                if restored:
                    _fsync_directory_path(session)
                    paths[name] = target
                else:
                    session._warn(ObservabilityWarning.PUBLISH_FAILED)
            finally:
                _close_staged_path(staged, installed=renamed)
        session._result = ObservabilityResult(
            session.result.snapshot_path,
            paths.get(_DASHBOARD_NAME),
            paths.get(_DATA_NAME),
            session.result.warnings,
        )
    except Exception:
        session._warn(ObservabilityWarning.PUBLISH_FAILED)
    return session.result


def _safe_target_snapshot_path(
    path: Path, directory_fd: int | None = None
) -> _TargetSnapshot | None:
    if not _canonical_child_safe_path(path, directory_fd):
        return None
    try:
        metadata = _windows_child_lstat(directory_fd, path)
    except FileNotFoundError:
        return _TargetSnapshot(False, None)
    except OSError:
        return None
    if not _safe_file(metadata) or not _single_link(metadata):
        return None
    return _TargetSnapshot(True, _file_snapshot(metadata))


def _canonical_child_safe_path(path: Path, directory_fd: int | None) -> bool:
    if directory_fd is not None:
        return _canonical_child_safe(directory_fd, path.name)
    try:
        names = [entry.name for entry in path.parent.iterdir()]
    except OSError:
        return False
    matches = [entry for entry in names if entry.casefold() == path.name.casefold()]
    return matches in ([], [path.name])


def _restore_staged_path(
    session: RefreshSession,
    target: Path,
    trusted: _StagedPath,
    *,
    installed: bool,
) -> tuple[bool, bool]:
    if (
        not _staged_descriptor_identity_matches(trusted)
        or session._namespace_fd is None
    ):
        return False, False
    if not _rewrite_staged_payload(trusted):
        return False, False
    if installed:
        after = _safe_target_snapshot_path(target, session._namespace_fd)
        installed_is_trusted = (
            after is not None and after.exists and after.file == trusted.file
        )
        if installed_is_trusted:
            return (
                _read_staged_payload(trusted) == trusted.payload
                and session._safe_namespace(),
                False,
            )
        return _restore_staged_path_by_replacement(
            session, target, trusted.payload
        ), False
    if not _same_staged_path(session, trusted):
        return False, False
    renamed = False
    try:
        _replace_windows_child(session._namespace_fd, trusted, target.name)
        renamed = True
        after = _safe_target_snapshot_path(target, session._namespace_fd)
        repaired = (
            after is not None
            and after.exists
            and after.file == trusted.file
            and _read_staged_payload(trusted) == trusted.payload
            and session._safe_namespace()
        )
        return repaired, renamed
    except OSError:
        return False, renamed


def _rewrite_staged_payload(staged: _StagedPath) -> bool:
    if not _staged_descriptor_identity_matches(staged):
        return False
    try:
        _write_descriptor(staged.descriptor, staged.payload)
        os.ftruncate(staged.descriptor, len(staged.payload))
        os.fsync(staged.descriptor)
    except OSError:
        return False
    return (
        _staged_descriptor_identity_matches(staged)
        and _read_staged_payload(staged) == staged.payload
    )


def _restore_staged_path_by_replacement(
    session: RefreshSession, target: Path, payload: bytes
) -> bool:
    if session._namespace_fd is None:
        return False
    recovery = _stage_path(session, payload)
    if recovery is None:
        return False
    renamed = False
    try:
        if not _same_staged_path(session, recovery):
            return False
        _replace_windows_child(session._namespace_fd, recovery, target.name)
        renamed = True
        after = _safe_target_snapshot_path(target, session._namespace_fd)
        return (
            after is not None
            and after.exists
            and after.file == recovery.file
            and _read_staged_payload(recovery) == payload
            and session._safe_namespace()
        )
    except OSError:
        return False
    finally:
        _close_staged_path(recovery, installed=renamed)
