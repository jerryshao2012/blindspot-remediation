"""Initialization command orchestration for the standalone release gate."""

from __future__ import annotations

import os
from pathlib import Path

from release_gate.config import MAX_CONFIG_BYTES, ConfigError, load_config_bytes


def init_repository(path: Path, *, from_config: Path | None = None) -> int:
    """Create the policy and evidence ignore entry transactionally."""
    from release_gate import cli

    policy_bytes = (
        read_approved_config(from_config)
        if from_config is not None
        else cli._INITIAL_POLICY.encode("utf-8")
    )
    load_config_bytes(
        policy_bytes,
        source=str(from_config) if from_config is not None else "<generic draft>",
    )
    repository = cli._repository(path)
    policy = repository / cli._POLICY_NAME
    ignore = repository / ".gitignore"
    cli._require_absent_policy(policy)
    ignore_snapshot = cli._snapshot_ignore(ignore)

    policy_stage = None
    locked_ignore = None
    try:
        policy_stage = cli._stage_policy(repository, policy_bytes)
        cli._transaction_hook("before-policy-create", policy)
        cli._require_absent_policy(policy)
        cli._transaction_hook("before-ignore-write", ignore)
        cli._require_absent_policy(policy)
        locked_ignore = cli._open_locked_ignore(ignore, ignore_snapshot)
        cli._append_locked_ignore(ignore, locked_ignore)
        cli._publish_policy(
            policy_stage,
            policy,
            policy_bytes,
            ignore_path=ignore,
            locked_ignore=locked_ignore,
        )
    except Exception as error:
        if locked_ignore is not None:
            cli._rollback_locked_ignore(ignore, locked_ignore)
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
            cli._close_locked_ignore(locked_ignore)
        if policy_stage is not None:
            cli._discard_policy_stage(policy_stage)
    try:
        print(f"INITIALIZED: {policy}")
    except (OSError, UnicodeError):
        pass
    return 0


def read_approved_config(path: Path) -> bytes:
    """Read and validate an approved config without following replacement paths."""
    from release_gate import cli

    try:
        inspected = os.lstat(path)
    except OSError as error:
        raise ConfigError(
            f"{path}: unable to read configuration: {error.strerror}"
        ) from error
    if not cli._is_regular_non_reparse(inspected):
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
        if not cli._is_regular_non_reparse(opened) or cli._identity(
            opened
        ) != cli._identity(inspected):
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
        if not cli._is_regular_non_reparse(final_path) or cli._identity(
            final_path
        ) != cli._identity(opened):
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
