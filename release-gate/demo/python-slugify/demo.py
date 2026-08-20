#!/usr/bin/env python3
"""Cross-platform driver for the python-slugify Release Gate demo."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEMO_ROOT = Path(__file__).resolve().parent
ASSETS = DEMO_ROOT / "assets"
CONTROLS = DEMO_ROOT / "controls"
ORACLE = DEMO_ROOT / "oracle"
WORKBENCH = DEMO_ROOT / "workbench"
REPOSITORY = WORKBENCH / "python-slugify"
TASK_VENV = WORKBENCH / "task-venv"
ORACLE_VENV = WORKBENCH / "oracle-venv"
CONTROL_EVIDENCE = WORKBENCH / "evidence"
UPSTREAM_URL = "https://github.com/un33k/python-slugify.git"
UPSTREAM_SHA = "7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4"
BASE_REF = "release-gate-demo-base"
EXPECTED_GATE_VERSION = "release-gate 0.3.0"
TEST_TOOLS = ("pytest==8.4.2",)


class DemoError(RuntimeError):
    """An expected, actionable demo error."""


@dataclass(frozen=True, slots=True)
class ResultSummary:
    run_id: str
    verdict: str
    reason_codes: tuple[str, ...]
    changed_paths: tuple[str, ...]
    outside_allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    review_required_paths: tuple[str, ...]
    checks: tuple[tuple[str, str, tuple[str, ...]], ...]
    manifest_path: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the cross-platform python-slugify Release Gate demo."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="check host prerequisites")
    commands.add_parser("setup", help="create the disposable workbench")
    commands.add_parser("reset", help="restore the trusted demo baseline")
    control = commands.add_parser("control", help="apply a deterministic candidate")
    control.add_argument("scenario", choices=("pass", "fail", "needs-human"))
    for name in ("inspect", "grade"):
        command = commands.add_parser(name)
        command.add_argument("--result", required=True, type=Path)
    commands.add_parser("verify", help="exercise all three verdicts without Copilot")
    return parser


def host_python_argv(platform: str | None = None) -> tuple[str, ...]:
    selected = platform or sys.platform
    if selected == "win32":
        return ("py", "-3")
    if selected == "darwin":
        return ("python3",)
    raise DemoError("this demo supports native Windows and macOS hosts")


def classify_oracle(verdict: str, correct: bool) -> str:
    if verdict == "NEEDS_HUMAN":
        return "escalated"
    mapping = {
        ("PASS", True): "good_pass",
        ("PASS", False): "FALSE_RELEASE",
        ("FAIL", True): "FALSE_BLOCK",
        ("FAIL", False): "good_catch",
    }
    try:
        return mapping[(verdict, correct)]
    except KeyError as error:
        raise DemoError(f"unsupported verdict for grading: {verdict}") from error


def read_result_summary(path: Path) -> ResultSummary:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DemoError(f"unable to read result JSON: {path}") from error
    if not isinstance(value, dict):
        raise DemoError("result must be a JSON object")
    if value.get("version") != 1:
        raise DemoError("result version must be 1")
    run_id = _required_string(value, "run_id")
    verdict = _required_string(value, "verdict")
    if verdict not in {"PASS", "FAIL", "NEEDS_HUMAN"}:
        raise DemoError(f"unsupported result verdict: {verdict}")
    scope = _required_mapping(value, "scope")
    checks_value = value.get("checks")
    if not isinstance(checks_value, list):
        raise DemoError("result checks must be an array")
    checks: list[tuple[str, str, tuple[str, ...]]] = []
    for item in checks_value:
        if not isinstance(item, dict):
            raise DemoError("each result check must be an object")
        checks.append(
            (
                _required_string(item, "id"),
                _required_string(item, "status"),
                _string_tuple(item, "reason_codes"),
            )
        )
    return ResultSummary(
        run_id=run_id,
        verdict=verdict,
        reason_codes=_string_tuple(value, "reason_codes"),
        changed_paths=_string_tuple(scope, "changed_paths"),
        outside_allowed_paths=_string_tuple(scope, "outside_allowed_paths"),
        forbidden_paths=_string_tuple(scope, "forbidden_paths"),
        review_required_paths=_string_tuple(scope, "review_required_paths"),
        checks=tuple(checks),
        manifest_path=_required_string(value, "manifest_path"),
    )


def _required_mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise DemoError(f"result {key} must be an object")
    return item


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise DemoError(f"result {key} must be a non-empty string")
    return item


def _string_tuple(value: dict[str, Any], key: str) -> tuple[str, ...]:
    item = value.get(key)
    if not isinstance(item, list) or not all(isinstance(entry, str) for entry in item):
        raise DemoError(f"result {key} must be an array of strings")
    return tuple(item)


def _run(
    argv: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [os.fspath(argument) for argument in argv]
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=check,
            text=True,
            capture_output=capture,
        )
    except FileNotFoundError as error:
        raise DemoError(f"required executable is unavailable: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() if error.stderr else f"exit {error.returncode}"
        raise DemoError(f"command failed: {' '.join(command)} ({detail})") from error


def _git(
    *arguments: str, cwd: Path | None = None, capture: bool = False
) -> str:
    result = _run(("git", *arguments), cwd=cwd or REPOSITORY, capture=capture)
    return result.stdout.strip() if capture else ""


def _which(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise DemoError(f"required executable is unavailable: {name}")
    return path


def _gate_argv(
    *arguments: str | os.PathLike[str],
) -> tuple[str | os.PathLike[str], ...]:
    """Build the release-gate invocation, preferring ``python -m release_gate``.

    Some corporate endpoint security policies block the generated
    ``release-gate`` executable shim while still allowing the interpreter it
    was built with. Resolving the sibling ``python`` next to that shim and
    running the module directly avoids executing the blocked binary.
    """

    exe = shutil.which("release-gate")
    if exe is not None:
        venv_python = Path(exe).with_name(
            "python.exe" if sys.platform == "win32" else "python"
        )
        if venv_python.is_file():
            return (venv_python, "-m", "release_gate", *arguments)
    return ("release-gate", *arguments)


def _task_python(venv: Path = TASK_VENV) -> Path:
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _task_pip(venv: Path = TASK_VENV) -> tuple[Path, str, str]:
    return (_task_python(venv), "-m", "pip")


def doctor() -> None:
    host_python_argv()
    for executable in ("git", "uv", "copilot", "release-gate"):
        print(f"{executable}: {_which(executable)}")
    if not (sys.version_info.major == 3 and 11 <= sys.version_info.minor <= 13):
        raise DemoError("Python 3.11 through 3.13 is required")
    version = _run(_gate_argv("--version"), capture=True).stdout.strip()
    if version != EXPECTED_GATE_VERSION:
        raise DemoError(
            f"Release Gate version mismatch: expected {EXPECTED_GATE_VERSION!r}, "
            f"got {version!r}"
        )
    print(f"python: {sys.version.split()[0]}")
    print("doctor: ready")


def setup() -> None:
    host_python_argv()
    _which("git")
    _require_gate_version()
    if WORKBENCH.exists() or WORKBENCH.is_symlink():
        raise DemoError(
            f"workbench already exists: {WORKBENCH}; use reset or remove it explicitly"
        )
    WORKBENCH.mkdir(mode=0o700)
    try:
        _run(("git", "clone", "--quiet", UPSTREAM_URL, REPOSITORY))
        _git("checkout", "--quiet", UPSTREAM_SHA)
        _git("switch", "--quiet", "-c", "release-gate-demo")
        _git("config", "user.name", "Release Gate Demo")
        _git("config", "user.email", "release-gate-demo@example.invalid")
        _run(
            _gate_argv(
                "init",
                "--repo",
                REPOSITORY,
                "--from-config",
                ASSETS / ".release-gate.yaml",
            )
        )
        _git("add", ".release-gate.yaml", ".gitignore")
        _git("commit", "--quiet", "-m", "chore: add release gate demo policy")
        _git("tag", BASE_REF)
        _verify_repository()
        _create_task_environment(TASK_VENV)
        _verify_upstream_tests()
        _run(_gate_argv("validate", "--repo", REPOSITORY))
    except Exception:
        print(f"setup stopped; inspect or remove {WORKBENCH}", file=sys.stderr)
        raise
    print(f"BASELINE GREEN at {UPSTREAM_SHA}")
    print(f"trusted base: {BASE_REF}")
    print(f"workbench: {REPOSITORY}")


def reset() -> None:
    _verify_repository()
    _git("reset", "--hard", BASE_REF)
    _git("clean", "-fdx", "-e", ".release-gate/runs/")
    _remove_owned_directory(TASK_VENV)
    _remove_owned_directory(ORACLE_VENV)
    _create_task_environment(TASK_VENV)
    _verify_upstream_tests()
    print(f"reset: {BASE_REF}")


def control(scenario: str) -> None:
    reset()
    patches = [CONTROLS / "pass.patch"]
    if scenario != "pass":
        patches.append(CONTROLS / f"{scenario}.patch")
    for patch in patches:
        if not patch.is_file():
            raise DemoError(f"control patch is missing: {patch}")
        _git("apply", "--check", os.fspath(patch))
        _git("apply", os.fspath(patch))
    changed = _git("status", "--short", capture=True)
    if not changed:
        raise DemoError(f"control patch produced no candidate changes: {scenario}")
    print(changed)
    print(f"control ready: {scenario}")


def inspect_result(path: Path) -> ResultSummary:
    resolved = path.expanduser().resolve(strict=True)
    summary = read_result_summary(resolved)
    manifest = resolved.parent / summary.manifest_path
    if not manifest.is_file() or (resolved.parent / ".incomplete").exists():
        raise DemoError("evidence package is incomplete or missing manifest.json")
    print(f"run: {summary.run_id}")
    print(f"verdict: {summary.verdict}")
    print(f"reason codes: {', '.join(summary.reason_codes) or 'none'}")
    print(f"changed paths: {', '.join(summary.changed_paths) or 'none'}")
    if summary.outside_allowed_paths:
        print(f"outside allowed: {', '.join(summary.outside_allowed_paths)}")
    if summary.forbidden_paths:
        print(f"forbidden: {', '.join(summary.forbidden_paths)}")
    if summary.review_required_paths:
        print(f"review required: {', '.join(summary.review_required_paths)}")
    for check_id, status, reasons in summary.checks:
        detail = f" ({', '.join(reasons)})" if reasons else ""
        print(f"check {check_id}: {status}{detail}")
    print(f"manifest: {manifest}")
    return summary


def grade(path: Path) -> str:
    _verify_repository()
    summary = inspect_result(path)
    correct = _oracle_truth()
    box = classify_oracle(summary.verdict, correct)
    print(f"truth: {'correct' if correct else 'wrong'}")
    print(f"classification: {box}")
    return box


def verify() -> None:
    if WORKBENCH.exists():
        _verify_repository()
    else:
        setup()
    expected = {
        "pass": (0, "PASS", "good_pass"),
        "fail": (1, "FAIL", "good_catch"),
        "needs-human": (2, "NEEDS_HUMAN", "escalated"),
    }
    CONTROL_EVIDENCE.mkdir(mode=0o700, exist_ok=True)
    for scenario, (exit_code, verdict, box) in expected.items():
        control(scenario)
        run_id = f"verify-{scenario}-{uuid.uuid4().hex[:8]}"
        result = _run(
            _gate_argv(
                "run",
                "--repo",
                REPOSITORY,
                "--base",
                BASE_REF,
                "--output",
                CONTROL_EVIDENCE,
                "--run-id",
                run_id,
            ),
            check=False,
            capture=True,
        )
        print(result.stderr, end="", file=sys.stderr)
        print(result.stdout, end="")
        if result.returncode != exit_code:
            raise DemoError(
                f"{scenario}: expected exit {exit_code}, got {result.returncode}"
            )
        result_path = _result_path(result.stdout)
        summary = inspect_result(result_path)
        if summary.verdict != verdict:
            raise DemoError(
                f"{scenario}: expected verdict {verdict}, got {summary.verdict}"
            )
        actual_box = grade(result_path)
        if actual_box != box:
            raise DemoError(f"{scenario}: expected {box}, got {actual_box}")
    reset()
    print("verify: PASS, FAIL, and NEEDS_HUMAN controls matched expectations")


def _require_gate_version() -> None:
    _which("release-gate")
    actual = _run(_gate_argv("--version"), capture=True).stdout.strip()
    if actual != EXPECTED_GATE_VERSION:
        raise DemoError(
            f"expected {EXPECTED_GATE_VERSION!r}, got {actual!r}; "
            "install this checkout by path"
        )


def _verify_repository() -> None:
    if REPOSITORY.is_symlink() or not (REPOSITORY / ".git").exists():
        raise DemoError(f"expected workbench repository is missing: {REPOSITORY}")
    if REPOSITORY.resolve().parent != WORKBENCH.resolve():
        raise DemoError("workbench repository resolved outside the demo workbench")
    origin = _git("remote", "get-url", "origin", capture=True).rstrip("/")
    accepted = {UPSTREAM_URL.rstrip("/"), UPSTREAM_URL.removesuffix(".git")}
    if origin not in accepted:
        raise DemoError(f"unexpected workbench origin: {origin}")
    base = _git("rev-parse", f"{BASE_REF}^{{commit}}", capture=True)
    parent = _git("rev-parse", f"{BASE_REF}^", capture=True)
    if len(base) != 40 or parent != UPSTREAM_SHA:
        raise DemoError(f"trusted base {BASE_REF} does not extend {UPSTREAM_SHA}")
    policy = _git("show", f"{BASE_REF}:.release-gate.yaml", capture=True)
    expected_policy = (ASSETS / ".release-gate.yaml").read_text(encoding="utf-8")
    if policy.rstrip("\n") != expected_policy.rstrip("\n"):
        raise DemoError("trusted base policy does not match the committed demo asset")


def _create_task_environment(venv: Path) -> None:
    _run((*host_python_argv(), "-m", "venv", venv))
    _run(
        (
            *_task_pip(venv),
            "install",
            "--disable-pip-version-check",
            "-q",
            "-e",
            REPOSITORY,
            *TEST_TOOLS,
        )
    )


def _verify_upstream_tests() -> None:
    result = _run(
        (
            _task_python(),
            "-m",
            "pytest",
            "test.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ),
        cwd=REPOSITORY,
        capture=True,
    )
    print(result.stdout.rstrip())
    if "82 passed" not in result.stdout:
        raise DemoError("expected the pinned upstream baseline to report 82 passed")


def _oracle_truth() -> bool:
    _remove_owned_directory(ORACLE_VENV)
    _run((*host_python_argv(), "-m", "venv", ORACLE_VENV))
    _run(
        (
            *_task_pip(ORACLE_VENV),
            "install",
            "--disable-pip-version-check",
            "-q",
            "-e",
            REPOSITORY,
            *TEST_TOOLS,
        )
    )
    result = _run(
        (
            _task_python(ORACLE_VENV),
            "-m",
            "pytest",
            ORACLE,
            "-q",
            "-p",
            "no:cacheprovider",
        ),
        cwd=REPOSITORY,
        check=False,
        capture=True,
    )
    print(result.stdout.rstrip())
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise DemoError(f"oracle could not run cleanly (exit {result.returncode})")


def _remove_owned_directory(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.resolve().parent != WORKBENCH.resolve():
        raise DemoError(f"refusing to remove unsafe demo path: {path}")
    shutil.rmtree(path)


def _result_path(stdout: str) -> Path:
    paths = [
        line.removeprefix("RESULT: ")
        for line in stdout.splitlines()
        if line.startswith("RESULT: ")
    ]
    if len(paths) != 1:
        raise DemoError("gate output did not contain exactly one RESULT path")
    return Path(paths[0])


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "doctor":
            doctor()
        elif arguments.command == "setup":
            setup()
        elif arguments.command == "reset":
            reset()
        elif arguments.command == "control":
            control(arguments.scenario)
        elif arguments.command == "inspect":
            inspect_result(arguments.result)
        elif arguments.command == "grade":
            grade(arguments.result)
        elif arguments.command == "verify":
            verify()
        else:
            raise DemoError(f"unsupported command: {arguments.command}")
    except DemoError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
