"""Manual mutation gate with cache isolation and byte-safe restoration."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "src/ratelimiter/__init__.py"
PYCACHE = TARGET.parent / "__pycache__"
_existing_pythonpath = os.environ.get("PYTHONPATH")
MUTANT_ENV = {
    **os.environ,
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONPATH": str(ROOT / "src")
    + (os.pathsep + _existing_pythonpath if _existing_pythonpath else ""),
}

MUTANTS = [
    (
        "M1 flip limit comparison >= to >",
        "if len(hits) >= self._limit:",
        "if len(hits) > self._limit:",
    ),
    (
        "M2 flip expiry boundary > to >=",
        "while hits and now - hits[0] > self._window:",
        "while hits and now - hits[0] >= self._window:",
    ),
    ("M3 drop recording of allowed hit", "        hits.append(now)\n", "\n"),
    ("M4 validation off-by-one <= to <", "if limit <= 0:", "if limit < 0:"),
    (
        "M5 deny becomes allow (fail open)",
        "            return False",
        "            return True",
    ),
    ("M6 prune from wrong end", "hits.popleft()", "hits.pop()"),
    (
        "M7 drop finiteness validation",
        "if not math.isfinite(window_seconds) or window_seconds <= 0:",
        "if window_seconds <= 0:",
    ),
    (
        "M8 denial records the attempt (memory leak)",
        "        if len(hits) >= self._limit:\n            return False",
        "        if len(hits) >= self._limit:\n"
        "            hits.append(now)\n"
        "            return False",
    ),
]

# Both controls change the source and preserve its size. Pinning one mtime
# constructs the exact cache-key collision that once made the second result
# inherit the first mutant's bytecode. C2 changes whitespace only and is
# strictly equivalent Python.
CONTROL = (
    ("C1 killer", "if limit <= 0:", "if limit >= 0:"),
    ("C2 equivalent", "self._limit = limit", "self._limit=  limit"),
)


@dataclass(frozen=True, slots=True)
class MutationResult:
    verdict: str
    exit_code: int


def _replacement(original: bytes, old: str, new: str, name: str) -> bytes:
    newline = "\r\n" if b"\r\n" in original else "\n"
    old_bytes = old.replace("\n", newline).encode()
    new_bytes = new.replace("\n", newline).encode()
    if original.count(old_bytes) != 1:
        raise RuntimeError(f"{name}: mutation pattern is not unique")
    return original.replace(old_bytes, new_bytes)


def _clear_bytecode() -> None:
    shutil.rmtree(PYCACHE, ignore_errors=True)


def run_mutant(
    original: bytes,
    name: str,
    old: str,
    new: str,
    pytest_target: str,
    *,
    pin_mtime: float | None = None,
) -> MutationResult:
    TARGET.write_bytes(_replacement(original, old, new, name))
    if pin_mtime is not None:
        os.utime(TARGET, (pin_mtime, pin_mtime))
    _clear_bytecode()
    with tempfile.TemporaryDirectory(prefix="rate-limiter-mutant-") as temporary:
        report = Path(temporary) / "pytest.xml"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-x",
                "-p",
                "no:cacheprovider",
                "--assert=plain",
                "-o",
                f"cache_dir={temporary}",
                f"--junitxml={report}",
                pytest_target,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=MUTANT_ENV,
        )
        try:
            root = element_tree.parse(report).getroot()
            suites = (
                (root,) if root.tag == "testsuite" else tuple(root.iter("testsuite"))
            )
            tests = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
            failures = sum(int(suite.attrib.get("failures", "0")) for suite in suites)
            errors = sum(int(suite.attrib.get("errors", "0")) for suite in suites)
        except (OSError, ValueError, element_tree.ParseError):
            tests = failures = errors = -1
    if PYCACHE.exists() and any(PYCACHE.iterdir()):
        raise RuntimeError("bytecode cache reappeared during mutant execution")
    if result.returncode == 1 and tests > 0 and failures > 0 and errors == 0:
        return MutationResult("KILLED", result.returncode)
    if result.returncode == 0 and tests > 0 and failures == 0 and errors == 0:
        return MutationResult("SURVIVED", result.returncode)
    return MutationResult("ERROR", result.returncode)


def _restore(original: bytes, atime_ns: int, mtime_ns: int) -> None:
    TARGET.write_bytes(original)
    os.utime(TARGET, ns=(atime_ns, mtime_ns))
    _clear_bytecode()
    if TARGET.read_bytes() != original:
        raise RuntimeError("mutation runner did not restore source byte-for-byte")


def negative_control() -> int:
    original = TARGET.read_bytes()
    status = TARGET.stat()
    try:
        pinned = 1_600_000_000.0
        results = [
            run_mutant(
                original,
                name,
                old,
                new,
                "tests/test_ratelimiter.py",
                pin_mtime=pinned,
            )
            for name, old, new in CONTROL
        ]
    except (OSError, RuntimeError) as error:
        print(f"negative control error: {error}", file=sys.stderr)
        return_code = 2
        results = []
    else:
        verdicts = [result.verdict for result in results]
        return_code = 0 if verdicts == ["KILLED", "SURVIVED"] else 1
        if any(result.verdict == "ERROR" for result in results):
            return_code = 2
    finally:
        _restore(original, status.st_atime_ns, status.st_mtime_ns)

    for (name, _, _), result in zip(CONTROL, results, strict=False):
        detail = (
            result.verdict
            if result.verdict != "ERROR"
            else f"ERROR (pytest exit {result.exit_code})"
        )
        print(f"{name}: {detail}")
    print("negative control: " + ("ok" if return_code == 0 else "FAILED"))
    return return_code


def mutation_run(pytest_target: str) -> int:
    original = TARGET.read_bytes()
    status = TARGET.stat()
    killed = 0
    errors = 0
    try:
        for name, old, new in MUTANTS:
            result = run_mutant(original, name, old, new, pytest_target)
            if result.verdict == "KILLED":
                verdict = result.verdict
                killed += 1
            elif result.verdict == "SURVIVED":
                verdict = result.verdict
            else:
                verdict = f"ERROR (pytest exit {result.exit_code}, no tests verified)"
                errors += 1
            print(f"{name}: {verdict}")
    except (OSError, RuntimeError) as error:
        print(f"mutation runner error: {error}", file=sys.stderr)
        errors += 1
    finally:
        _restore(original, status.st_atime_ns, status.st_mtime_ns)

    summary = f"\n{killed}/{len(MUTANTS)} mutants killed"
    if errors:
        summary += f", {errors} ERROR — run is invalid"
    print(summary)
    if errors:
        return 2
    return 0 if killed == len(MUTANTS) else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--negative-control":
        return negative_control()
    pytest_target = sys.argv[1] if len(sys.argv) > 1 else "tests"
    return mutation_run(pytest_target)


if __name__ == "__main__":
    raise SystemExit(main())
