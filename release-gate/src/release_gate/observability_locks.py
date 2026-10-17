"""Platform dispatch for observability lock operations."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, cast

_LOCK_OFFSET = 0


def uses_windows_backend() -> bool:
    return os.name == "nt"


def try_lock(descriptor: int, windows_lock: Callable[[int, bool], None]) -> bool:
    if uses_windows_backend():
        try:
            windows_lock(descriptor, True)
        except OSError:
            return False
        return True

    import fcntl

    posix_locker = cast(Any, fcntl)

    try:
        posix_locker.lockf(
            descriptor,
            posix_locker.LOCK_EX | posix_locker.LOCK_NB,
            1,
            _LOCK_OFFSET,
            os.SEEK_SET,
        )
        return True
    except (OSError, ValueError):
        return False


def unlock(descriptor: int, windows_lock: Callable[[int, bool], None]) -> None:
    if uses_windows_backend():
        windows_lock(descriptor, False)
        return

    import fcntl

    posix_locker = cast(Any, fcntl)

    posix_locker.lockf(descriptor, posix_locker.LOCK_UN, 1, _LOCK_OFFSET, os.SEEK_SET)
