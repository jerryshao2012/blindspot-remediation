from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from release_gate.config import load_config
from release_gate.models import PlatformName

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "rate-limiter"
DRIVER = DEMO / "demo.py"
POLICY = DEMO / "assets" / ".release-gate.yaml"
ORACLE = DEMO / "oracle" / "test_ratelimiter_oracle.py"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_driver() -> ModuleType:
    return load_module("rate_limiter_demo", DRIVER)


def test_rate_limiter_demo_contains_repeatable_release_gate_assets() -> None:
    expected = {
        DEMO / ".gitignore",
        DEMO / "README.md",
        DEMO / "demo.py",
        DEMO / "assets" / ".release-gate.yaml",
        DEMO / "controls" / "pass.patch",
        DEMO / "controls" / "fail.patch",
        DEMO / "controls" / "needs-human.patch",
        DEMO / "oracle" / "test_ratelimiter_oracle.py",
        DEMO / "tools" / "gauntlet.py",
    }

    assert not [path for path in expected if not path.is_file()]


def test_parser_exposes_rate_limiter_demo_commands() -> None:
    driver = load_driver()
    parser = driver.build_parser()

    for command in ("doctor", "setup", "reset", "verify"):
        assert parser.parse_args([command]).command == command
    for command in ("inspect", "grade"):
        parsed = parser.parse_args([command, "--result", "result.json"])
        assert parsed.command == command
    for scenario in ("pass", "fail", "needs-human"):
        assert parser.parse_args(["control", scenario]).scenario == scenario
    with pytest.raises(SystemExit):
        parser.parse_args(["control", "unknown"])


def test_platform_support_is_explicit() -> None:
    driver = load_driver()

    assert driver.require_supported_platform("win32") is None
    assert driver.require_supported_platform("darwin") is None
    with pytest.raises(driver.DemoError, match="Windows and macOS"):
        driver.require_supported_platform("linux")


def test_child_environments_require_uv_managed_python_3_12(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    commands: list[tuple[object, ...]] = []

    def record(arguments: tuple[object, ...], **_: object) -> None:
        commands.append(arguments)

    monkeypatch.setattr(driver, "_run", record)
    monkeypatch.setattr(driver, "REPOSITORY", tmp_path / "rate-limiter")

    driver._create_environment(tmp_path / "task-venv")

    assert commands[0] == (
        "uv",
        "venv",
        "--python",
        "3.12",
        "--seed",
        tmp_path / "task-venv",
    )


def test_oracle_classification_preserves_gate_verdict() -> None:
    driver = load_driver()

    assert driver.classify_oracle("PASS", True) == "good_pass"
    assert driver.classify_oracle("PASS", False) == "FALSE_RELEASE"
    assert driver.classify_oracle("FAIL", True) == "FALSE_BLOCK"
    assert driver.classify_oracle("FAIL", False) == "good_catch"
    assert driver.classify_oracle("NEEDS_HUMAN", True) == "escalated"
    assert driver.classify_oracle("PASS", None) == "oracle_error"


def test_result_summary_reads_fields_used_by_the_demo(tmp_path: Path) -> None:
    driver = load_driver()
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "version": 1,
                "run_id": "control-pass",
                "verdict": "PASS",
                "reason_codes": [],
                "scope": {
                    "changed_paths": ["README.md"],
                    "outside_allowed_paths": [],
                    "forbidden_paths": [],
                    "review_required_paths": [],
                },
                "checks": [
                    {"id": "quality-gauntlet", "status": "PASS", "reason_codes": []}
                ],
                "manifest_path": "manifest.json",
            }
        ),
        encoding="utf-8",
    )

    summary = driver.read_result_summary(result)

    assert summary.run_id == "control-pass"
    assert summary.verdict == "PASS"
    assert summary.changed_paths == ("README.md",)
    assert summary.checks == (("quality-gauntlet", "PASS", ()),)


def test_rate_limiter_policy_is_valid_on_windows_and_macos() -> None:
    config = load_config(POLICY)

    assert config.scope.allowed_paths == ("/README.md", "src/**", "examples/**")
    assert "tests/**" in config.scope.forbidden_paths
    assert "/.release-gate.yaml" in config.scope.review_required_paths
    assert [control.id for control in config.prepare] == [
        "create-demo-venv",
        "install-demo-dependencies",
    ]
    assert config.prepare[0].argv == (
        "uv",
        "venv",
        "--python",
        "3.12",
        "--seed",
        ".release-gate-venv",
    )
    assert config.prepare[1].argv[:3] == ("uv", "pip", "install")
    assert [check.id for check in config.checks] == ["quality-gauntlet"]
    assert config.checks[0].mode.value == "differential"
    for platform in (PlatformName.WINDOWS, PlatformName.MACOS):
        for control in (*config.prepare, *config.checks):
            assert control.resolve(platform).argv


def test_reference_oracle_accepts_baseline_and_kills_all_mutants() -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(DEMO / "src")
    baseline = subprocess.run(
        [sys.executable, "-m", "pytest", str(ORACLE), "-q", "-p", "no:cacheprovider"],
        cwd=DEMO,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr

    mutants = subprocess.run(
        [sys.executable, "tools/mutants.py", str(ORACLE)],
        cwd=DEMO,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert mutants.returncode == 0, mutants.stdout + mutants.stderr
    assert "8/8 mutants killed" in mutants.stdout


def test_control_patches_apply_to_clean_baseline(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    for name in ("README.md", "src"):
        source = DEMO / name
        target = repository / name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    shutil.copy2(POLICY, repository / ".release-gate.yaml")

    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Demo Test"], cwd=repository, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "demo@example.invalid"],
        cwd=repository,
        check=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repository, check=True)
    for scenario, expected_path in (
        ("pass", "README.md"),
        ("fail", "src/ratelimiter/__init__.py"),
        ("needs-human", ".release-gate.yaml"),
    ):
        subprocess.run(
            ["git", "reset", "--hard", "HEAD"],
            cwd=repository,
            check=False,
            capture_output=True,
        )
        subprocess.run(
            ["git", "apply", "--check", str(DEMO / "controls" / f"{scenario}.patch")],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "apply", str(DEMO / "controls" / f"{scenario}.patch")],
            cwd=repository,
            check=True,
        )
        changed = subprocess.run(
            ["git", "status", "--short"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert expected_path in changed
        subprocess.run(["git", "checkout", "--", "."], cwd=repository, check=True)


def test_owned_directory_removal_refuses_paths_outside_workbench(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench = tmp_path / "workbench"
    outside = tmp_path / "outside"
    workbench.mkdir()
    outside.mkdir()
    monkeypatch.setattr(driver, "WORKBENCH", workbench)

    with pytest.raises(driver.DemoError, match="unsafe demo path"):
        driver._remove_owned_directory(outside)
    assert outside.is_dir()


def test_rate_limiter_readme_has_both_complete_operator_paths() -> None:
    readme = (DEMO / "README.md").read_text(encoding="utf-8")

    for phrase in (
        "Choose a path",
        "uv tool install --force .\\release-gate",
        "cd .\\release-gate\\demo\\rate-limiter",
        "uv run --python 3.12 --no-project python demo.py verify",
        "uv pip install",
        "demo.py verify",
        "/release-gate run --base release-gate-rate-limiter-base",
        "oracle_error",
        "POLICY_FILE_CHANGED",
        "VS Code Copilot Chat",
        "Where pytest is installed",
        ".\\workbench\\task-venv\\Scripts\\python.exe -m pytest",
        "./workbench/task-venv/bin/python -m pytest",
        "Python: Select Interpreter",
    ):
        assert phrase in readme


def test_source_state_covers_gate_policy_controls_driver_and_oracle() -> None:
    script = (DEMO / "tools" / "source_state.sh").read_text(encoding="utf-8")

    for path in ("assets", "controls", "demo.py", "oracle", "README.md"):
        assert path in script


def test_portable_gauntlet_passes_strict_type_checking() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", str(DEMO / "tools" / "gauntlet.py")],
        cwd=DEMO,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_mutation_runner_restores_crlf_source_byte_for_byte(tmp_path: Path) -> None:
    copied = tmp_path / "demo"
    shutil.copytree(DEMO, copied, ignore=shutil.ignore_patterns("workbench", ".venv"))
    target = copied / "src" / "ratelimiter" / "__init__.py"
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    before = target.read_bytes()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(copied / "src")

    result = subprocess.run(
        [sys.executable, "tools/mutants.py", str(ORACLE)],
        cwd=copied,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert target.read_bytes() == before


def test_successful_baseline_verification_cleans_generated_candidate_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    repository = tmp_path / "repository"
    repository.mkdir()
    task_venv = tmp_path / "task-venv"
    python = task_venv / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    calls: list[tuple[str, ...]] = []

    def run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        (repository / ".coverage").touch()
        return subprocess.CompletedProcess([], 0, "", "")

    def git(*arguments: str, capture: bool = False) -> str:
        del capture
        calls.append(arguments)
        return ""

    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(driver, "TASK_VENV", task_venv)
    monkeypatch.setattr(driver, "_run", run)
    monkeypatch.setattr(driver, "_git", git)
    monkeypatch.setattr(driver.sys, "platform", "darwin")

    driver._verify_baseline()

    assert ("clean", "-fdx", "-e", ".release-gate/runs/") in calls
