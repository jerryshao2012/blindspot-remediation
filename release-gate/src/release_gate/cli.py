"""Command-line entry point."""

from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the release-gate CLI.

    Subcommands are added in the CLI implementation slice. Keeping the entry
    point importable here makes built distributions independently smokeable.
    """
    del argv
    return 0
