"""Platform dispatch for observability lock operations."""

from __future__ import annotations

import os
from collections.abc import Callable

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


def unlock(descriptor: int, windows_lock: Callable[[int, bool], None]) -> None:
    if uses_windows_backend():
        windows_lock(descriptor, False)
        return

    import fcntl

    fcntl.lockf(descriptor, fcntl.LOCK_UN, 1, _LOCK_OFFSET, os.SEEK_SET)
