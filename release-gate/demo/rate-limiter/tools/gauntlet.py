"""Cross-platform entry point for the rate-limiter quality gauntlet."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_step(label: str, arguments: Sequence[str]) -> int:
    print(f"=== {label} ===", flush=True)
    result = subprocess.run(arguments, cwd=ROOT)
    return result.returncode


def scan_forbidden(pattern: str, roots: Iterable[Path]) -> int:
    expression = re.compile(pattern, re.IGNORECASE)
    try:
        for root in roots:
            for path in sorted(root.rglob("*.py")):
                lines = path.read_text(encoding="utf-8").splitlines()
                for number, line in enumerate(lines, 1):
                    if expression.search(line):
                        print(f"{path.relative_to(ROOT)}:{number}:{line}")
                        return 1
    except OSError as error:
        print(f"scan error: {error}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    for stale in (ROOT / ".coverage", ROOT / "coverage.xml"):
        stale.unlink(missing_ok=True)

    python = sys.executable
    steps: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "tests + coverage",
            (
                python,
                "-m",
                "pytest",
                "-q",
                "--cov=ratelimiter",
                "--cov-report=term-missing",
            ),
        ),
        ("types", (python, "-m", "mypy", "src", "tests", "examples", "tools")),
        ("lint", (python, "-m", "ruff", "check", ".")),
        ("format", (python, "-m", "ruff", "format", "--check", ".")),
        ("supply chain", (python, "-m", "pip_audit", "-r", "requirements-dev.txt")),
    )
    for label, command in steps:
        status = run_step(label, command)
        if status:
            return 1 if status == 1 else 2

    print("=== must-not scans ===", flush=True)
    scans = (
        (r"time\.", (ROOT / "tests",)),
        (
            r"api[_-]?key|s" + r"ecret|pass" + r"word|to" + r"ken|private[_-]?key",
            tuple(ROOT / name for name in ("src", "tests", "tools", "examples")),
        ),
    )
    for pattern, roots in scans:
        status = scan_forbidden(pattern, roots)
        if status:
            return status
    print("must-not scans clean")

    final_steps: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("mutation", (python, "tools/mutants.py")),
        ("real execution", (python, "examples/demo.py")),
    )
    for label, command in final_steps:
        status = run_step(label, command)
        if status:
            return 1 if status == 1 else 2

    print("=== gauntlet: all layers green ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
