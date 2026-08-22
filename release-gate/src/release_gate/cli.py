"""Command-line entry point for the standalone release gate."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

from release_gate import __version__
from release_gate.config import (
    MAX_CONFIG_BYTES,
    ConfigError,
    load_config,
    load_config_bytes,
)
from release_gate.engine import GateInputError, run_gate
from release_gate.repair.controller import (
    apply_repair,
    approve_repair,
    cancel_repair,
    evaluate_repair,
    finalize_repair,
    request_repair,
    start_repair,
)
from release_gate.repair.workspace import RepairWorkspaceError

_POLICY_NAME = ".release-gate.yaml"
_EVIDENCE_IGNORE = "/.release-gate/runs/"
_EVIDENCE_IGNORE_BYTES = f"{_EVIDENCE_IGNORE}\n".encode()
_INITIAL_POLICY = """\
version: 1

scope:
  allowed_paths:
    - "**"
  forbidden_paths: []
  review_required_paths:
    - "/.release-gate.yaml"

prepare: []

checks:
  - id: configure-me
    mode: candidate
    severity: advisory
    argv: ["release-gate-configure-me"]
"""


class _UsageError(ValueError):
    pass


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _UsageError(message)


@dataclass(frozen=True, slots=True)
class _FileIdentity:
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class _IgnoreSnapshot:
    exists: bool
    identity: _FileIdentity | None
    content: bytes
    length: int
    sha256: str
    append: bytes


@dataclass(slots=True)
class _WriteJournal:
    identity: _FileIdentity | None = None
    written: int = 0
    created: bool = False


@dataclass(frozen=True, slots=True)
class _PolicyStage:
    directory: Path
    directory_identity: _FileIdentity
    path: Path
    identity: _FileIdentity
    descriptor: int


@dataclass(slots=True)
class _LockedIgnore:
    descriptor: int
    snapshot: _IgnoreSnapshot
    journal: _WriteJournal


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and return a stable release-gate exit code."""

    parser = _build_parser()
    try:
        arguments = parser.parse_args(argv)
        if arguments.version:
            print(f"release-gate {__version__}")
            return 0
        if arguments.command == "init":
            source = Path(arguments.from_config) if arguments.from_config else None
            return _init(Path(arguments.repo), from_config=source)
        if arguments.command == "validate":
            return _validate(Path(arguments.repo))
        if arguments.command == "run":
            outcome = run_gate(
                Path(arguments.repo),
                base=arguments.base,
                output=Path(arguments.output) if arguments.output else None,
                run_id=arguments.run_id,
            )
            for label, path in (
                ("SNAPSHOT", outcome.snapshot_path),
                ("DASHBOARD", outcome.dashboard_path),
                ("OBSERVABILITY_DATA", outcome.observability_data_path),
            ):
                if path is not None and path.exists():
                    print(f"{label}: {path.absolute()}", file=sys.stderr)
            for warning in outcome.observability_warnings:
                print(f"WARNING: {warning.value}", file=sys.stderr)
            print(f"VERDICT: {outcome.verdict.value}")
            print(f"RESULT: {outcome.result_path}")
            return outcome.exit_code
        if arguments.command.startswith("repair-"):
            try:
                if arguments.command == "repair-start":
                    repair_outcome = start_repair(
                        Path(arguments.repo),
                        base=arguments.base,
                        output=Path(arguments.output) if arguments.output else None,
                        session_id=arguments.session_id,
                    )
                    print(f"REPAIR_SESSION: {repair_outcome.session_dir.absolute()}")
                    print(f"REPAIR_STATE: {repair_outcome.state.value}")
                    print(f"NEXT_ACTION: {repair_outcome.next_action}")
                    if (
                        repair_outcome.approval_request_path
                        and repair_outcome.approval_request_path.exists()
                    ):
                        req_path = (
                            repair_outcome.approval_request_path.absolute()
                        )
                        print(f"REPAIR_REQUEST: {req_path}")
                    if (
                        repair_outcome.summary_path
                        and repair_outcome.summary_path.exists()
                    ):
                        print(
                            f"REPAIR_SUMMARY: {repair_outcome.summary_path.absolute()}"
                        )
                    return 0
                if arguments.command == "repair-approve":
                    repair_outcome = approve_repair(
                        Path(arguments.session),
                        Path(arguments.approval),
                    )
                    print(f"REPAIR_SESSION: {repair_outcome.session_dir.absolute()}")
                    print(f"REPAIR_STATE: {repair_outcome.state.value}")
                    print(f"NEXT_ACTION: {repair_outcome.next_action}")
                    return 0
                if arguments.command == "repair-request":
                    req_info = request_repair(Path(arguments.session))
                    print(f"REPAIR_SESSION: {Path(arguments.session).absolute()}")
                    print(f"REPAIR_STATE: {req_info['state']}")
                    print(f"NEXT_ACTION: {req_info['next_action']}")
                    print(f"WORKSPACE: {req_info['workspace_path']}")
                    print(f"APPROVED_PATHS: {', '.join(req_info['approved_paths'])}")
                    print(f"FAILED_CHECKS: {', '.join(req_info['failed_check_ids'])}")
                    return 0
                if arguments.command == "repair-evaluate":
                    repair_outcome = evaluate_repair(Path(arguments.session))
                    print(f"REPAIR_SESSION: {repair_outcome.session_dir.absolute()}")
                    print(f"REPAIR_STATE: {repair_outcome.state.value}")
                    print(f"NEXT_ACTION: {repair_outcome.next_action}")
                    if (
                        repair_outcome.summary_path
                        and repair_outcome.summary_path.exists()
                    ):
                        print(
                            f"REPAIR_SUMMARY: {repair_outcome.summary_path.absolute()}"
                        )
                    return 0
                if arguments.command == "repair-finalize":
                    repair_outcome = finalize_repair(Path(arguments.session))
                    print(f"REPAIR_SESSION: {repair_outcome.session_dir.absolute()}")
                    print(f"REPAIR_STATE: {repair_outcome.state.value}")
                    print(f"NEXT_ACTION: {repair_outcome.next_action}")
                    if (
                        repair_outcome.summary_path
                        and repair_outcome.summary_path.exists()
                    ):
                        print(
                            f"REPAIR_SUMMARY: {repair_outcome.summary_path.absolute()}"
                        )
                    return 0
                if arguments.command == "repair-apply":
                    repair_outcome = apply_repair(
                        Path(arguments.session),
                        Path(arguments.approval),
                    )
                    print(f"REPAIR_SESSION: {repair_outcome.session_dir.absolute()}")
                    print(f"REPAIR_STATE: {repair_outcome.state.value}")
                    print(f"NEXT_ACTION: {repair_outcome.next_action}")
                    if (
                        repair_outcome.summary_path
                        and repair_outcome.summary_path.exists()
                    ):
                        print(
                            f"REPAIR_SUMMARY: {repair_outcome.summary_path.absolute()}"
                        )
                    return 0
                if arguments.command == "repair-cancel":
                    repair_outcome = cancel_repair(Path(arguments.session))
                    print(f"REPAIR_SESSION: {repair_outcome.session_dir.absolute()}")
                    print(f"REPAIR_STATE: {repair_outcome.state.value}")
                    print(f"NEXT_ACTION: {repair_outcome.next_action}")
                    return 0
            except (ValueError, FileNotFoundError, RepairWorkspaceError) as error:
                print(f"ERROR: {error}", file=sys.stderr)
                return 3
        raise _UsageError("a command is required")
    except _UsageError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 3
    except (ConfigError, GateInputError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 3
    except Exception as error:
        print(f"ERROR: internal release-gate failure: {error}", file=sys.stderr)
        return 4


def _build_parser() -> _ArgumentParser:
    parser = _ArgumentParser(prog="release-gate")
    parser.add_argument("--version", action="store_true")
    commands = parser.add_subparsers(dest="command")
    init = commands.add_parser("init")
    init.add_argument("--repo", default=".", metavar="PATH")
    init.add_argument("--from-config", metavar="PATH")
    validate = commands.add_parser("validate")
    validate.add_argument("--repo", default=".", metavar="PATH")
    run = commands.add_parser("run")
    run.add_argument("--repo", default=".", metavar="PATH")
    run.add_argument("--base", required=True, metavar="REF")
    run.add_argument("--output", metavar="PATH")
    run.add_argument("--run-id", metavar="ID")

    repair_start = commands.add_parser("repair-start")
    repair_start.add_argument("--repo", default=".", metavar="PATH")
    repair_start.add_argument("--base", required=True, metavar="REF")
    repair_start.add_argument("--output", metavar="PATH")
    repair_start.add_argument("--session-id", metavar="ID")

    repair_approve = commands.add_parser("repair-approve")
    repair_approve.add_argument("--session", required=True, metavar="PATH")
    repair_approve.add_argument("--approval", required=True, metavar="PATH")

    repair_request = commands.add_parser("repair-request")
    repair_request.add_argument("--session", required=True, metavar="PATH")

    repair_evaluate = commands.add_parser("repair-evaluate")
    repair_evaluate.add_argument("--session", required=True, metavar="PATH")

    repair_finalize = commands.add_parser("repair-finalize")
    repair_finalize.add_argument("--session", required=True, metavar="PATH")

    repair_apply = commands.add_parser("repair-apply")
    repair_apply.add_argument("--session", required=True, metavar="PATH")
    repair_apply.add_argument("--approval", required=True, metavar="PATH")

    repair_cancel = commands.add_parser("repair-cancel")
    repair_cancel.add_argument("--session", required=True, metavar="PATH")

    return parser


def _repository(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ConfigError(f"{path}: repository path does not exist") from error
    if not resolved.is_dir():
        raise ConfigError(f"{resolved}: repository path is not a directory")
    return resolved


def _init(path: Path, *, from_config: Path | None = None) -> int:
    policy_bytes = (
        _read_approved_config(from_config)
        if from_config is not None
        else _INITIAL_POLICY.encode("utf-8")
    )
    load_config_bytes(
        policy_bytes,
        source=str(from_config) if from_config is not None else "<generic draft>",
    )
    repository = _repository(path)
    policy = repository / _POLICY_NAME
    ignore = repository / ".gitignore"
    _require_absent_policy(policy)
    ignore_snapshot = _snapshot_ignore(ignore)

    policy_stage: _PolicyStage | None = None
    locked_ignore: _LockedIgnore | None = None
    try:
        policy_stage = _stage_policy(repository, policy_bytes)
        _transaction_hook("before-policy-create", policy)
        _require_absent_policy(policy)
        _transaction_hook("before-ignore-write", ignore)
        _require_absent_policy(policy)
        locked_ignore = _open_locked_ignore(ignore, ignore_snapshot)
        _append_locked_ignore(ignore, locked_ignore)
        _publish_policy(
            policy_stage,
            policy,
            policy_bytes,
            ignore_path=ignore,
            locked_ignore=locked_ignore,
        )
    except Exception as error:
        if locked_ignore is not None:
            _rollback_locked_ignore(ignore, locked_ignore)
        if isinstance(error, ConfigError):
            raise
        if isinstance(error, OSError):
            message = error.strerror or str(error)
            raise ConfigError(
                f"{repository}: initialization failed: {message}"
            ) from error
        raise
    finally:
        if locked_ignore is not None:
            _close_locked_ignore(locked_ignore)
        if policy_stage is not None:
            _discard_policy_stage(policy_stage)
    # Publication is the commit point. Diagnostics after it are best effort so a
    # closed stdout cannot turn a committed initialization into an error result.
    try:
        print(f"INITIALIZED: {policy}")
    except (OSError, UnicodeError):
        pass
    return 0


def _read_approved_config(path: Path) -> bytes:
    try:
        inspected = os.lstat(path)
    except OSError as error:
        raise ConfigError(
            f"{path}: unable to read configuration: {error.strerror}"
        ) from error
    if not _is_regular_non_reparse(inspected):
        raise ConfigError(
            f"{path}: configuration source must be an ordinary non-reparse file"
        )
    if inspected.st_size > MAX_CONFIG_BYTES:
        raise ConfigError(f"{path}: configuration exceeds the 1 MiB UTF-8 limit")

    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ConfigError(
            f"{path}: unable to read configuration: {error.strerror}"
        ) from error
    try:
        opened = os.fstat(descriptor)
        if not _is_regular_non_reparse(opened) or _identity(opened) != _identity(
            inspected
        ):
            raise ConfigError(f"{path}: configuration source changed before reading")
        data = _read_bounded_descriptor(descriptor, MAX_CONFIG_BYTES)
        if len(data) > MAX_CONFIG_BYTES:
            raise ConfigError(f"{path}: configuration exceeds the 1 MiB UTF-8 limit")
        os.lseek(descriptor, 0, os.SEEK_SET)
        confirmation = _read_bounded_descriptor(descriptor, MAX_CONFIG_BYTES)
        final = os.fstat(descriptor)
        if (
            confirmation != data
            or _file_change_signature(final) != _file_change_signature(opened)
            or final.st_size != len(data)
        ):
            raise ConfigError(f"{path}: configuration changed while being read")
        try:
            final_path = os.lstat(path)
        except OSError as error:
            raise ConfigError(f"{path}: configuration source changed") from error
        if not _is_regular_non_reparse(final_path) or _identity(
            final_path
        ) != _identity(opened):
            raise ConfigError(f"{path}: configuration source changed")
    finally:
        os.close(descriptor)
    load_config_bytes(data, source=str(path))
    return data


def _read_bounded_descriptor(descriptor: int, limit: int) -> bytes:
    chunks: list[bytes] = []
    remaining = limit + 1
    while remaining:
        chunk = os.read(descriptor, min(remaining, 64 * 1024))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _file_change_signature(status: os.stat_result) -> tuple[int, int, int]:
    return (status.st_size, status.st_mtime_ns, status.st_ctime_ns)


def _require_absent_policy(path: Path) -> None:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as error:
        raise ConfigError(f"{path}: unable to inspect policy target") from error
    raise ConfigError(f"{path}: policy already exists; refusing to overwrite")


def _snapshot_ignore(path: Path) -> _IgnoreSnapshot:
    try:
        status = os.lstat(path)
    except FileNotFoundError:
        return _IgnoreSnapshot(
            exists=False,
            identity=None,
            content=b"",
            length=0,
            sha256=hashlib.sha256(b"").hexdigest(),
            append=_EVIDENCE_IGNORE_BYTES,
        )
    except OSError as error:
        raise ConfigError(f"{path}: unable to inspect Git ignore file") from error

    _require_regular_ignore(path, status)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ConfigError(f"{path}: unable to read Git ignore file") from error
    try:
        opened = os.fstat(descriptor)
        _require_regular_ignore(path, opened)
        if _identity(opened) != _identity(status):
            raise ConfigError(f"{path}: Git ignore file changed during inspection")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read()
        final = os.fstat(descriptor)
        if _identity(final) != _identity(opened) or final.st_size != len(content):
            raise ConfigError(f"{path}: Git ignore file changed during inspection")
        _require_path_identity(path, _identity(opened))
    finally:
        os.close(descriptor)

    entry = _EVIDENCE_IGNORE.encode()
    if entry in content.splitlines():
        append = b""
    else:
        prefix = b"" if not content or content.endswith((b"\n", b"\r")) else b"\n"
        append = prefix + _EVIDENCE_IGNORE_BYTES
    return _IgnoreSnapshot(
        exists=True,
        identity=_identity(opened),
        content=content,
        length=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        append=append,
    )


def _stage_policy(repository: Path, data: bytes) -> _PolicyStage:
    directory = Path(tempfile.mkdtemp(prefix=".release-gate-init-", dir=repository))
    try:
        directory_status = os.lstat(directory)
    except OSError as error:
        raise ConfigError(f"{repository}: unable to inspect policy stage") from error
    if not _is_directory_non_reparse(directory_status):
        raise ConfigError(f"{repository}: policy stage is not a safe directory")
    directory_identity = _identity(directory_status)
    path = directory / "policy"
    identity: _FileIdentity | None = None
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o666)
    except OSError as error:
        _discard_private_stage(
            directory,
            directory_identity=directory_identity,
            identity=None,
        )
        raise ConfigError(f"{repository}: unable to stage policy") from error
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise ConfigError(f"{repository}: staged policy is not a regular file")
        identity = _identity(status)
        journal = _WriteJournal()
        _write_all(descriptor, data, journal)
        os.fsync(descriptor)
        if journal.written != len(data):
            raise ConfigError(f"{repository}: unable to stage complete policy")
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        _discard_private_stage(
            directory,
            directory_identity=directory_identity,
            identity=identity,
        )
        raise
    if identity is None:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise ConfigError(f"{repository}: staged policy has no verified identity")
    return _PolicyStage(
        directory=directory,
        directory_identity=directory_identity,
        path=path,
        identity=identity,
        descriptor=descriptor,
    )


def _open_locked_ignore(path: Path, snapshot: _IgnoreSnapshot) -> _LockedIgnore:
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    journal = _WriteJournal(created=not snapshot.exists)
    descriptor: int
    if snapshot.exists:
        try:
            descriptor = os.open(path, flags)
        except OSError as error:
            raise ConfigError(f"{path}: unable to open Git ignore file") from error
    else:
        try:
            descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError as error:
            raise ConfigError(
                f"{path}: Git ignore file appeared during initialization"
            ) from error
        except OSError as error:
            raise ConfigError(f"{path}: unable to create Git ignore file") from error
    try:
        _acquire_advisory_lock(descriptor, path)
        status = os.fstat(descriptor)
        _require_regular_ignore(path, status)
        identity = _identity(status)
        journal.identity = identity
        if snapshot.exists:
            if identity != snapshot.identity:
                raise ConfigError(f"{path}: Git ignore file changed before update")
            existing = _read_descriptor(descriptor)
            if (
                len(existing) != snapshot.length
                or hashlib.sha256(existing).hexdigest() != snapshot.sha256
            ):
                raise ConfigError(f"{path}: Git ignore file changed before update")
        elif _read_descriptor(descriptor) != b"":
            raise ConfigError(f"{path}: new Git ignore file changed before update")
        _require_path_identity(path, identity)
        return _LockedIgnore(descriptor=descriptor, snapshot=snapshot, journal=journal)
    except Exception:
        _release_advisory_lock(descriptor)
        os.close(descriptor)
        raise


def _append_locked_ignore(path: Path, locked: _LockedIgnore) -> None:
    if not locked.snapshot.append:
        return
    identity = locked.journal.identity
    if identity is None:
        raise ConfigError(f"{path}: Git ignore file has no verified identity")
    os.lseek(locked.descriptor, 0, os.SEEK_END)
    _write_all(locked.descriptor, locked.snapshot.append, locked.journal)
    _transaction_hook("after-ignore-write", path)
    os.fsync(locked.descriptor)
    _require_path_identity(path, identity)


def _publish_policy(
    stage: _PolicyStage,
    path: Path,
    data: bytes,
    *,
    ignore_path: Path,
    locked_ignore: _LockedIgnore,
) -> None:
    _transaction_hook("before-policy-publish", path)
    _require_absent_policy(path)
    _require_stage_source(stage, path, data)
    # Keep this as the final validation before the atomic no-overwrite link.
    # Cooperative writers cannot pass the held advisory lock; a non-cooperating
    # replacement or byte change at this deterministic boundary is rejected.
    _require_locked_ignore_ready(ignore_path, locked_ignore)
    try:
        os.link(stage.path, path, follow_symlinks=False)
    except FileExistsError as error:
        raise ConfigError(
            f"{path}: policy already exists; refusing to overwrite"
        ) from error
    except OSError as error:
        raise ConfigError(f"{path}: unable to publish policy") from error


def _require_stage_source(stage: _PolicyStage, target: Path, data: bytes) -> None:
    _require_stage_directory(stage, target)
    status = os.fstat(stage.descriptor)
    if (
        _identity(status) != stage.identity
        or not _is_regular_non_reparse(status)
        or _read_descriptor(stage.descriptor) != data
    ):
        raise ConfigError(f"{target}: staged policy changed before publication")
    try:
        path_status = os.lstat(stage.path)
    except OSError as error:
        raise ConfigError(f"{target}: staged policy disappeared") from error
    if _identity(path_status) != stage.identity:
        raise ConfigError(f"{target}: staged policy changed before publication")
    _require_stage_directory(stage, target)


def _require_stage_directory(stage: _PolicyStage, target: Path) -> None:
    try:
        status = os.lstat(stage.directory)
    except OSError as error:
        raise ConfigError(f"{target}: policy staging directory disappeared") from error
    if _identity(status) != stage.directory_identity or not _is_directory_non_reparse(
        status
    ):
        raise ConfigError(f"{target}: policy staging directory changed")


def _require_locked_ignore_ready(path: Path, locked: _LockedIgnore) -> None:
    identity = locked.journal.identity
    if identity is None:
        raise ConfigError(f"{path}: Git ignore file has no verified identity")
    expected = locked.snapshot.content + locked.snapshot.append
    if locked.journal.written != len(locked.snapshot.append):
        raise ConfigError(f"{path}: Git ignore update is incomplete")
    status = os.fstat(locked.descriptor)
    if _identity(status) != identity or not _is_regular_non_reparse(status):
        raise ConfigError(f"{path}: Git ignore file changed before commit")
    _require_path_identity(path, identity)
    if _read_descriptor(locked.descriptor) != expected:
        raise ConfigError(f"{path}: Git ignore file changed before commit")
    final = os.fstat(locked.descriptor)
    if (
        _identity(final) != identity
        or not _is_regular_non_reparse(final)
        or final.st_size != len(expected)
    ):
        raise ConfigError(f"{path}: Git ignore file changed before commit")
    _require_path_identity(path, identity)


def _discard_policy_stage(stage: _PolicyStage) -> None:
    try:
        os.close(stage.descriptor)
    except OSError:
        pass
    _discard_private_stage(
        stage.directory,
        directory_identity=stage.directory_identity,
        identity=stage.identity,
    )


def _discard_private_stage(
    directory: Path,
    *,
    directory_identity: _FileIdentity,
    identity: _FileIdentity | None,
) -> None:
    if not _path_is_directory_identity(directory, directory_identity):
        return
    path = directory / "policy"
    if identity is not None:
        try:
            status = os.lstat(path)
            if _identity(status) == identity and _is_regular_non_reparse(status):
                os.unlink(path)
        except OSError:
            pass
    try:
        _transaction_hook("before-stage-rmdir", directory)
        if not _path_is_directory_identity(directory, directory_identity):
            return
        os.rmdir(directory)
    except Exception:
        pass


def _path_is_directory_identity(path: Path, identity: _FileIdentity) -> bool:
    try:
        status = os.lstat(path)
    except OSError:
        return False
    return _identity(status) == identity and _is_directory_non_reparse(status)


def _write_all(descriptor: int, data: bytes, journal: _WriteJournal) -> None:
    while journal.written < len(data):
        count = os.write(descriptor, data[journal.written :])
        if count <= 0:
            raise OSError("file write made no progress")
        journal.written += count


def _read_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 64 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _rollback_locked_ignore(path: Path, locked: _LockedIgnore) -> None:
    snapshot = locked.snapshot
    journal = locked.journal
    if journal.identity is None:
        return
    try:
        status = os.fstat(locked.descriptor)
        if _identity(status) != journal.identity or not _is_regular_non_reparse(status):
            return
        _require_path_identity(path, journal.identity)
        content = _read_descriptor(locked.descriptor)
        expected = snapshot.content + snapshot.append[: journal.written]
        if content != expected:
            return
        _transaction_hook("before-ignore-rollback", path)
        _require_path_identity(path, journal.identity)
        if _read_descriptor(locked.descriptor) != expected:
            return
        os.ftruncate(locked.descriptor, snapshot.length)
        os.fsync(locked.descriptor)
    except (ConfigError, OSError):
        return


def _close_locked_ignore(locked: _LockedIgnore) -> None:
    _release_advisory_lock(locked.descriptor)
    try:
        os.close(locked.descriptor)
    except OSError:
        pass


def _acquire_advisory_lock(descriptor: int, path: Path) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            windows_locker = cast(Any, msvcrt)
            windows_locker.locking(descriptor, windows_locker.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        raise ConfigError(
            f"{path}: Git ignore file is locked by another process"
        ) from error


def _release_advisory_lock(descriptor: int) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            windows_locker = cast(Any, msvcrt)
            windows_locker.locking(descriptor, windows_locker.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_UN)
    except OSError:
        pass


def _require_path_identity(path: Path, identity: _FileIdentity) -> None:
    try:
        status = os.lstat(path)
    except OSError as error:
        raise ConfigError(
            f"{path}: Git ignore file changed during initialization"
        ) from error
    _require_regular_ignore(path, status)
    if _identity(status) != identity:
        raise ConfigError(f"{path}: Git ignore file changed during initialization")


def _require_regular_ignore(path: Path, status: os.stat_result) -> None:
    if not _is_regular_non_reparse(status):
        raise ConfigError(
            f"{path}: Git ignore target must be an ordinary non-reparse file"
        )


def _is_regular_non_reparse(status: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(status, "st_file_attributes", 0)
    return stat.S_ISREG(status.st_mode) and not bool(attributes & reparse_flag)


def _is_directory_non_reparse(status: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(status, "st_file_attributes", 0)
    return stat.S_ISDIR(status.st_mode) and not bool(attributes & reparse_flag)


def _identity(status: os.stat_result) -> _FileIdentity:
    return _FileIdentity(device=status.st_dev, inode=status.st_ino)


def _transaction_hook(event: str, path: Path) -> None:
    del event, path


def _validate(path: Path) -> int:
    policy = _repository(path) / _POLICY_NAME
    load_config(policy)
    print(f"VALID: {policy}")
    return 0
