from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from release_gate.config import load_config
from release_gate.models import PlatformName

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "python-slugify"
DRIVER = DEMO / "demo.py"
POLICY = DEMO / "assets" / ".release-gate.yaml"


def load_driver() -> ModuleType:
    spec = importlib.util.spec_from_file_location("python_slugify_demo", DRIVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parser_exposes_simplified_demo_commands() -> None:
    driver = load_driver()
    parser = driver.build_parser()

    for command in ("doctor", "setup", "reset", "verify"):
        assert parser.parse_args([command]).command == command
    for command in ("inspect", "grade"):
        parsed = parser.parse_args([command, "--result", "result.json"])
        assert parsed.command == command
    assert parser.parse_args(["control", "pass"]).scenario == "pass"
    with pytest.raises(SystemExit):
        parser.parse_args(["control", "unknown"])
    with pytest.raises(SystemExit):
        parser.parse_args(["campaign-report"])


def test_platform_support_is_explicit() -> None:
    driver = load_driver()

    assert driver.require_supported_platform("win32") is None
    assert driver.require_supported_platform("darwin") is None
    with pytest.raises(driver.DemoError, match="Windows and macOS"):
        driver.require_supported_platform("linux")


def test_classify_oracle_preserves_escalation_precedence() -> None:
    driver = load_driver()

    assert driver.classify_oracle("PASS", True) == "good_pass"
    assert driver.classify_oracle("PASS", False) == "FALSE_RELEASE"
    assert driver.classify_oracle("FAIL", True) == "FALSE_BLOCK"
    assert driver.classify_oracle("FAIL", False) == "good_catch"
    assert driver.classify_oracle("NEEDS_HUMAN", True) == "escalated"


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
                    "changed_paths": ["setup.py"],
                    "outside_allowed_paths": [],
                    "forbidden_paths": [],
                    "review_required_paths": [],
                },
                "checks": [
                    {
                        "id": "tests-and-coverage",
                        "status": "PASS",
                        "reason_codes": [],
                    }
                ],
                "manifest_path": "manifest.json",
            }
        ),
        encoding="utf-8",
    )

    summary = driver.read_result_summary(result)

    assert summary.run_id == "control-pass"
    assert summary.verdict == "PASS"
    assert summary.changed_paths == ("setup.py",)
    assert summary.checks == (("tests-and-coverage", "PASS", ()),)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ({}, "version"),
        ({"version": 1}, "run_id"),
        (
            {
                "version": 1,
                "run_id": "run",
                "verdict": "UNKNOWN",
                "scope": {},
                "checks": [],
                "reason_codes": [],
                "manifest_path": "manifest.json",
            },
            "verdict",
        ),
    ],
)
def test_result_summary_rejects_invalid_results(
    tmp_path: Path, value: object, message: str
) -> None:
    driver = load_driver()
    result = tmp_path / "result.json"
    result.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(driver.DemoError, match=message):
        driver.read_result_summary(result)


def test_gate_invocation_prefers_sibling_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "release-gate"
    python = bin_dir / "python"
    shim.touch()
    python.touch()
    monkeypatch.setattr(driver.shutil, "which", lambda name: str(shim))
    monkeypatch.setattr(driver.sys, "platform", "darwin")

    assert driver._gate_argv("--version") == (
        python,
        "-m",
        "release_gate",
        "--version",
    )


def test_demo_policy_is_valid_and_resolves_on_both_platforms() -> None:
    config = load_config(POLICY)

    assert config.scope.forbidden_paths == (
        "/test.py",
        ".github/**",
        "/.vscode/**",
    )
    assert [control.id for control in config.prepare] == [
        "create-demo-venv",
        "install-build-tools",
        "install-demo-dependencies",
    ]
    assert [check.id for check in config.checks] == [
        "tests-and-coverage",
        "task-consistency",
        "types",
    ]
    for platform in (PlatformName.WINDOWS, PlatformName.MACOS):
        for control in (*config.prepare, *config.checks):
            assert control.resolve(platform).argv


def test_demo_dependency_preparation_is_build_isolation_safe() -> None:
    driver = load_driver()
    config = load_config(POLICY)
    environment, build_tools, dependencies = config.prepare

    assert environment.argv == (
        "uv",
        "venv",
        "--python",
        "3.12",
        "--seed",
        ".release-gate-venv",
    )
    assert environment.resolve(PlatformName.WINDOWS).argv == environment.argv

    assert "setuptools>=61.2" in build_tools.argv
    assert "wheel>=0.37" in build_tools.argv
    assert build_tools.argv[:3] == ("uv", "pip", "install")
    assert dependencies.argv[:3] == ("uv", "pip", "install")
    assert "wheel>=0.37" in driver.BUILD_TOOLS
    assert "--no-build-isolation" in dependencies.argv
    assert dependencies.environment["PIP_NO_CACHE_DIR"] == "1"
    assert build_tools.inherit_environment == ("PATH",)
    assert dependencies.inherit_environment == ("PATH",)


def test_committed_demo_assets_and_windows_guidance_are_self_contained() -> None:
    expected = {
        DEMO / ".gitignore",
        DEMO / "README.md",
        POLICY,
        DEMO / "assets" / "TASK.md",
        DEMO / "controls" / "pass.patch",
        DEMO / "controls" / "fail.patch",
        DEMO / "controls" / "needs-human.patch",
        DEMO / "oracle" / "test_x1_oracle.py",
    }
    assert not [path for path in expected if not path.is_file()]

    readme = (DEMO / "README.md").read_text(encoding="utf-8")
    for phrase in (
        "Choose a path",
        "uv tool install --force .\\release-gate",
        "cd .\\release-gate\\demo\\python-slugify",
        "uv run --python 3.12 --no-project python demo.py verify",
        "uv pip install",
        "demo.py verify",
        "C:\\rg-temp",
        "PREPARATION_FAILED",
        "outside allowed: test.py",
        "review required: .release-gate.yaml",
        "Corporate proxy settings",
    ):
        assert phrase in readme
    assert "workbench/" in (DEMO / ".gitignore").read_text(encoding="utf-8")


def test_trusted_base_validation_checks_origin_parent_and_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench = tmp_path / "workbench"
    repository = workbench / "python-slugify"
    repository.mkdir(parents=True)

    def git(*arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Demo Test")
    git("config", "user.email", "demo-test@example.invalid")
    git("remote", "add", "origin", driver.UPSTREAM_URL)
    (repository / "tracked.txt").write_text("upstream\n", encoding="utf-8")
    git("add", "tracked.txt")
    git("commit", "-qm", "upstream")
    upstream = git("rev-parse", "HEAD")
    (repository / ".release-gate.yaml").write_bytes(POLICY.read_bytes())
    (repository / ".gitignore").write_text("/.release-gate/runs/\n", encoding="utf-8")
    git("add", ".release-gate.yaml", ".gitignore")
    git("commit", "-qm", "policy")
    git("tag", driver.BASE_REF)

    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(driver, "UPSTREAM_SHA", upstream)

    driver._verify_repository()
    git("remote", "set-url", "origin", "https://example.invalid/wrong.git")
    with pytest.raises(driver.DemoError, match="unexpected workbench origin"):
        driver._verify_repository()


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
