from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from release_gate.config import load_config
from release_gate.evidence import FINALIZATION_RESERVE, EvidenceRun
from release_gate.models import PlatformName

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "python-slugify"
DRIVER = DEMO / "demo.py"
POLICY = DEMO / "assets" / ".release-gate.yaml"


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git(repository: Path, *arguments: str, input_bytes: bytes | None = None) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        input=input_bytes,
        check=True,
        capture_output=True,
    )
    return result.stdout.decode().strip()


def _evidence_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    workbench = tmp_path / "workbench"
    repository = workbench / "python-slugify"
    repository.mkdir(parents=True)
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "Demo Test")
    _git(repository, "config", "user.email", "demo-test@example.invalid")
    source = repository / "candidate.txt"
    source.write_text("base\n", encoding="utf-8")
    _git(repository, "add", "candidate.txt")
    _git(repository, "commit", "-qm", "base")
    base_commit = _git(repository, "rev-parse", "HEAD")
    base_tree = _git(repository, "rev-parse", "HEAD^{tree}")
    source.write_text("recorded candidate\n", encoding="utf-8")
    _git(repository, "add", "candidate.txt")
    candidate_tree = _git(repository, "write-tree")
    patch = subprocess.run(
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
            candidate_tree,
        ],
        cwd=repository,
        check=True,
        capture_output=True,
    ).stdout
    _git(repository, "reset", "--hard", base_commit)
    source.write_text("mutable drift\n", encoding="utf-8")

    config = b"{}\n"
    started = "2026-08-20T12:00:00Z"
    finished = "2026-08-20T12:00:01Z"
    run = EvidenceRun.create(
        tmp_path / "evidence",
        "recorded-run",
        total_bytes=FINALIZATION_RESERVE + len(patch) + len(config),
        patch=patch,
        effective_config=config,
    )
    result = {
        "version": 1,
        "run_id": "recorded-run",
        "verdict": "PASS",
        "exit_code": 0,
        "reason_codes": [],
        "started_at": started,
        "finished_at": finished,
        "duration_ms": 1000,
        "base_commit": base_commit,
        "candidate_tree": candidate_tree,
        "patch_sha256": _sha(patch),
        "config_sha256": _sha(config),
        "scope": {
            "status": "PASS",
            "reason_codes": [],
            "changed_paths": ["candidate.txt"],
            "outside_allowed_paths": [],
            "forbidden_paths": [],
            "review_required_paths": [],
        },
        "checks": [
            {
                "id": "check",
                "mode": "candidate",
                "severity": "blocking",
                "status": "PASS",
                "reason_codes": [],
                "assertions": [],
            }
        ],
        "manifest_path": "manifest.json",
    }
    execution = {
        "control_id": "check",
        "phase": "check",
        "side": "candidate",
        "argv": ["true"],
        "cwd": ".",
        "environment_keys": ["PATH"],
        "started_at": started,
        "finished_at": finished,
        "duration_ms": 1000,
        "classification": "pass",
        "exit_code": 0,
        "timed_out": False,
        "reason_codes": [],
        "metrics": {},
    }
    manifest = {
        "version": 1,
        "run_id": "recorded-run",
        "hash_algorithm": "sha256",
        "created_at": finished,
        "started_at": started,
        "finished_at": finished,
        "duration_ms": 1000,
        "base_commit": base_commit,
        "candidate_tree": candidate_tree,
        "patch_sha256": _sha(patch),
        "config_sha256": _sha(config),
        "engine_version": "0.3.0",
        "platform": {
            "family": "macos",
            "system": "Darwin",
            "release": "test",
            "machine": "arm64",
        },
        "runtime": {
            "implementation": "CPython",
            "version": "3.13.0",
            "executable": "python",
            "executable_sha256": "a" * 64,
        },
        "reason_codes": [],
        "executions": [execution],
    }
    completed = run.finalize(result, manifest, b"[]\n")
    return workbench, completed / "result.json", candidate_tree


def load_driver() -> ModuleType:
    spec = importlib.util.spec_from_file_location("python_slugify_demo", DRIVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_demo_driver_is_committed() -> None:
    assert DRIVER.is_file()


def test_parser_exposes_documented_commands() -> None:
    driver = load_driver()

    parser = driver.build_parser()

    for command in ("doctor", "setup", "reset", "verify"):
        assert parser.parse_args([command]).command == command
    for command in ("inspect", "grade"):
        parsed = parser.parse_args([command, "--result", "result.json"])
        assert parsed.command == command
    parsed = parser.parse_args(
        [
            "grade",
            "--result",
            "result.json",
            "--run-kind",
            "re-gate",
            "--wall-seconds",
            "103",
            "--usage-value",
            "16.6",
            "--usage-unit",
            "AIC",
            "--model",
            "model-x",
            "--human-step",
            "dependency install",
        ]
    )
    assert parsed.run_kind == "re-gate"
    assert parsed.wall_seconds == 103.0
    assert parser.parse_args(["campaign-report"]).command == "campaign-report"
    assert parser.parse_args(["control", "pass"]).scenario == "pass"
    with pytest.raises(SystemExit):
        parser.parse_args(["control", "unknown"])


def test_platform_commands_are_native() -> None:
    driver = load_driver()

    assert driver.host_python_argv("win32") == ("py", "-3")
    assert driver.host_python_argv("darwin") == ("python3",)
    with pytest.raises(driver.DemoError, match="Windows and macOS"):
        driver.host_python_argv("linux")


def test_classify_oracle_preserves_escalation_precedence() -> None:
    driver = load_driver()

    assert driver.classify_oracle("PASS", True) == "good_pass"
    assert driver.classify_oracle("PASS", False) == "FALSE_RELEASE"
    assert driver.classify_oracle("FAIL", True) == "FALSE_BLOCK"
    assert driver.classify_oracle("FAIL", False) == "good_catch"
    assert driver.classify_oracle("NEEDS_HUMAN", True) == "escalated"


def test_result_summary_requires_a_complete_v1_result(tmp_path: Path) -> None:
    driver = load_driver()
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "version": 1,
                "run_id": "control-pass",
                "finished_at": "2026-08-20T12:00:00Z",
                "duration_ms": 1200,
                "base_commit": "a" * 40,
                "candidate_tree": "b" * 40,
                "patch_sha256": "c" * 64,
                "config_sha256": "d" * 64,
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
                        "assertions": [],
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
    assert summary.finished_at == "2026-08-20T12:00:00Z"
    assert summary.duration_ms == 1200
    assert summary.base_commit == "a" * 40
    assert summary.candidate_tree == "b" * 40
    assert summary.patch_sha256 == "c" * 64
    assert summary.config_sha256 == "d" * 64
    assert summary.changed_paths == ("setup.py",)
    assert summary.checks == (("tests-and-coverage", "PASS", ()),)

    result.write_text("{}", encoding="utf-8")
    with pytest.raises(driver.DemoError, match="version"):
        driver.read_result_summary(result)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"usage_value": 1.0}, "supplied together"),
        ({"usage_unit": "AIC"}, "supplied together"),
        ({"wall_seconds": -1.0}, "finite and non-negative"),
        ({"wall_seconds": float("nan")}, "finite and non-negative"),
        ({"usage_value": float("inf"), "usage_unit": "AIC"}, "finite"),
        ({"model": ""}, "model"),
        ({"model": "x" * 257}, "model"),
        ({"usage_value": 1.0, "usage_unit": "bad\nunit"}, "usage_unit"),
        ({"human_step": "bad\x00step"}, "human_step"),
    ],
)
def test_campaign_metadata_rejects_invalid_values(
    changes: dict[str, object], message: str
) -> None:
    driver = load_driver()
    values: dict[str, object] = {
        "run_kind": "trial",
        "wall_seconds": None,
        "usage_value": None,
        "usage_unit": None,
        "model": None,
        "human_step": None,
    }
    values.update(changes)

    with pytest.raises(driver.DemoError, match=message):
        driver.CampaignMetadata(**values)


def test_result_summary_rejects_missing_or_invalid_identity(tmp_path: Path) -> None:
    driver = load_driver()
    base = {
        "version": 1,
        "run_id": "identity",
        "finished_at": "2026-08-20T12:00:00Z",
        "duration_ms": 1,
        "base_commit": "a" * 40,
        "candidate_tree": "b" * 40,
        "patch_sha256": "c" * 64,
        "config_sha256": "d" * 64,
        "verdict": "PASS",
        "reason_codes": [],
        "scope": {
            "changed_paths": [],
            "outside_allowed_paths": [],
            "forbidden_paths": [],
            "review_required_paths": [],
        },
        "checks": [],
        "manifest_path": "manifest.json",
    }
    result = tmp_path / "result.json"
    for key, value in (("base_commit", None), ("duration_ms", -1)):
        candidate = dict(base)
        if value is None:
            candidate.pop(key)
        else:
            candidate[key] = value
        result.write_text(json.dumps(candidate), encoding="utf-8")
        with pytest.raises(driver.DemoError, match=key):
            driver.read_result_summary(result)


def test_reconstructs_exact_recorded_candidate_not_mutable_workbench(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench, result_path, candidate_tree = _evidence_fixture(tmp_path)
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", workbench / "python-slugify")
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    _, _, summary = driver.load_result(result_path)

    with driver.reconstruct_oracle_candidate(result_path, summary) as candidate:
        assert (candidate / "candidate.txt").read_text() == "recorded candidate\n"
        assert _git(candidate, "write-tree") == candidate_tree

    assert not list(workbench.glob("oracle-candidate-*"))


def test_reconstruction_verifies_inventory_before_reading_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench, result_path, _ = _evidence_fixture(tmp_path)
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", workbench / "python-slugify")
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    _, _, summary = driver.load_result(result_path)
    (result_path.parent / "trace.json").write_bytes(b"tampered")

    with pytest.raises(driver.DemoError, match="evidence verification failed"):
        with driver.reconstruct_oracle_candidate(result_path, summary):
            pytest.fail("tampered evidence must not yield a candidate")


@pytest.mark.parametrize("damage", ["missing-manifest", "incomplete", "patch"])
def test_reconstruction_rejects_incomplete_or_changed_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    driver = load_driver()
    workbench, result_path, _ = _evidence_fixture(tmp_path)
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", workbench / "python-slugify")
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    _, _, summary = driver.load_result(result_path)
    if damage == "missing-manifest":
        (result_path.parent / "manifest.json").unlink()
    elif damage == "incomplete":
        (result_path.parent / ".incomplete").write_bytes(b"")
    else:
        (result_path.parent / "candidate.patch").write_bytes(b"changed")

    with pytest.raises(driver.DemoError, match="evidence verification failed"):
        with driver.reconstruct_oracle_candidate(result_path, summary):
            pytest.fail("invalid evidence must not yield a candidate")


def test_load_result_refuses_symlink_redirect(tmp_path: Path) -> None:
    driver = load_driver()
    _, result_path, _ = _evidence_fixture(tmp_path)
    redirected = tmp_path / "redirected-result.json"
    redirected.symlink_to(result_path)

    with pytest.raises(driver.DemoError, match=r"symlink|reparse"):
        driver.load_result(redirected)


def test_reconstruction_rejects_unavailable_base_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench, result_path, _ = _evidence_fixture(tmp_path)
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", workbench / "python-slugify")
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    _, _, summary = driver.load_result(result_path)

    def unavailable(*args: object, **kwargs: object) -> str:
        raise driver.DemoError("missing object")

    monkeypatch.setattr(driver, "_git", unavailable)

    with pytest.raises(driver.DemoError, match=r"clone|base commit"):
        with driver.reconstruct_oracle_candidate(result_path, summary):
            pytest.fail("missing base must not yield a candidate")


def test_oracle_source_digest_covers_relative_paths_and_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    oracle = tmp_path / "oracle"
    oracle.mkdir()
    (oracle / "a.py").write_text("first", encoding="utf-8")
    (oracle / "b.py").write_text("second", encoding="utf-8")
    monkeypatch.setattr(driver, "ORACLE", oracle)

    first = driver.oracle_source_sha256()
    (oracle / "b.py").write_text("changed", encoding="utf-8")
    assert driver.oracle_source_sha256() != first
    (oracle / "b.py").unlink()
    (oracle / "b.py").symlink_to(oracle / "a.py")

    with pytest.raises(driver.DemoError, match="oracle source"):
        driver.oracle_source_sha256()


def test_grade_records_false_release_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench, result_path, _ = _evidence_fixture(tmp_path)
    campaign = tmp_path / "private-campaign"
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", workbench / "python-slugify")
    monkeypatch.setattr(driver, "ORACLE_VENV", workbench / "oracle-venv")
    monkeypatch.setattr(driver, "PRIVATE_CAMPAIGN", campaign)
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    monkeypatch.setattr(
        driver,
        "_oracle_assessment",
        lambda repository, environment: driver.OracleAssessment(False, False),
    )
    metadata = driver.CampaignMetadata(model="model-x", usage_value=2, usage_unit="AIC")

    assert driver.grade(result_path, metadata=metadata) == "FALSE_RELEASE"
    first = (campaign / "records" / "recorded-run.json").read_bytes()
    assert driver.grade(result_path, metadata=metadata) == "FALSE_RELEASE"

    data = json.loads((campaign / "campaign-v1.json").read_text())
    assert data["record_count"] == 1
    metric = data["primary"]["metrics"]["false_release_per_total"]
    assert (metric["numerator"], metric["denominator"]) == (1, 1)
    assert (campaign / "records" / "recorded-run.json").read_bytes() == first


def test_grade_conflicting_metadata_preserves_existing_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench, result_path, _ = _evidence_fixture(tmp_path)
    campaign = tmp_path / "private-campaign"
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", workbench / "python-slugify")
    monkeypatch.setattr(driver, "PRIVATE_CAMPAIGN", campaign)
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    monkeypatch.setattr(
        driver,
        "_oracle_assessment",
        lambda repository, environment: driver.OracleAssessment(True, False),
    )
    driver.grade(result_path, metadata=driver.CampaignMetadata(model="first"))
    before = {
        path: path.read_bytes()
        for path in (
            campaign / "records" / "recorded-run.json",
            campaign / "campaign-v1.json",
            campaign / "index.html",
        )
    }

    with pytest.raises(driver.DemoError, match="already exists"):
        driver.grade(result_path, metadata=driver.CampaignMetadata(model="changed"))

    assert {path: path.read_bytes() for path in before} == before


def test_oracle_error_is_recorded_and_main_returns_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    driver = load_driver()
    workbench, result_path, _ = _evidence_fixture(tmp_path)
    campaign = tmp_path / "private-campaign"
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", workbench / "python-slugify")
    monkeypatch.setattr(driver, "PRIVATE_CAMPAIGN", campaign)
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    monkeypatch.setattr(
        driver,
        "_oracle_assessment",
        lambda repository, environment: driver.OracleAssessment(None, True),
    )

    assert driver.main(["grade", "--result", str(result_path)]) == 1

    output = capsys.readouterr().out
    assert output.index("classification: oracle_error") < output.index(
        "CAMPAIGN_RECORD:"
    )
    for label in ("CAMPAIGN_RECORD", "CAMPAIGN_REPORT", "CAMPAIGN_DATA"):
        assert f"{label}:" in output
    stored = json.loads(
        (campaign / "records" / "recorded-run.json").read_text()
    )
    assert stored["oracle"]["classification"] == "oracle_error"
    assert stored["oracle"]["truth"] is None


def test_campaign_report_rebuilds_outputs_without_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench, result_path, _ = _evidence_fixture(tmp_path)
    campaign = tmp_path / "private-campaign"
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", workbench / "python-slugify")
    monkeypatch.setattr(driver, "PRIVATE_CAMPAIGN", campaign)
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    monkeypatch.setattr(
        driver,
        "_oracle_assessment",
        lambda repository, environment: driver.OracleAssessment(True, False),
    )
    driver.grade(result_path, metadata=driver.CampaignMetadata())
    (campaign / "campaign-v1.json").unlink()
    (campaign / "index.html").unlink()

    def oracle_must_not_run(*args: object) -> object:
        pytest.fail("campaign-report must not run the oracle")

    monkeypatch.setattr(driver, "_oracle_assessment", oracle_must_not_run)
    assert driver.main(["campaign-report"]) == 0
    assert (campaign / "campaign-v1.json").is_file()
    assert (campaign / "index.html").is_file()


def test_verify_grades_controls_without_recording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench, result_path, _ = _evidence_fixture(tmp_path)
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "CONTROL_EVIDENCE", tmp_path / "control-evidence")
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    monkeypatch.setattr(driver, "control", lambda scenario: None)
    monkeypatch.setattr(driver, "reset", lambda: None)
    expected = [
        (0, "PASS", "good_pass"),
        (1, "FAIL", "good_catch"),
        (2, "NEEDS_HUMAN", "escalated"),
    ]
    calls = iter(expected)
    current: list[tuple[str, str]] = []

    def run(*args: object, **kwargs: object) -> SimpleNamespace:
        exit_code, verdict, box = next(calls)
        current.append((verdict, box))
        return SimpleNamespace(
            returncode=exit_code,
            stdout=f"RESULT: {result_path}\n",
            stderr="",
        )

    _, _, base_summary = driver.load_result(result_path)
    monkeypatch.setattr(driver, "_run", run)
    monkeypatch.setattr(
        driver,
        "inspect_result",
        lambda path: replace(base_summary, verdict=current[-1][0]),
    )
    grade_calls: list[tuple[bool, str]] = []

    def grade(path: Path, *, metadata: object, record: bool) -> str:
        grade_calls.append((record, metadata.run_kind))
        return current[-1][1]

    monkeypatch.setattr(driver, "grade", grade)

    driver.verify()

    assert grade_calls == [(False, "control")] * 3


def test_demo_policy_is_valid_and_resolves_on_both_platforms() -> None:
    config = load_config(POLICY)

    assert config.scope.forbidden_paths == ("/test.py", ".github/**")
    assert [check.id for check in config.checks] == [
        "tests-and-coverage",
        "task-consistency",
        "types",
    ]
    for platform in (PlatformName.WINDOWS, PlatformName.MACOS):
        for control in (*config.prepare, *config.checks):
            assert control.resolve(platform).argv


def test_committed_demo_assets_are_self_contained() -> None:
    expected = {
        DEMO / ".gitignore",
        DEMO / "README.md",
        DEMO / "assets" / ".release-gate.yaml",
        DEMO / "assets" / "TASK.md",
        DEMO / "controls" / "pass.patch",
        DEMO / "controls" / "fail.patch",
        DEMO / "controls" / "needs-human.patch",
        DEMO / "oracle" / "test_x1_oracle.py",
    }

    assert not [path for path in expected if not path.is_file()]
    readme = (DEMO / "README.md").read_text(encoding="utf-8")
    assert "../../../demo/tasks/X1_v2.md" in readme
    assert "../../../demo/oracle/test_x1_oracle.py" in readme
    assert "../../../demo/runs/RUNLOG.md" in readme
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
    (repository / ".gitignore").write_text(
        "/.release-gate/runs/\n", encoding="utf-8"
    )
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
