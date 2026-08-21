"""Cross-platform, self-auditing rate-limiter quality gauntlet."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_existing_pythonpath = os.environ.get("PYTHONPATH")
CHILD_ENV = {
    **os.environ,
    "PYTHONPATH": str(ROOT / "src")
    + (os.pathsep + _existing_pythonpath if _existing_pythonpath else ""),
}
EXPECTED_LAYERS = (
    "orchestration controls",
    "checker controls",
    "tests + coverage",
    "types",
    "lint",
    "format",
    "supply chain",
    "must-not scans",
    "mutation control",
    "mutation",
    "real execution",
    "source state",
)


class LayerLedger:
    """Record successful completion against one fixed expected-layer manifest."""

    def __init__(self, expected: Sequence[str]) -> None:
        if not expected or len(expected) != len(set(expected)):
            raise ValueError("expected layers must be non-empty and unique")
        self.expected = tuple(expected)
        self._completed: list[str] = []

    @property
    def completed(self) -> tuple[str, ...]:
        return tuple(self._completed)

    def validate(self, label: str) -> int:
        if label not in self.expected:
            print(f"gauntlet error: unknown layer {label!r}", file=sys.stderr)
            return 2
        if label in self._completed:
            print(f"gauntlet error: duplicate layer {label!r}", file=sys.stderr)
            return 2
        return 0

    def complete(self, label: str) -> int:
        status = self.validate(label)
        if status:
            return status
        self._completed.append(label)
        return 0

    def audit(self, *, announce: bool = False) -> int:
        missing = tuple(
            label for label in self.expected if label not in self._completed
        )
        for label in missing:
            print(f"gauntlet error: missing layer {label!r}", file=sys.stderr)
        if missing:
            return 1
        if announce:
            print("=== gauntlet: all layers green ===")
        return 0


def run_layer(ledger: LayerLedger, label: str, arguments: Sequence[str]) -> int:
    status = ledger.validate(label)
    if status:
        return status
    print(f"=== {label} ===", flush=True)
    try:
        result = subprocess.run(arguments, cwd=ROOT, env=CHILD_ENV)
    except OSError as error:
        print(
            f"gauntlet error: layer {label!r} could not start: {error}",
            file=sys.stderr,
        )
        return 2
    if result.returncode:
        print(
            f"gauntlet error: layer {label!r} failed (rc={result.returncode})",
            file=sys.stderr,
        )
        return result.returncode
    return ledger.complete(label)


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def scan_forbidden(pattern: str, roots: Iterable[Path]) -> int:
    try:
        expression = re.compile(pattern, re.IGNORECASE)
    except re.error as error:
        print(f"scan error: invalid pattern: {error}", file=sys.stderr)
        return 2
    try:
        for root in roots:
            status = _scan_root(expression, root)
            if status:
                return status
    except (OSError, UnicodeError) as error:
        print(f"scan error: {error}", file=sys.stderr)
        return 2
    return 0


def _scan_root(expression: re.Pattern[str], root: Path) -> int:
    if not root.exists() or not root.is_dir() or root.is_symlink():
        print(f"scan error: unreadable or missing root: {root}", file=sys.stderr)
        return 2
    for path in sorted(root.rglob("*.py")):
        if path.is_symlink() or not path.is_file():
            print(f"scan error: input is not a regular file: {path}", file=sys.stderr)
            return 2
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, 1):
            if expression.search(line):
                print(f"{_display_path(path)}:{number}:{line}")
                return 1
    return 0


def orchestration_controls() -> int:
    missing = LayerLedger(("first", "second"))
    if missing.complete("first") or missing.audit() != 1:
        return 1
    unknown = LayerLedger(("known",))
    if unknown.complete("unknown") != 2:
        return 1
    duplicate = LayerLedger(("once",))
    if duplicate.complete("once") or duplicate.complete("once") != 2:
        return 1
    complete = LayerLedger(("first", "second"))
    if complete.complete("first") or complete.complete("second"):
        return 1
    if complete.audit(announce=False):
        return 1
    child = LayerLedger(("child",))
    status = run_layer(child, "child", (sys.executable, "-c", "raise SystemExit(7)"))
    if status != 7 or child.completed:
        return 1
    print("orchestration controls: 5/5 passed")
    return 0


def checker_controls() -> int:
    with tempfile.TemporaryDirectory(prefix="rate-limiter-scan-") as temporary:
        root = Path(temporary)
        source = root / "fixture.py"
        source.write_text("value = 1\n", encoding="utf-8")
        if scan_forbidden("forbidden", (root,)) != 0:
            return 1
        source.write_text("FORBIDDEN = True\n", encoding="utf-8")
        if scan_forbidden("forbidden", (root,)) != 1:
            return 1
        if scan_forbidden("forbidden", (root / "missing",)) != 2:
            return 1
    print("checker controls: clean, violation, and broken input passed")
    return 0


def must_not_scans() -> int:
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
    return 0


def _run_callable(ledger: LayerLedger, label: str, function: Callable[[], int]) -> int:
    status = ledger.validate(label)
    if status:
        return status
    print(f"=== {label} ===", flush=True)
    try:
        result = function()
    except Exception as error:
        print(f"gauntlet error: layer {label!r} crashed: {error}", file=sys.stderr)
        return 2
    if result:
        print(
            f"gauntlet error: layer {label!r} failed (rc={result})",
            file=sys.stderr,
        )
        return result
    return ledger.complete(label)


def _run_commands(
    ledger: LayerLedger,
    layers: Sequence[tuple[str, Sequence[str]]],
) -> int:
    for label, command in layers:
        status = run_layer(ledger, label, command)
        if status:
            return status
    return 0


def main() -> int:
    for stale in (ROOT / ".coverage", ROOT / "coverage.xml"):
        stale.unlink(missing_ok=True)

    python = sys.executable
    ledger = LayerLedger(EXPECTED_LAYERS)
    for label, function in (
        ("orchestration controls", orchestration_controls),
        ("checker controls", checker_controls),
    ):
        status = _run_callable(ledger, label, function)
        if status:
            return status

    command_layers: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "tests + coverage",
            (
                python,
                "-m",
                "pytest",
                "-q",
                "--cov=ratelimiter",
                "--cov-branch",
                "--cov-report=term-missing",
                "--cov-fail-under=100",
            ),
        ),
        ("types", (python, "-m", "mypy", "src", "tests", "examples", "tools")),
        ("lint", (python, "-m", "ruff", "check", ".")),
        ("format", (python, "-m", "ruff", "format", "--check", ".")),
        (
            "supply chain",
            (python, "-m", "pip_audit", "-r", "requirements-dev.txt"),
        ),
    )
    status = _run_commands(ledger, command_layers)
    if status:
        return status

    status = _run_callable(ledger, "must-not scans", must_not_scans)
    if status:
        return status

    status = _run_commands(
        ledger,
        (
            ("mutation control", (python, "tools/mutants.py", "--negative-control")),
            ("mutation", (python, "tools/mutants.py")),
            ("real execution", (python, "examples/demo.py")),
            ("source state", (python, "tools/source_state.py", "--candidate")),
        ),
    )
    if status:
        return status

    return ledger.audit(announce=True)


if __name__ == "__main__":
    raise SystemExit(main())
