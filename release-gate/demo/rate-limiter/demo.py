"""Build and exercise an isolated Release Gate rate-limiter workbench."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
CONTROLS = ROOT / "controls"
ORACLE = ROOT / "oracle" / "test_ratelimiter_oracle.py"
WORKBENCH = ROOT / "workbench"
REPOSITORY = WORKBENCH / "rate-limiter"
TASK_VENV = WORKBENCH / "task-venv"
ORACLE_VENV = WORKBENCH / "oracle-venv"
CONTROL_EVIDENCE = WORKBENCH / "control-evidence"
BASE_REF = "release-gate-rate-limiter-base"
EXPECTED_GATE_VERSION = "release-gate 0.5.0"
SOURCE_ITEMS = (
    "README.md",
    "evidence.md",
    "examples",
    "pyproject.toml",
    "requirements-dev.txt",
    "spec.md",
    "src",
    "tests",
    "tools/gauntlet.py",
    "tools/gauntlet.sh",
    "tools/mutants.py",
    "tools/source_state.py",
)


class DemoError(RuntimeError):
    """The operator-facing demo cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class ResultSummary:
    run_id: str
    base_commit: str
    candidate_tree: str
    patch_sha256: str
    config_sha256: str
    verdict: str
    reason_codes: tuple[str, ...]
    changed_paths: tuple[str, ...]
    outside_allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    review_required_paths: tuple[str, ...]
    checks: tuple[tuple[str, str, tuple[str, ...]], ...]
    manifest_path: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("doctor", "setup", "reset", "verify"):
        commands.add_parser(command)
    control = commands.add_parser("control")
    control.add_argument("scenario", choices=("pass", "fail", "needs-human"))
    for command in ("inspect", "grade"):
        item = commands.add_parser(command)
        item.add_argument("--result", required=True, type=Path)
    return parser


def require_supported_platform(platform: str | None = None) -> None:
    family = sys.platform if platform is None else platform
    if family not in {"win32", "darwin"}:
        raise DemoError("this walkthrough supports Windows and macOS")


def classify_oracle(verdict: str, correct: bool | None) -> str:
    if correct is None:
        return "oracle_error"
    if verdict == "NEEDS_HUMAN":
        return "escalated"
    if verdict == "PASS":
        return "good_pass" if correct else "FALSE_RELEASE"
    if verdict == "FAIL":
        return "FALSE_BLOCK" if correct else "good_catch"
    raise DemoError(f"unsupported verdict: {verdict}")


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise DemoError(f"result field {field!r} is invalid")
    return tuple(value)


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise DemoError(f"result field {field!r} is invalid")
    return value


def _check_summary(value: Any, index: int) -> tuple[str, str, tuple[str, ...]]:
    if not isinstance(value, dict):
        raise DemoError(f"result check {index} is invalid")
    return (
        _required_string(value.get("id"), f"checks[{index}].id"),
        _required_string(value.get("status"), f"checks[{index}].status"),
        _string_tuple(value.get("reason_codes"), f"checks[{index}].reason_codes"),
    )


def read_result_summary(path: Path) -> ResultSummary:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DemoError(f"unable to read result: {error}") from error
    if not isinstance(value, dict) or value.get("version") != 1:
        raise DemoError("result version is missing or unsupported")
    run_id = _required_string(value.get("run_id"), "run_id")
    verdict = value.get("verdict")
    manifest_path = _required_string(value.get("manifest_path"), "manifest_path")
    if verdict not in {"PASS", "FAIL", "NEEDS_HUMAN"}:
        raise DemoError("result verdict is invalid")
    scope = value.get("scope")
    checks_value = value.get("checks")
    if not isinstance(scope, dict) or not isinstance(checks_value, list):
        raise DemoError("result scope or checks is invalid")
    checks = [_check_summary(check, index) for index, check in enumerate(checks_value)]
    return ResultSummary(
        run_id=run_id,
        base_commit=_required_string(value.get("base_commit"), "base_commit"),
        candidate_tree=_required_string(value.get("candidate_tree"), "candidate_tree"),
        patch_sha256=_required_string(value.get("patch_sha256"), "patch_sha256"),
        config_sha256=_required_string(value.get("config_sha256"), "config_sha256"),
        verdict=verdict,
        reason_codes=_string_tuple(value.get("reason_codes"), "reason_codes"),
        changed_paths=_string_tuple(scope.get("changed_paths"), "scope.changed_paths"),
        outside_allowed_paths=_string_tuple(
            scope.get("outside_allowed_paths"), "scope.outside_allowed_paths"
        ),
        forbidden_paths=_string_tuple(
            scope.get("forbidden_paths"), "scope.forbidden_paths"
        ),
        review_required_paths=_string_tuple(
            scope.get("review_required_paths"), "scope.review_required_paths"
        ),
        checks=tuple(checks),
        manifest_path=manifest_path,
    )


def _run(
    arguments: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = tuple(os.fspath(argument) for argument in arguments)
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=check,
            capture_output=capture,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise DemoError(f"command failed: {' '.join(command)}") from error


def _which(executable: str) -> str:
    path = shutil.which(executable)
    if path is None:
        raise DemoError(f"required executable is unavailable: {executable}")
    return path


def _gate_argv(
    *arguments: str | os.PathLike[str],
) -> tuple[str | os.PathLike[str], ...]:
    shim = Path(_which("release-gate")).resolve()
    sibling_python = shim.with_name(
        "python.exe" if sys.platform == "win32" else "python"
    )
    if sibling_python.is_file():
        return (sibling_python, "-m", "release_gate", *arguments)
    return (shim, *arguments)


def _git(*arguments: str, capture: bool = False) -> str:
    result = _run(("git", *arguments), cwd=REPOSITORY, capture=capture)
    return result.stdout.strip() if capture else ""


def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def doctor() -> None:
    require_supported_platform()
    for executable in ("git", "uv", "copilot", "release-gate"):
        print(f"{executable}: {_which(executable)}")
    evaluation_python = _run(
        ("uv", "python", "find", "3.12"), capture=True
    ).stdout.strip()
    _require_gate_version()
    print(f"runner python: {sys.version.split()[0]}")
    print(f"evaluation python: {evaluation_python}")
    print("doctor: ready")


def _copy_baseline() -> None:
    REPOSITORY.mkdir(mode=0o700)
    for name in SOURCE_ITEMS:
        source = ROOT / name
        target = REPOSITORY / name
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
            )
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            raise DemoError(f"baseline source is missing: {source}")


def _create_environment(venv: Path, *, oracle_only: bool = False) -> None:
    _run(("uv", "venv", "--python", "3.12", "--seed", venv))
    python = _venv_python(venv)
    arguments: tuple[str | os.PathLike[str], ...]
    if oracle_only:
        arguments = (REPOSITORY, "pytest==9.1.1")
    else:
        arguments = ("-r", REPOSITORY / "requirements-dev.txt")
    _run(
        (
            "uv",
            "pip",
            "install",
            "--python",
            python,
            "--disable-pip-version-check",
            "--no-cache-dir",
            "-q",
            *arguments,
        ),
        cwd=REPOSITORY,
    )


def _verify_baseline() -> None:
    _run((_venv_python(TASK_VENV), "tools/gauntlet.py"), cwd=REPOSITORY)
    _git("clean", "-fdx", "-e", ".release-gate/runs/")


def setup() -> None:
    require_supported_platform()
    _which("git")
    _which("uv")
    _require_gate_version()
    if WORKBENCH.exists() or WORKBENCH.is_symlink():
        raise DemoError(f"workbench already exists: {WORKBENCH}; use reset")
    WORKBENCH.mkdir(mode=0o700)
    try:
        _copy_baseline()
        _git("init", "--quiet")
        _git("config", "user.name", "Release Gate Demo")
        _git("config", "user.email", "release-gate-demo@example.invalid")
        _git("config", "core.autocrlf", "true")
        _run(
            _gate_argv(
                "init",
                "--repo",
                REPOSITORY,
                "--from-config",
                ASSETS / ".release-gate.yaml",
            )
        )
        _git("add", "-A")
        _git("commit", "--quiet", "-m", "chore: establish rate-limiter demo baseline")
        _git("tag", BASE_REF)
        _verify_repository()
        _create_environment(TASK_VENV)
        _verify_baseline()
        _run(_gate_argv("validate", "--repo", REPOSITORY))
    except Exception:
        print(f"setup stopped; inspect or remove {WORKBENCH}", file=sys.stderr)
        raise
    print(f"BASELINE GREEN at {_git('rev-parse', BASE_REF, capture=True)}")
    print(f"trusted base: {BASE_REF}")
    print(f"workbench: {REPOSITORY}")


def _verify_repository() -> None:
    if REPOSITORY.is_symlink() or not (REPOSITORY / ".git").is_dir():
        raise DemoError(f"expected workbench repository is missing: {REPOSITORY}")
    if REPOSITORY.resolve().parent != WORKBENCH.resolve():
        raise DemoError("workbench repository resolved outside the demo workbench")
    base = _git("rev-parse", f"{BASE_REF}^{{commit}}", capture=True)
    head = _git("rev-parse", "HEAD", capture=True)
    if len(base) != 40 or head != base:
        raise DemoError(f"trusted base {BASE_REF} is not the workbench HEAD")
    policy = _git("show", f"{BASE_REF}:.release-gate.yaml", capture=True)
    expected = (ASSETS / ".release-gate.yaml").read_text(encoding="utf-8")
    if policy.rstrip("\n") != expected.rstrip("\n"):
        raise DemoError("trusted base policy does not match the reviewed asset")


def _remove_owned_directory(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.resolve().parent != WORKBENCH.resolve():
        raise DemoError(f"refusing to remove unsafe demo path: {path}")
    shutil.rmtree(path)


def reset() -> None:
    _verify_repository()
    _git("reset", "--hard", BASE_REF)
    _git("clean", "-fdx", "-e", ".release-gate/runs/")
    _remove_owned_directory(TASK_VENV)
    _remove_owned_directory(ORACLE_VENV)
    _create_environment(TASK_VENV)
    _verify_baseline()
    print(f"reset: {BASE_REF}")


def control(scenario: str) -> None:
    reset()
    patch = CONTROLS / f"{scenario}.patch"
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
    print(f"base commit: {summary.base_commit}")
    print(f"candidate tree: {summary.candidate_tree}")
    print(f"patch sha256: {summary.patch_sha256}")
    print(f"config sha256: {summary.config_sha256}")
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


def _oracle_truth() -> bool | None:
    _remove_owned_directory(ORACLE_VENV)
    _create_environment(ORACLE_VENV, oracle_only=True)
    result = _run(
        (
            _venv_python(ORACLE_VENV),
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
    print(result.stderr.rstrip(), file=sys.stderr)
    return None


def grade(path: Path) -> str:
    _verify_repository()
    summary = inspect_result(path)
    correct = _oracle_truth()
    classification = classify_oracle(summary.verdict, correct)
    truth = "oracle error" if correct is None else ("correct" if correct else "wrong")
    print(f"truth: {truth}")
    print(f"classification: {classification}")
    return classification


def _result_path(stdout: str) -> Path:
    paths = [
        line.removeprefix("RESULT: ")
        for line in stdout.splitlines()
        if line.startswith("RESULT: ")
    ]
    if len(paths) != 1:
        raise DemoError("gate output did not contain exactly one RESULT path")
    return Path(paths[0])


def _verify_oracle_mutants() -> None:
    _remove_owned_directory(ORACLE_VENV)
    _create_environment(ORACLE_VENV, oracle_only=True)
    result = _run(
        (_venv_python(ORACLE_VENV), "tools/mutants.py", ORACLE),
        cwd=REPOSITORY,
        check=False,
        capture=True,
    )
    print(result.stdout.rstrip())
    if result.returncode != 0 or "8/8 mutants killed" not in result.stdout:
        raise DemoError("reference oracle did not kill all eight mutants")


def verify() -> None:
    if WORKBENCH.exists():
        _verify_repository()
        reset()
    else:
        setup()
    _verify_oracle_mutants()
    expected = {
        "pass": (0, "PASS", "good_pass"),
        "fail": (1, "FAIL", "good_catch"),
        "needs-human": (2, "NEEDS_HUMAN", "escalated"),
    }
    CONTROL_EVIDENCE.mkdir(mode=0o700, exist_ok=True)
    for scenario, (exit_code, verdict, classification) in expected.items():
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
            raise DemoError(f"{scenario}: expected {verdict}, got {summary.verdict}")
        actual = grade(result_path)
        if actual != classification:
            raise DemoError(f"{scenario}: expected {classification}, got {actual}")
    reset()
    print("verify: PASS, FAIL, and NEEDS_HUMAN controls matched expectations")


def _require_gate_version() -> None:
    actual = _run(_gate_argv("--version"), capture=True).stdout.strip()
    if actual != EXPECTED_GATE_VERSION:
        raise DemoError(
            f"expected {EXPECTED_GATE_VERSION!r}, got {actual!r}; install this checkout"
        )


def _dispatch(arguments: argparse.Namespace) -> None:
    handlers: dict[str, Callable[[], None]] = {
        "doctor": doctor,
        "setup": setup,
        "reset": reset,
        "verify": verify,
        "inspect": lambda: inspect_result(arguments.result),
        "grade": lambda: grade(arguments.result),
        "control": lambda: control(arguments.scenario),
    }
    try:
        handler = handlers[arguments.command]
    except KeyError as error:
        raise DemoError(f"unsupported command: {arguments.command}") from error
    handler()


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        _dispatch(arguments)
    except DemoError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
