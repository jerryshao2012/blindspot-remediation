#!/usr/bin/env python3
"""Cross-platform driver for the python-slugify Release Gate demo."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from release_gate.evidence import EvidenceError, verify_run

DEMO_ROOT = Path(__file__).resolve().parent
ASSETS = DEMO_ROOT / "assets"
CONTROLS = DEMO_ROOT / "controls"
ORACLE = DEMO_ROOT / "oracle"
WORKBENCH = DEMO_ROOT / "workbench"
REPOSITORY = WORKBENCH / "python-slugify"
TASK_VENV = WORKBENCH / "task-venv"
ORACLE_VENV = WORKBENCH / "oracle-venv"
CONTROL_EVIDENCE = WORKBENCH / "evidence"
PRIVATE_CAMPAIGN = DEMO_ROOT / "private-campaign"
UPSTREAM_URL = "https://github.com/un33k/python-slugify.git"
UPSTREAM_SHA = "7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4"
BASE_REF = "release-gate-demo-base"
EXPECTED_GATE_VERSION = "release-gate 0.3.0"
TEST_TOOLS = ("pytest==8.4.2",)
RUN_KINDS = ("trial", "re-gate", "control")
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")


def _load_campaign_module() -> Any:
    name = "python_slugify_private_campaign"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    path = DEMO_ROOT / "campaign_report.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load private campaign module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


campaign_report = _load_campaign_module()


class DemoError(RuntimeError):
    """An expected, actionable demo error."""


class OracleGradeError(DemoError):
    """The oracle failed after its unknown result was durably recorded."""


@dataclass(frozen=True, slots=True)
class ResultSummary:
    run_id: str
    finished_at: str
    duration_ms: int
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


@dataclass(frozen=True, slots=True)
class CampaignMetadata:
    run_kind: str = "trial"
    wall_seconds: float | None = None
    usage_value: float | None = None
    usage_unit: str | None = None
    model: str | None = None
    human_step: str | None = None

    def __post_init__(self) -> None:
        if self.run_kind not in RUN_KINDS:
            raise DemoError(f"unsupported run_kind: {self.run_kind}")
        _optional_number(self.wall_seconds, "wall_seconds")
        _optional_number(self.usage_value, "usage_value")
        if (self.usage_value is None) != (self.usage_unit is None):
            raise DemoError("usage_value and usage_unit must be supplied together")
        _optional_metadata_text(self.usage_unit, "usage_unit", 32)
        _optional_metadata_text(self.model, "model", 256)
        _optional_metadata_text(self.human_step, "human_step", 256)


@dataclass(frozen=True, slots=True)
class OracleAssessment:
    truth: bool | None
    error: bool


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
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--result", required=True, type=Path)
    grade = commands.add_parser("grade")
    grade.add_argument("--result", required=True, type=Path)
    grade.add_argument("--run-kind", choices=RUN_KINDS, default="trial")
    grade.add_argument("--wall-seconds", type=float)
    grade.add_argument("--usage-value", type=float)
    grade.add_argument("--usage-unit")
    grade.add_argument("--model")
    grade.add_argument("--human-step")
    commands.add_parser(
        "campaign-report", help="regenerate the private campaign report"
    )
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
        result_bytes = path.read_bytes()
        value: object = json.loads(result_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DemoError(f"unable to read result JSON: {path}") from error
    return _parse_result_summary(value)


def load_result(path: Path) -> tuple[Path, bytes, ResultSummary]:
    """Load a result once, preserving the exact bytes used for its identity."""

    try:
        expanded = path.expanduser()
        _refuse_redirect(expanded)
        _refuse_redirect(expanded.absolute().parent)
        resolved = expanded.resolve(strict=True)
        result_bytes = resolved.read_bytes()
        value: object = json.loads(result_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DemoError(f"unable to read result JSON: {path}") from error
    return resolved, result_bytes, _parse_result_summary(value)


def _parse_result_summary(value: object) -> ResultSummary:
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
        finished_at=_required_string(value, "finished_at"),
        duration_ms=_required_non_negative_int(value, "duration_ms"),
        base_commit=_required_digest(value, "base_commit", _HEX_40),
        candidate_tree=_required_digest(value, "candidate_tree", _HEX_40),
        patch_sha256=_required_digest(value, "patch_sha256", _SHA256),
        config_sha256=_required_digest(value, "config_sha256", _SHA256),
        verdict=verdict,
        reason_codes=_string_tuple(value, "reason_codes"),
        changed_paths=_string_tuple(scope, "changed_paths"),
        outside_allowed_paths=_string_tuple(scope, "outside_allowed_paths"),
        forbidden_paths=_string_tuple(scope, "forbidden_paths"),
        review_required_paths=_string_tuple(scope, "review_required_paths"),
        checks=tuple(checks),
        manifest_path=_required_string(value, "manifest_path"),
    )


def _required_non_negative_int(value: dict[str, Any], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise DemoError(f"result {key} must be a non-negative integer")
    return item


def _required_digest(
    value: dict[str, Any], key: str, pattern: re.Pattern[str]
) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not pattern.fullmatch(item):
        raise DemoError(f"result {key} is invalid")
    return item


def _optional_number(value: object, label: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DemoError(f"{label} must be numeric")
    if not math.isfinite(float(value)) or value < 0:
        raise DemoError(f"{label} must be finite and non-negative")


def _optional_metadata_text(
    value: object, label: str, maximum_length: int
) -> None:
    if value is None:
        return
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum_length
        or _CONTROL_CHARACTER.search(value)
    ):
        raise DemoError(f"{label} is invalid")


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


def _run_bytes(
    argv: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path,
    input_bytes: bytes,
) -> bytes:
    command = [os.fspath(argument) for argument in argv]
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            input=input_bytes,
            check=True,
            capture_output=True,
        ).stdout
    except FileNotFoundError as error:
        raise DemoError(f"required executable is unavailable: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
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
    resolved, _, summary = load_result(path)
    manifest = resolved.parent / summary.manifest_path
    if not manifest.is_file() or (resolved.parent / ".incomplete").exists():
        raise DemoError("evidence package is incomplete or missing manifest.json")
    _print_result_summary(resolved, summary)
    return summary


def _print_result_summary(resolved: Path, summary: ResultSummary) -> None:
    manifest = resolved.parent / summary.manifest_path
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


def grade(
    path: Path, *, metadata: CampaignMetadata, record: bool = True
) -> str:
    resolved, result_bytes, summary = load_result(path)
    _print_result_summary(resolved, summary)
    oracle_digest = oracle_source_sha256()
    with reconstruct_oracle_candidate(resolved, summary) as candidate:
        assessment = _oracle_assessment(candidate, ORACLE_VENV)
    if assessment.error or assessment.truth is None:
        box = "oracle_error"
        print("truth: unknown (oracle error)")
    else:
        box = classify_oracle(summary.verdict, assessment.truth)
        print(f"truth: {'correct' if assessment.truth else 'wrong'}")
    print(f"classification: {box}")
    if record:
        campaign_record = {
            "version": 1,
            "run_id": summary.run_id,
            "run_kind": metadata.run_kind,
            "gate": {
                "verdict": summary.verdict,
                "finished_at": summary.finished_at,
                "duration_ms": summary.duration_ms,
                "base_commit": summary.base_commit,
                "candidate_tree": summary.candidate_tree,
                "patch_sha256": summary.patch_sha256,
                "config_sha256": summary.config_sha256,
                "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
            },
            "oracle": {
                "truth": assessment.truth,
                "classification": box,
                "source_sha256": oracle_digest,
                "graded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
            "ai": {
                "wall_seconds": metadata.wall_seconds,
                "usage_value": metadata.usage_value,
                "usage_unit": metadata.usage_unit,
                "model": metadata.model,
                "human_step": metadata.human_step,
            },
        }
        try:
            paths = campaign_report.record_and_refresh(
                PRIVATE_CAMPAIGN, campaign_record
            )
        except campaign_report.CampaignError as error:
            raise DemoError(str(error)) from error
        print(f"CAMPAIGN_RECORD: {paths.record}")
        print(f"CAMPAIGN_REPORT: {paths.report}")
        print(f"CAMPAIGN_DATA: {paths.data}")
    if assessment.error or assessment.truth is None:
        raise OracleGradeError("oracle error was recorded in the private campaign")
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
        actual_box = grade(
            result_path,
            metadata=CampaignMetadata(
                run_kind="control", human_step="deterministic control"
            ),
            record=False,
        )
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


@contextmanager
def reconstruct_oracle_candidate(
    result_path: Path, summary: ResultSummary
) -> Iterator[Path]:
    """Yield the exact candidate tree recorded by verified gate evidence."""

    _verify_repository()
    evidence_root = result_path.parent
    _refuse_evidence_redirects(evidence_root)
    try:
        verify_run(evidence_root)
    except (EvidenceError, OSError) as error:
        raise DemoError(f"evidence verification failed: {error}") from error
    verified_summary = read_result_summary(result_path)
    if verified_summary != summary:
        raise DemoError("verified result identity changed during grading")
    patch_path = evidence_root / "candidate.patch"
    try:
        patch = patch_path.read_bytes()
    except OSError as error:
        raise DemoError("verified candidate patch is unreadable") from error
    if hashlib.sha256(patch).hexdigest() != summary.patch_sha256:
        raise DemoError("candidate patch digest does not match result identity")

    WORKBENCH.mkdir(mode=0o700, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix="oracle-candidate-", dir=WORKBENCH)
    ).absolute()
    os.chmod(temporary, 0o700)
    candidate = temporary / "repository"
    try:
        try:
            _git("cat-file", "-e", f"{summary.base_commit}^{{commit}}")
        except DemoError as error:
            raise DemoError("recorded base commit is unavailable") from error
        try:
            _run(
                (
                    "git",
                    "-c",
                    "protocol.file.allow=always",
                    "clone",
                    "--no-hardlinks",
                    "--no-checkout",
                    "--quiet",
                    REPOSITORY,
                    candidate,
                )
            )
            _git("checkout", "--detach", "--force", summary.base_commit, cwd=candidate)
            _run_bytes(
                (
                    "git",
                    "apply",
                    "--binary",
                    "--index",
                    "--whitespace=nowarn",
                    "-",
                ),
                cwd=candidate,
                input_bytes=patch,
            )
            actual_tree = _git("write-tree", cwd=candidate, capture=True)
        except DemoError as error:
            raise DemoError(
                "recorded candidate could not be cloned or patch applied"
            ) from error
        if actual_tree != summary.candidate_tree:
            raise DemoError(
                "reconstructed candidate tree mismatch: "
                f"expected {summary.candidate_tree}, got {actual_tree}"
            )
        yield candidate
    finally:
        _remove_owned_directory(temporary)


def oracle_source_sha256() -> str:
    """Hash the complete hidden-oracle source set with path boundaries."""

    try:
        _refuse_redirect(ORACLE)
        if not ORACLE.is_dir():
            raise DemoError("oracle source directory is missing")
        files: list[Path] = []
        for path in ORACLE.rglob("*"):
            _refuse_redirect(path)
            if path.is_dir():
                continue
            if not path.is_file():
                raise DemoError(f"oracle source is not an ordinary file: {path}")
            files.append(path)
        files.sort(key=lambda item: item.relative_to(ORACLE).as_posix())
        if not files:
            raise DemoError("oracle source set is empty")
        digest = hashlib.sha256()
        for path in files:
            relative = path.relative_to(ORACLE).as_posix().encode("utf-8")
            content = path.read_bytes()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
        return digest.hexdigest()
    except DemoError as error:
        raise DemoError(f"oracle source set is invalid: {error}") from error
    except (OSError, UnicodeError) as error:
        raise DemoError(f"oracle source set is unreadable: {error}") from error


def _oracle_assessment(repository: Path, environment: Path) -> OracleAssessment:
    try:
        _remove_owned_directory(environment)
        _run((*host_python_argv(), "-m", "venv", environment))
        _run(
            (
                *_task_pip(environment),
                "install",
                "--disable-pip-version-check",
                "-q",
                "-e",
                repository,
                *TEST_TOOLS,
            )
        )
        result = _run(
            (
                _task_python(environment),
                "-m",
                "pytest",
                ORACLE,
                "-q",
                "-p",
                "no:cacheprovider",
            ),
            cwd=repository,
            check=False,
            capture=True,
        )
    except (DemoError, OSError):
        return OracleAssessment(truth=None, error=True)
    print(result.stdout.rstrip())
    if result.returncode == 0:
        return OracleAssessment(truth=True, error=False)
    if result.returncode == 1:
        return OracleAssessment(truth=False, error=False)
    return OracleAssessment(truth=None, error=True)


def _remove_owned_directory(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.resolve().parent != WORKBENCH.resolve():
        raise DemoError(f"refusing to remove unsafe demo path: {path}")
    shutil.rmtree(path)


def _refuse_redirect(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise DemoError(f"path is missing or unreadable: {path}") from error
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if stat.S_ISLNK(metadata.st_mode) or (reparse and attributes & reparse):
        raise DemoError(f"refusing symlink or reparse-point path: {path}")


def _refuse_evidence_redirects(root: Path) -> None:
    _refuse_redirect(root)
    if not root.is_dir():
        raise DemoError(f"evidence root is not a directory: {root}")
    try:
        paths = list(root.rglob("*"))
    except OSError as error:
        raise DemoError(f"evidence root is unreadable: {root}") from error
    for path in paths:
        _refuse_redirect(path)


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
            metadata = CampaignMetadata(
                run_kind=arguments.run_kind,
                wall_seconds=arguments.wall_seconds,
                usage_value=arguments.usage_value,
                usage_unit=arguments.usage_unit,
                model=arguments.model,
                human_step=arguments.human_step,
            )
            grade(arguments.result, metadata=metadata)
        elif arguments.command == "campaign-report":
            try:
                paths = campaign_report.refresh(PRIVATE_CAMPAIGN)
            except campaign_report.CampaignError as error:
                raise DemoError(str(error)) from error
            print(f"CAMPAIGN_REPORT: {paths.report}")
            print(f"CAMPAIGN_DATA: {paths.data}")
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
