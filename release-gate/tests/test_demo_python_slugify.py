from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from release_gate.assurance.policy import load_policy
from release_gate.config import load_config
from release_gate.models import PlatformName

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "python-slugify"
DRIVER = DEMO / "demo.py"
POLICY = DEMO / "assets" / ".release-gate.yaml"
ASSURANCE_POLICY = DEMO / "assets" / ".release-gate-assurance.yaml"


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
    for command in ("inspect", "inspect-assurance", "grade"):
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
                    }
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


def assurance_result(gate_result_path: Path) -> dict[str, object]:
    return {
        "version": 1,
        "run_id": "assured-pass",
        "engine_version": "0.7.0",
        "gate_result_path": str(gate_result_path),
        "gate_result_sha256": "a" * 64,
        "gate_manifest_sha256": "b" * 64,
        "base_commit": "c" * 40,
        "candidate_tree": "d" * 40,
        "patch_sha256": "e" * 64,
        "policy_sha256": "f" * 64,
        "mode": "advisory",
        "gate_verdict": "PASS",
        "disposition": "NEEDS_HUMAN",
        "exit_code": 0,
        "assessment_status": "COMPLETE",
        "evidence_sufficient": False,
        "reason_codes": ["ASSURANCE_REQUIREMENTS_UNMET"],
        "artifacts": [],
        "coverage": {"mapping_uncertainty_rate": 0.25},
        "unmet_requirements": [
            {
                "dimension_id": "behavior_region",
                "value": "boundary",
                "independent_support": 0,
                "minimum_independent_support": 1,
            }
        ],
        "duration_ms": 12,
    }


def test_assurance_summary_reads_demo_fields(tmp_path: Path) -> None:
    driver = load_driver()
    gate_result = (tmp_path / "gate" / "result.json").resolve()
    result = tmp_path / "result.json"
    result.write_text(json.dumps(assurance_result(gate_result)), encoding="utf-8")

    summary = driver.read_assurance_summary(result)

    assert summary.run_id == "assured-pass"
    assert summary.gate_result_path == str(gate_result)
    assert summary.mode == "advisory"
    assert summary.gate_verdict == "PASS"
    assert summary.disposition == "NEEDS_HUMAN"
    assert summary.assessment_status == "COMPLETE"
    assert summary.evidence_sufficient is False
    assert summary.reason_codes == ("ASSURANCE_REQUIREMENTS_UNMET",)
    assert summary.coverage == {"mapping_uncertainty_rate": 0.25}
    assert summary.unmet_requirements[0]["value"] == "boundary"


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ({"version": 2}, "version"),
        ({"version": True}, "version"),
        ({"version": 1.0}, "version"),
        ({"mode": "optional"}, "mode"),
        ({"gate_verdict": "UNKNOWN"}, "gate_verdict"),
        ({"disposition": "UNKNOWN"}, "disposition"),
        ({"assessment_status": "PENDING"}, "assessment_status"),
        ({"gate_result_path": "relative/result.json"}, "absolute"),
        ({"gate_result_path": None}, "gate_result_path"),
        ({"evidence_sufficient": 1}, "boolean"),
        ({"reason_codes": [1]}, "reason_codes"),
        ({"coverage": []}, "coverage"),
        ({"unmet_requirements": ["boundary"]}, "unmet_requirements"),
    ],
)
def test_assurance_summary_rejects_invalid_results(
    tmp_path: Path, replacement: dict[str, object], message: str
) -> None:
    driver = load_driver()
    value = assurance_result((tmp_path / "gate-result.json").resolve())
    value.update(replacement)
    result = tmp_path / "result.json"
    result.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(driver.DemoError, match=message):
        driver.read_assurance_summary(result)


def test_assurance_summary_rejects_malformed_json_and_nonobject_root(
    tmp_path: Path,
) -> None:
    driver = load_driver()
    result = tmp_path / "result.json"
    result.write_text("{", encoding="utf-8")
    with pytest.raises(driver.DemoError, match="unable to read assurance result JSON"):
        driver.read_assurance_summary(result)

    result.write_text("[]", encoding="utf-8")
    with pytest.raises(driver.DemoError, match="JSON object"):
        driver.read_assurance_summary(result)


def test_inspect_assurance_result_prints_decision_and_link_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    driver = load_driver()
    gate_result = (tmp_path / "gate" / "result.json").resolve()
    package = tmp_path / "assurance"
    package.mkdir()
    result = package / "result.json"
    result.write_text(json.dumps(assurance_result(gate_result)), encoding="utf-8")
    (package / "manifest.json").write_text("{}", encoding="utf-8")

    summary = driver.inspect_assurance_result(result)

    assert summary.gate_result_path == str(gate_result)
    output = capsys.readouterr().out
    for line in (
        "run: assured-pass",
        f"linked gate result: {gate_result}",
        "mode: advisory",
        "gate verdict: PASS",
        "disposition: NEEDS_HUMAN",
        "assessment status: COMPLETE",
        "evidence sufficient: false",
        "reason codes: ASSURANCE_REQUIREMENTS_UNMET",
        "mapping uncertainty: 0.25",
        "unmet requirements:",
        f"manifest: {package / 'manifest.json'}",
    ):
        assert line in output


@pytest.mark.parametrize("incomplete", [False, True])
def test_inspect_assurance_result_requires_complete_package(
    tmp_path: Path, incomplete: bool
) -> None:
    driver = load_driver()
    package = tmp_path / "assurance"
    package.mkdir()
    result = package / "result.json"
    result.write_text(
        json.dumps(assurance_result((tmp_path / "gate-result.json").resolve())),
        encoding="utf-8",
    )
    if incomplete:
        (package / "manifest.json").write_text("{}", encoding="utf-8")
        (package / ".incomplete").touch()

    with pytest.raises(driver.DemoError, match="incomplete or missing manifest.json"):
        driver.inspect_assurance_result(result)


def test_main_dispatches_inspect_assurance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    driver = load_driver()
    package = tmp_path / "assurance"
    package.mkdir()
    result = package / "result.json"
    result.write_text(
        json.dumps(assurance_result((tmp_path / "gate-result.json").resolve())),
        encoding="utf-8",
    )
    (package / "manifest.json").write_text("{}", encoding="utf-8")

    assert driver.main(["inspect-assurance", "--result", str(result)]) == 0
    assert "linked gate result:" in capsys.readouterr().out


@pytest.mark.parametrize("inspector", ["inspect_result", "inspect_assurance_result"])
def test_inspectors_report_symlink_loops_as_demo_errors(
    tmp_path: Path, inspector: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    result = tmp_path / "result.json"

    def raise_symlink_loop(path: Path, *, strict: bool = False) -> Path:
        raise RuntimeError("Symlink loop from test")

    monkeypatch.setattr(driver.Path, "resolve", raise_symlink_loop)

    with pytest.raises(driver.DemoError, match="result does not exist"):
        getattr(driver, inspector)(result)


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


def test_verify_runs_assurance_for_all_controls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    driver = load_driver()
    repository = tmp_path / "repository"
    evidence = tmp_path / "evidence"
    repository.mkdir()
    calls: list[tuple[str, ...]] = []
    graded: list[Path] = []
    controlled: list[str] = []
    scenario_results = {
        "pass": (0, "PASS", "PASS", "COMPLETE", True, (), 0.25),
        "fail": (1, "FAIL", "FAIL", "NOT_EVALUATED", False, (), None),
        "needs-human": (
            2,
            "NEEDS_HUMAN",
            "NEEDS_HUMAN",
            "NOT_EVALUATED",
            False,
            (),
            None,
        ),
    }

    def fake_run(
        argv: tuple[str | Path, ...],
        *,
        cwd: Path | None = None,
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check, capture
        scenario = controlled[-1]
        code, verdict, disposition, status, sufficient, unmet, uncertainty = (
            scenario_results[scenario]
        )
        command = tuple(str(item) for item in argv)
        calls.append(command)
        run_id = command[command.index("--run-id") + 1]
        gate_package = evidence / scenario / "gate"
        assurance_package = evidence / scenario / "assurance"
        gate_package.mkdir(parents=True)
        assurance_package.mkdir(parents=True)
        gate_result = (gate_package / "result.json").resolve()
        gate_result.write_text(
            json.dumps(
                {
                    "version": 1,
                    "run_id": f"gate-{scenario}",
                    "base_commit": "a" * 40,
                    "candidate_tree": "b" * 40,
                    "patch_sha256": "c" * 64,
                    "config_sha256": "d" * 64,
                    "verdict": verdict,
                    "reason_codes": [],
                    "scope": {
                        "changed_paths": ["setup.py"],
                        "outside_allowed_paths": [],
                        "forbidden_paths": [],
                        "review_required_paths": [],
                    },
                    "checks": [],
                    "manifest_path": "manifest.json",
                }
            ),
            encoding="utf-8",
        )
        (gate_package / "manifest.json").write_text("{}", encoding="utf-8")
        assurance = assurance_result(gate_result)
        assurance.update(
            {
                "run_id": run_id,
                "gate_verdict": verdict,
                "disposition": disposition,
                "assessment_status": status,
                "evidence_sufficient": sufficient,
                "reason_codes": [],
                "coverage": (
                    {"mapping_uncertainty_rate": uncertainty}
                    if uncertainty is not None
                    else None
                ),
                "unmet_requirements": list(unmet),
            }
        )
        assurance_result_path = (assurance_package / "result.json").resolve()
        assurance_result_path.write_text(json.dumps(assurance), encoding="utf-8")
        (assurance_package / "manifest.json").write_text("{}", encoding="utf-8")
        stdout = "\n".join(
            (
                f"GATE_VERDICT: {verdict}",
                f"ASSURANCE_DISPOSITION: {disposition}",
                "ASSURANCE_MODE: advisory",
                f"ASSESSMENT_STATUS: {status}",
                f"RESULT: {assurance_result_path}",
                "",
            )
        )
        return subprocess.CompletedProcess(command, code, stdout, "")

    classifications = iter(("good_pass", "good_catch", "escalated"))

    def fake_grade(path: Path) -> str:
        graded.append(path)
        return next(classifications)

    monkeypatch.setattr(driver, "WORKBENCH", tmp_path / "missing-workbench")
    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(driver, "CONTROL_EVIDENCE", evidence)
    monkeypatch.setattr(driver, "setup", lambda: None)
    monkeypatch.setattr(driver, "control", controlled.append)
    monkeypatch.setattr(driver, "reset", lambda: None)
    monkeypatch.setattr(driver, "_gate_argv", lambda *args: ("release-gate", *args))
    monkeypatch.setattr(driver, "_run", fake_run)
    monkeypatch.setattr(driver, "grade", fake_grade)

    driver.verify()

    assert controlled == ["pass", "fail", "needs-human"]
    assert len(calls) == 3
    run_ids: set[str] = set()
    for command in calls:
        assert command[:2] == ("release-gate", "assure")
        assert command[2:8] == (
            "--repo",
            str(repository),
            "--base",
            driver.BASE_REF,
            "--output",
            str(evidence),
        )
        assert command[8] == "--run-id"
        run_ids.add(command[9])
    assert len(run_ids) == 3
    assert graded == [
        (evidence / scenario / "gate" / "result.json").resolve()
        for scenario in ("pass", "fail", "needs-human")
    ]
    output = capsys.readouterr().out
    for line in (
        "GATE_VERDICT: PASS",
        "ASSURANCE_DISPOSITION: PASS",
        "ASSURANCE_MODE: advisory",
        "ASSESSMENT_STATUS: COMPLETE",
        "GATE_VERDICT: FAIL",
        "ASSURANCE_DISPOSITION: FAIL",
        "GATE_VERDICT: NEEDS_HUMAN",
        "ASSURANCE_DISPOSITION: NEEDS_HUMAN",
        "ASSESSMENT_STATUS: NOT_EVALUATED",
        "RESULT: ",
        "verify: gate verdicts and assurance dispositions matched expectations",
    ):
        assert line in output


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ({"coverage": {"mapping_uncertainty_rate": True}}, "mapping uncertainty"),
        ({"coverage": {"mapping_uncertainty_rate": "0.25"}}, "mapping uncertainty"),
        ({"coverage": {"mapping_uncertainty_rate": 0.96}}, "mapping uncertainty"),
        ({"coverage": {"mapping_uncertainty_rate": math.nan}}, "mapping uncertainty"),
        ({"coverage": {"mapping_uncertainty_rate": math.inf}}, "mapping uncertainty"),
        ({"coverage": {"mapping_uncertainty_rate": -0.01}}, "mapping uncertainty"),
        ({"evidence_sufficient": False}, "insufficient"),
        ({"unmet_requirements": ({"dimension_id": "boundary"},)}, "unmet"),
    ],
)
def test_validate_pass_assurance_rejects_invalid_evidence(
    replacement: dict[str, object], message: str
) -> None:
    driver = load_driver()
    values = {
        "run_id": "verify-pass",
        "gate_result_path": "/absolute/gate/result.json",
        "mode": "advisory",
        "gate_verdict": "PASS",
        "disposition": "PASS",
        "assessment_status": "COMPLETE",
        "evidence_sufficient": True,
        "reason_codes": (),
        "coverage": {"mapping_uncertainty_rate": 0.25},
        "unmet_requirements": (),
    }
    values.update(replacement)
    summary = driver.AssuranceSummary(**values)

    with pytest.raises(driver.DemoError, match=message):
        driver._validate_assurance_control(
            "pass", summary, "PASS", "PASS", "COMPLETE"
        )


@pytest.mark.parametrize("verdict", ["FAIL", "NEEDS_HUMAN"])
def test_validate_nonpass_assurance_rejects_claimed_coverage(verdict: str) -> None:
    driver = load_driver()
    summary = driver.AssuranceSummary(
        run_id=f"verify-{verdict.lower()}",
        gate_result_path="/absolute/gate/result.json",
        mode="advisory",
        gate_verdict=verdict,
        disposition=verdict,
        assessment_status="NOT_EVALUATED",
        evidence_sufficient=False,
        reason_codes=(),
        coverage={"mapping_uncertainty_rate": 0.25},
        unmet_requirements=(),
    )

    with pytest.raises(driver.DemoError, match="claimed coverage"):
        driver._validate_assurance_control(
            verdict.lower(), summary, verdict, verdict, "NOT_EVALUATED"
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


def test_demo_assurance_policy_is_reviewed_and_valid() -> None:
    policy = load_policy(ASSURANCE_POLICY.read_bytes())

    assert policy.version == 1
    assert policy.mode == "advisory"
    assert policy.concept_schema.schema_id == "python-slugify-behavior"
    assert policy.concept_schema.schema_version == "1.0.0"

    [dimension] = policy.concept_schema.dimensions
    assert dimension.dimension_id == "behavior_region"
    assert dimension.values == [
        "transliteration",
        "unicode",
        "boundary",
        "customization",
        "cli_contract",
    ]
    assert [
        (region.dimension_id, region.value, region.minimum_independent_support)
        for region in policy.required_regions
    ] == [("behavior_region", value, 1) for value in dimension.values]
    assert policy.maximum_mapping_uncertainty_rate == 0.95
    assert policy.limits.max_artifacts <= 256
    assert policy.limits.max_report_bytes <= 4_194_304
    assert policy.limits.max_total_report_bytes <= 16_777_216
    assert policy.limits.max_elapsed_seconds <= 30.0

    source = {
        "test.py": "5262916dbabb42b0d63b7c3eaa200aa435e8bb6d888287a048ed649eb29d91b1"
    }
    assert len(policy.mappings) == 5
    assert all(mapping.sources == source for mapping in policy.mappings)
    assert all(
        mapping.independence_group == "upstream-test.py"
        for mapping in policy.mappings
    )
    assert [
        (
            mapping.selector.check_id,
            mapping.selector.report_id,
            mapping.selector.suite,
            mapping.selector.classname,
            mapping.selector.name,
            mapping.concepts,
        )
        for mapping in policy.mappings
    ] == [
        (
            "tests-and-coverage",
            "junit",
            "pytest",
            "test.TestSlugify",
            "test_cyrillic_text",
            {"behavior_region": "transliteration"},
        ),
        (
            "tests-and-coverage",
            "junit",
            "pytest",
            "test.TestSlugifyUnicode",
            "test_emojis",
            {"behavior_region": "unicode"},
        ),
        (
            "tests-and-coverage",
            "junit",
            "pytest",
            "test.TestSlugify",
            "test_max_length_cutoff_not_required",
            {"behavior_region": "boundary"},
        ),
        (
            "tests-and-coverage",
            "junit",
            "pytest",
            "test.TestSlugify",
            "test_replacements_german_umlaut_custom",
            {"behavior_region": "customization"},
        ),
        (
            "tests-and-coverage",
            "junit",
            "pytest",
            "test.TestCommandParams",
            "test_two_text_sources_fails",
            {"behavior_region": "cli_contract"},
        ),
    ]


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
        ASSURANCE_POLICY,
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
        "failure mode or assurance claim",
        "N-A",
        "UNAVAILABLE",
        "SUBSTITUTED",
    ):
        assert phrase in readme
    assert "workbench/" in (DEMO / ".gitignore").read_text(encoding="utf-8")


def test_demo_walkthrough_documents_conceptual_diversity_assurance() -> None:
    readme = (DEMO / "README.md").read_text(encoding="utf-8")
    normalized = " ".join(readme.split())
    policy = load_policy(ASSURANCE_POLICY.read_bytes())

    for phrase in (
        ".release-gate-assurance.yaml",
        "GATE_VERDICT",
        "ASSURANCE_DISPOSITION",
        "ASSESSMENT_STATUS",
        "mapping uncertainty",
        "independence group",
        "advisory",
        "enforce",
        "unmapped majority",
        "candidate-side passing",
        "verify: gate verdicts and assurance dispositions matched expectations",
        "insufficient or unavailable",
        "disposition remains `PASS`",
        "any `NEEDS_HUMAN` disposition exits 2",
        "deterministic gate verdict",
        "not eligible",
    ):
        assert phrase.casefold() in normalized.casefold()

    [dimension] = policy.concept_schema.dimensions
    for region in dimension.values:
        assert f"`{region}`" in readme
    for mapping in policy.mappings:
        for path, digest in mapping.sources.items():
            assert f"`{path}: {digest}`" in readme
        assert f"`{mapping.independence_group}` independence group" in readme
    assert f"`{policy.maximum_mapping_uncertainty_rate}`" in readme

    windows_assure = (
        "release-gate assure --repo .\\workbench\\python-slugify "
        "--base release-gate-demo-base"
    )
    macos_assure = (
        "release-gate assure --repo ./workbench/python-slugify "
        "--base release-gate-demo-base"
    )
    assert windows_assure in normalized
    assert macos_assure in normalized
    assert (
        'demo.py inspect-assurance --result "C:\\absolute\\path\\to\\assurance\\result.json"'
        in normalized
    )
    assert (
        'demo.py inspect-assurance --result "/absolute/path/to/assurance/result.json"'
        in normalized
    )
    assert (
        "Run `inspect-assurance` on it and use its `linked gate result` path for "
        "`inspect`"
    ) in normalized
    assert "assure exit code" in normalized.casefold()
    assert "reviewed base-policy change" in normalized.casefold()


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
    (repository / ".release-gate-assurance.yaml").write_bytes(
        ASSURANCE_POLICY.read_bytes()
    )
    (repository / ".gitignore").write_text("/.release-gate/runs/\n", encoding="utf-8")
    git("add", ".release-gate.yaml", ".release-gate-assurance.yaml", ".gitignore")
    git("commit", "-qm", "policy")
    git("tag", driver.BASE_REF)

    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(driver, "UPSTREAM_SHA", upstream)

    driver._verify_repository()
    (repository / ".release-gate.yaml").write_bytes(POLICY.read_bytes() + b"\n")
    git("add", ".release-gate.yaml")
    git("commit", "--amend", "-qm", "tampered primary policy")
    git("tag", "-f", driver.BASE_REF)
    with pytest.raises(driver.DemoError, match="trusted base policy"):
        driver._verify_repository()

    (repository / ".release-gate.yaml").write_bytes(POLICY.read_bytes())
    (repository / ".release-gate-assurance.yaml").write_text(
        "version: 1\nmode: enforce\n", encoding="utf-8"
    )
    git("add", ".release-gate.yaml", ".release-gate-assurance.yaml")
    git("commit", "--amend", "-qm", "tampered assurance policy")
    git("tag", "-f", driver.BASE_REF)
    with pytest.raises(driver.DemoError, match="assurance policy"):
        driver._verify_repository()

    git("remote", "set-url", "origin", driver.UPSTREAM_URL)
    git("remote", "set-url", "origin", "https://example.invalid/wrong.git")
    with pytest.raises(driver.DemoError, match="unexpected workbench origin"):
        driver._verify_repository()


def test_setup_installs_both_trusted_policies_before_tagging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    workbench = tmp_path / "workbench"
    repository = workbench / "python-slugify"
    git_calls: list[tuple[str, ...]] = []
    run_calls: list[tuple[str, ...]] = []

    def fake_run(
        argv: tuple[object, ...],
        *,
        cwd: Path | None = None,
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        command = tuple(str(item) for item in argv)
        run_calls.append(command)
        if command[:3] == ("git", "clone", "--quiet"):
            repository.mkdir(parents=True)
            (repository / ".git").mkdir()
        elif "init" in command:
            (repository / ".release-gate.yaml").write_bytes(POLICY.read_bytes())
            (repository / ".gitignore").write_text(
                "/.release-gate/runs/\n", encoding="utf-8"
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    def fake_git(*arguments: str, **kwargs: object) -> str:
        git_calls.append(arguments)
        return ""

    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(driver, "TASK_VENV", workbench / "task-venv")
    monkeypatch.setattr(driver, "require_supported_platform", lambda: None)
    monkeypatch.setattr(driver, "_which", lambda name: name)
    monkeypatch.setattr(driver, "_require_gate_version", lambda: None)
    monkeypatch.setattr(driver, "_run", fake_run)
    monkeypatch.setattr(driver, "_git", fake_git)
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    monkeypatch.setattr(driver, "_create_task_environment", lambda path: None)
    monkeypatch.setattr(driver, "_verify_upstream_tests", lambda: None)

    driver.setup()

    assert (repository / ".release-gate-assurance.yaml").read_bytes() == (
        ASSURANCE_POLICY.read_bytes()
    )
    staged = (
        "add",
        ".release-gate.yaml",
        ".release-gate-assurance.yaml",
        ".gitignore",
    )
    assert staged in git_calls
    commit = ("commit", "--quiet", "-m", "chore: add release gate demo policy")
    tag = ("tag", driver.BASE_REF)
    assert git_calls.index(staged) < git_calls.index(commit) < git_calls.index(tag)
    assert [command[-5:] for command in run_calls if "init" in command] == [
        ("init", "--repo", str(repository), "--from-config", str(POLICY))
    ]


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
