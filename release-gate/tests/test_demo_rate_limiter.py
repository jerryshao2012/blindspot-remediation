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

    for command in ("doctor", "setup", "reset", "verify", "verify-repair"):
        assert parser.parse_args([command]).command == command
    parsed_repair = parser.parse_args(["prepare-repair"])
    assert parsed_repair.command == "prepare-repair"
    assert parsed_repair.graphify == "missing"
    assert parser.parse_args(
        ["prepare-repair", "--graphify", "stale"]
    ).graphify == "stale"
    with pytest.raises(SystemExit):
        parser.parse_args(["prepare-repair", "--graphify", "fresh"])
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


def test_demo_uses_non_editable_local_installs_for_portable_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    commands: list[tuple[object, ...]] = []

    def record(arguments: tuple[object, ...], **_: object) -> None:
        commands.append(arguments)

    monkeypatch.setattr(driver, "_run", record)
    monkeypatch.setattr(driver, "REPOSITORY", tmp_path / "rate-limiter")
    driver._create_environment(tmp_path / "oracle-venv", oracle_only=True)

    install = commands[1]
    assert "-e" not in install
    assert driver.REPOSITORY in install
    requirements = (DEMO / "requirements-dev.txt").read_text(encoding="utf-8")
    assert requirements.startswith(".\n")
    assert "-e ." not in requirements


def test_baseline_copy_supports_explicit_nested_source_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    repository = tmp_path / "workbench" / "rate-limiter"
    repository.parent.mkdir()
    monkeypatch.setattr(driver, "REPOSITORY", repository)

    driver._copy_baseline()

    assert (repository / "tools" / "gauntlet.py").read_bytes() == (
        DEMO / "tools" / "gauntlet.py"
    ).read_bytes()
    assert not (repository / "tools" / "gauntlet 2.py").exists()


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
                "base_commit": "a" * 40,
                "candidate_tree": "b" * 40,
                "patch_sha256": "c" * 64,
                "config_sha256": "d" * 64,
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
    assert summary.base_commit == "a" * 40
    assert summary.candidate_tree == "b" * 40
    assert summary.patch_sha256 == "c" * 64
    assert summary.config_sha256 == "d" * 64
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


def test_repair_patches_apply_sequentially_and_end_green(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    shutil.copytree(
        DEMO,
        repository,
        ignore=shutil.ignore_patterns("workbench", ".venv", "__pycache__"),
    )
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
    base_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    trees: list[str] = []
    digests: list[str] = []

    for patch_name in ("C0.patch", "C1.patch", "C2.patch"):
        patch = DEMO / "repairs" / patch_name
        subprocess.run(
            ["git", "apply", "--check", str(patch)],
            cwd=repository,
            check=True,
        )
        subprocess.run(["git", "apply", str(patch)], cwd=repository, check=True)
        subprocess.run(["git", "add", "-A"], cwd=repository, check=True)
        tree = subprocess.run(
            ["git", "write-tree"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        diff = subprocess.run(
            [
                "git",
                "diff-tree",
                "--no-commit-id",
                "--binary",
                "--full-index",
                "--no-color",
                "--no-ext-diff",
                "--find-renames",
                "-r",
                "-p",
                base_tree,
                tree,
            ],
            cwd=repository,
            check=True,
            capture_output=True,
        ).stdout
        trees.append(tree)
        digests.append(__import__("hashlib").sha256(diff).hexdigest())

    source = (repository / "src" / "ratelimiter" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "now - hits[0] > self._window" in source
    assert "A limiter should use an injected monotonic clock in production." in (
        repository / "README.md"
    ).read_text(encoding="utf-8")
    assert len({*trees}) == 3
    assert len({*digests}) == 3


def test_generated_trusted_base_ignores_graphify_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    repository = tmp_path / "rate-limiter"
    repository.mkdir()
    monkeypatch.setattr(driver, "REPOSITORY", repository)

    (repository / ".gitignore").write_text("/.release-gate/runs/\n", encoding="utf-8")

    driver._ensure_gitignore_entry("/graphify-out/")

    assert "/graphify-out/" in (repository / ".gitignore").read_text(encoding="utf-8")


def test_prepare_graphify_modes_create_missing_or_stale_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    repository = tmp_path / "rate-limiter"
    graph = repository / "graphify-out" / "graph.json"
    repository.mkdir()
    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(driver, "_git", lambda *args, capture=False: "a" * 40)

    driver._prepare_graphify_fixture("missing")
    assert not graph.exists()

    driver._prepare_graphify_fixture("stale")
    payload = json.loads(graph.read_text(encoding="utf-8"))
    assert payload["built_at_commit"] == "0" * 40
    assert payload["built_at_commit"] != "a" * 40


def test_repair_preparation_refuses_leftover_approval_or_temp_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench = tmp_path / "workbench"
    approvals = workbench / "approvals"
    repair_temp = workbench / "repair-temp"
    workbench.mkdir()
    approvals.mkdir()
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "APPROVALS", approvals)
    monkeypatch.setattr(driver, "REPAIR_TEMP", repair_temp)

    with pytest.raises(driver.DemoError, match=r"demo[.]py reset"):
        driver._ensure_no_repair_leftovers()


def test_repair_approval_files_bind_session_and_final_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    approvals = tmp_path / "approvals"
    monkeypatch.setattr(driver, "APPROVALS", approvals)

    start = driver._write_start_approval("rep-demo")
    assert json.loads(start.read_text(encoding="utf-8"))["session_id"] == "rep-demo"

    final = driver._write_final_approval(
        "rep-demo",
        final_candidate_tree="b" * 40,
        final_patch_digest="c" * 64,
    )
    final_doc = json.loads(final.read_text(encoding="utf-8"))
    assert final_doc["session_id"] == "rep-demo"
    assert final_doc["final_candidate_tree"] == "b" * 40
    assert final_doc["final_patch_digest"] == "c" * 64
    assert final_doc["approved_at"].endswith("Z")


def test_repair_protocol_output_parsing_and_state_assertions() -> None:
    driver = load_driver()
    output = "\n".join(
        (
            "REPAIR_SESSION: /tmp/session",
            "REPAIR_STATE: awaiting_approval",
            "NEXT_ACTION: approve_or_cancel",
        )
    )

    assert driver._output_value(output, "REPAIR_SESSION") == "/tmp/session"
    driver._assert_repair_state(
        output, state="awaiting_approval", next_action="approve_or_cancel"
    )
    with pytest.raises(driver.DemoError, match="expected repair state"):
        driver._assert_repair_state(
            output, state="repairing", next_action="edit_workspace"
        )


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
        "uv run --python 3.12 --no-project python demo.py verify-repair",
        "verify-repair: C0 FAIL -> C1 FAIL -> C2 PASS -> applied",
        "demo.py prepare-repair --graphify stale",
        "/release-gate repair --base release-gate-rate-limiter-base",
        "awaiting_approval",
        "awaiting_final_approval",
        "workbench\\approvals",
        "workbench/repair-temp",
        "Graphify",
        "successful live host observation remains pending until Copilot is available",
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
    script = (DEMO / "tools" / "source_state.py").read_text(encoding="utf-8")

    for path in ("assets", "controls", "demo.py", "oracle", "README.md"):
        assert path in script


def test_source_state_manifest_is_deterministic_and_length_delimited(
    tmp_path: Path,
) -> None:
    source_state = load_module(
        "rate_limiter_source_state", DEMO / "tools" / "source_state.py"
    )
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "bc").write_bytes(b"d")
    (tmp_path / "ab").write_bytes(b"cd")

    first = source_state.content_manifest(tmp_path, ("a", "ab"))
    second = source_state.content_manifest(tmp_path, ("ab", "a"))

    assert first == second
    assert len(first.digest) == 64
    assert first.files == ("a/bc", "ab")


def test_source_state_manifest_rejects_missing_and_special_inputs(
    tmp_path: Path,
) -> None:
    source_state = load_module(
        "rate_limiter_source_state_errors", DEMO / "tools" / "source_state.py"
    )
    with pytest.raises(source_state.SourceStateError, match="missing"):
        source_state.content_manifest(tmp_path, ("missing",))

    target = tmp_path / "target"
    target.write_text("content", encoding="utf-8")
    link = tmp_path / "link"
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")
    with pytest.raises(source_state.SourceStateError, match="regular file"):
        source_state.content_manifest(tmp_path, ("link",))


def test_gauntlet_ledger_rejects_missing_unknown_and_duplicate_layers() -> None:
    gauntlet = load_module("rate_limiter_gauntlet_ledger", DEMO / "tools/gauntlet.py")
    ledger = gauntlet.LayerLedger(("tests", "mutation"))

    assert ledger.complete("tests") == 0
    assert ledger.audit() == 1
    assert ledger.complete("unknown") == 2
    assert ledger.complete("tests") == 2


def test_gauntlet_records_success_only_and_propagates_child_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gauntlet = load_module("rate_limiter_gauntlet_exit", DEMO / "tools/gauntlet.py")
    ledger = gauntlet.LayerLedger(("tests", "later"))
    monkeypatch.setattr(
        gauntlet.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 7),
    )

    assert gauntlet.run_layer(ledger, "tests", ("python", "-V")) == 7
    assert ledger.completed == ()


def test_gauntlet_treats_child_spawn_failure_as_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gauntlet = load_module("rate_limiter_gauntlet_spawn", DEMO / "tools/gauntlet.py")
    ledger = gauntlet.LayerLedger(("tests",))

    def broken_spawn(*_args: object, **_kwargs: object) -> object:
        raise OSError("cannot execute")

    monkeypatch.setattr(gauntlet.subprocess, "run", broken_spawn)
    assert gauntlet.run_layer(ledger, "tests", ("missing",)) == 2
    assert ledger.completed == ()


def test_forbidden_scanner_handles_clean_violating_and_broken_inputs(
    tmp_path: Path,
) -> None:
    gauntlet = load_module("rate_limiter_gauntlet_scanner", DEMO / "tools/gauntlet.py")
    root = tmp_path / "src"
    root.mkdir()
    source = root / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    assert gauntlet.scan_forbidden("secret", (root,)) == 0
    source.write_text("secret = 1\n", encoding="utf-8")
    assert gauntlet.scan_forbidden("secret", (root,)) == 1
    assert gauntlet.scan_forbidden("secret", (tmp_path / "missing",)) == 2


def test_gauntlet_enforces_full_coverage_and_runs_negative_controls() -> None:
    text = (DEMO / "tools" / "gauntlet.py").read_text(encoding="utf-8")
    assert "--cov-fail-under=100" in text
    assert "orchestration controls" in text
    assert "checker controls" in text
    assert "--negative-control" in text
    assert '"tools/source_state.py", "--candidate"' in text


def test_gauntlet_and_mutation_runner_execute_candidate_source() -> None:
    gauntlet = load_module(
        "rate_limiter_gauntlet_environment", DEMO / "tools/gauntlet.py"
    )
    mutants = load_module("rate_limiter_mutant_environment", DEMO / "tools/mutants.py")
    expected = str(DEMO / "src")

    assert gauntlet.CHILD_ENV["PYTHONPATH"].split(os.pathsep)[0] == expected
    assert mutants.MUTANT_ENV["PYTHONPATH"].split(os.pathsep)[0] == expected


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


def test_mutation_runner_negative_control_is_cache_isolated_and_restores_bytes(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "demo"
    shutil.copytree(DEMO, copied, ignore=shutil.ignore_patterns("workbench", ".venv"))
    target = copied / "src" / "ratelimiter" / "__init__.py"
    before = target.read_bytes()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(copied / "src")

    result = subprocess.run(
        [sys.executable, "tools/mutants.py", "--negative-control"],
        cwd=copied,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "C1 killer: KILLED" in result.stdout
    assert "C2 equivalent: SURVIVED" in result.stdout
    assert "negative control: ok" in result.stdout
    assert target.read_bytes() == before
    assert not (target.parent / "__pycache__").exists()


def test_mutation_runner_treats_collection_failure_as_error(tmp_path: Path) -> None:
    copied = tmp_path / "demo"
    shutil.copytree(DEMO, copied, ignore=shutil.ignore_patterns("workbench", ".venv"))
    broken = copied / "broken-tests"
    broken.mkdir()
    (broken / "test_broken.py").write_text(
        "import dependency_that_does_not_exist\n", encoding="utf-8"
    )
    before = (copied / "src" / "ratelimiter" / "__init__.py").read_bytes()

    result = subprocess.run(
        [sys.executable, "tools/mutants.py", str(broken)],
        cwd=copied,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "ERROR" in result.stdout
    assert "8/8 mutants killed" not in result.stdout
    assert (copied / "src" / "ratelimiter" / "__init__.py").read_bytes() == before


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
