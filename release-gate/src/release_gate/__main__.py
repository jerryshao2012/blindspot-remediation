"""Allows ``python -m release_gate`` as a fallback when the console-script
executable is unavailable (for example, blocked by endpoint security policy)."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
