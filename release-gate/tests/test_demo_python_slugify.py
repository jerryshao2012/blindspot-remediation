from __future__ import annotations

import hashlib
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
    for command in ("inspect", "inspect-assurance", "layers", "grade"):
        parsed = parser.parse_args([command, "--result", "result.json"])
        assert parsed.command == command
    assert parser.parse_args(["control", "pass"]).scenario == "pass"
    assert parser.parse_args(["control", "pass"]).enforce is False
    enforced = parser.parse_args(["control", "skip-evasion", "--enforce"])
    assert (enforced.scenario, enforced.enforce) == ("skip-evasion", True)
    assert parser.parse_args(["reset", "--enforce"]).enforce is True
    assert parser.parse_args(["verify"]).layers is False
    assert parser.parse_args(["verify", "--layers"]).layers is True
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

    with pytest.raises(driver.DemoError, match=r"incomplete or missing manifest.json"):
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


@pytest.mark.parametrize("layers", [False, True])
def test_verify_runs_assurance_for_selected_scenarios(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    layers: bool,
) -> None:
    driver = load_driver()
    repository = tmp_path / "repository"
    evidence = tmp_path / "evidence"
    repository.mkdir()
    calls: list[tuple[str, ...]] = []
    graded: list[tuple[Path, str]] = []
    controlled: list[tuple[str, str]] = []
    current: list[str] = []
    expected_names = tuple(driver.SCENARIOS) if layers else driver.DEFAULT_SCENARIOS

    def fake_control(scenario: str, base: str) -> None:
        controlled.append((scenario, base))
        current.append(expected_names[len(controlled) - 1])

    def fake_run(
        argv: tuple[str | Path, ...],
        *,
        cwd: Path | None = None,
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check, capture
        scenario = driver.SCENARIOS[current[-1]]
        command = tuple(str(item) for item in argv)
        calls.append(command)
        run_id = command[command.index("--run-id") + 1]
        gate_package = evidence / scenario.name / "gate"
        assurance_package = evidence / scenario.name / "assurance"
        gate_package.mkdir(parents=True)
        assurance_package.mkdir(parents=True)
        gate_result = (gate_package / "result.json").resolve()
        gate_result.write_text("{}", encoding="utf-8")
        assurance = assurance_result(gate_result)
        complete = scenario.assessment_status == "COMPLETE"
        assurance.update(
            {
                "run_id": run_id,
                "mode": "enforce" if scenario.enforce else "advisory",
                "gate_verdict": scenario.gate_verdict,
                "disposition": scenario.disposition,
                "assessment_status": scenario.assessment_status,
                "evidence_sufficient": scenario.evidence_sufficient,
                "reason_codes": [],
                "coverage": (
                    {"mapping_uncertainty_rate": 0.25 if complete else 0}
                    if complete
                    else None
                ),
                "unmet_requirements": [
                    {"dimension_id": dimension, "value": value}
                    for dimension, value in scenario.unmet
                ],
            }
        )
        assurance_result_path = (assurance_package / "result.json").resolve()
        assurance_result_path.write_text(json.dumps(assurance), encoding="utf-8")
        (assurance_package / "manifest.json").write_text("{}", encoding="utf-8")
        stdout = "\n".join(
            (
                f"GATE_VERDICT: {scenario.gate_verdict}",
                f"ASSURANCE_DISPOSITION: {scenario.disposition}",
                f"ASSESSMENT_STATUS: {scenario.assessment_status}",
                f"RESULT: {assurance_result_path}",
                "",
            )
        )
        return subprocess.CompletedProcess(command, scenario.exit_code, stdout, "")

    def fake_layer_report(path: Path) -> dict[str, object]:
        scenario = driver.SCENARIOS[current[-1]]
        mapped = sorted(driver.MAPPED_FAILURE_MODES)
        if scenario.assessment_status == "COMPLETE":
            unverified = [
                value
                for dimension, value in scenario.unmet
                if dimension == "failure_mode"
            ]
            counted = 8
        else:
            unverified = mapped
            counted = 0
        return {
            "mapped_failure_modes": mapped,
            "unverified_failure_modes": unverified,
            "counted_evidence": counted,
        }

    def fake_grade_run(path: Path, disposition: str | None = None) -> tuple[str, str]:
        assert disposition is not None
        graded.append((path, disposition))
        scenario = driver.SCENARIOS[current[-1]]
        return scenario.gate_box, scenario.disposition_box

    monkeypatch.setattr(driver, "WORKBENCH", tmp_path / "missing-workbench")
    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(driver, "CONTROL_EVIDENCE", evidence)
    monkeypatch.setattr(driver, "setup", lambda: None)
    monkeypatch.setattr(driver, "control", fake_control)
    monkeypatch.setattr(driver, "reset", lambda base=driver.BASE_REF: None)
    monkeypatch.setattr(driver, "_gate_argv", lambda *args: ("release-gate", *args))
    monkeypatch.setattr(driver, "_run", fake_run)
    monkeypatch.setattr(driver, "layer_report", fake_layer_report)
    monkeypatch.setattr(driver, "_grade_run", fake_grade_run)

    driver.verify(layers=layers)

    assert [name for name in current] == list(expected_names)
    assert controlled == [
        (
            driver.SCENARIOS[name].control,
            driver.ENFORCE_REF if driver.SCENARIOS[name].enforce else driver.BASE_REF,
        )
        for name in expected_names
    ]
    assert len(calls) == len(expected_names)
    for command, (_, base) in zip(calls, controlled, strict=True):
        assert command[:2] == ("release-gate", "assure")
        assert command[2:8] == (
            "--repo",
            str(repository),
            "--base",
            base,
            "--output",
            str(evidence),
        )
        assert command[8] == "--run-id"
    assert len({command[9] for command in calls}) == len(expected_names)
    assert [path for path, _ in graded] == [
        (evidence / name / "gate" / "result.json").resolve() for name in expected_names
    ]
    output = capsys.readouterr().out
    assert "verify: gate verdicts and assurance dispositions matched expectations" in (
        output
    )
    assert (
        "verify: unverified layers were surfaced without false coverage" in output
    ) is layers
    assert "=== scenario summary" in output


def test_verify_rejects_a_layer_report_that_counts_unevaluated_evidence() -> None:
    driver = load_driver()
    scenario = driver.SCENARIOS["omit-tox"]
    report = {
        "mapped_failure_modes": sorted(driver.MAPPED_FAILURE_MODES),
        "unverified_failure_modes": sorted(driver.MAPPED_FAILURE_MODES),
        "counted_evidence": 1,
    }

    with pytest.raises(driver.DemoError, match="unevaluated assurance counted"):
        driver._validate_layer_report("omit-tox", report, scenario)

    report["counted_evidence"] = 0
    report["unverified_failure_modes"] = []
    with pytest.raises(driver.DemoError, match="every mapped failure mode"):
        driver._validate_layer_report("omit-tox", report, scenario)


def test_verify_rejects_unexpected_unverified_failure_modes() -> None:
    driver = load_driver()
    scenario = driver.SCENARIOS["skip-evasion"]
    report = {
        "mapped_failure_modes": sorted(driver.MAPPED_FAILURE_MODES),
        "unverified_failure_modes": [],
        "counted_evidence": 9,
    }

    with pytest.raises(driver.DemoError, match="expected unverified failure modes"):
        driver._validate_layer_report("skip-evasion", report, scenario)

    report["unverified_failure_modes"] = ["import_declaration_mismatch"]
    driver._validate_layer_report("skip-evasion", report, scenario)


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
        driver._validate_assurance_control("pass", summary, "PASS", "PASS", "COMPLETE")


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


@pytest.mark.parametrize("verdict", ["FAIL", "NEEDS_HUMAN"])
@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ({"evidence_sufficient": True}, "claimed sufficient evidence"),
        (
            {"unmet_requirements": ({"dimension_id": "boundary"},)},
            "claimed unmet requirements",
        ),
    ],
)
def test_validate_nonpass_assurance_rejects_evidence_claims(
    verdict: str, replacement: dict[str, object], message: str
) -> None:
    driver = load_driver()
    values = {
        "run_id": f"verify-{verdict.lower()}",
        "gate_result_path": "/absolute/gate/result.json",
        "mode": "advisory",
        "gate_verdict": verdict,
        "disposition": verdict,
        "assessment_status": "NOT_EVALUATED",
        "evidence_sufficient": False,
        "reason_codes": (),
        "coverage": None,
        "unmet_requirements": (),
    }
    values.update(replacement)
    summary = driver.AssuranceSummary(**values)

    with pytest.raises(driver.DemoError, match=message):
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
    tests_and_coverage = config.checks[0]
    coverage_floor = next(
        assertion.value
        for assertion in tests_and_coverage.assertions
        if assertion.report == "coverage"
        and assertion.metric == "/percent_covered"
        and assertion.comparison == "candidate"
    )
    assert coverage_floor == 85
    for platform in (PlatformName.WINDOWS, PlatformName.MACOS):
        assert (
            f"--cov-fail-under={coverage_floor}"
            in tests_and_coverage.resolve(platform).argv
        )
    for platform in (PlatformName.WINDOWS, PlatformName.MACOS):
        for control in (*config.prepare, *config.checks):
            assert control.resolve(platform).argv


def test_demo_assurance_policy_is_reviewed_and_valid() -> None:
    policy = load_policy(ASSURANCE_POLICY.read_bytes())

    assert policy.version == 1
    assert policy.mode == "advisory"
    assert policy.concept_schema.schema_id == "python-slugify-behavior"
    assert policy.concept_schema.schema_version == "1.1.0"

    regions, failure_modes = policy.concept_schema.dimensions
    assert regions.dimension_id == "behavior_region"
    assert regions.values == [
        "transliteration",
        "unicode",
        "boundary",
        "customization",
        "cli_contract",
    ]
    assert failure_modes.dimension_id == "failure_mode"
    assert failure_modes.values == [
        "public_api_regression",
        "import_declaration_mismatch",
        "incomplete_migration",
        "type_regression",
    ]
    assert [
        (region.dimension_id, region.value, region.minimum_independent_support)
        for region in policy.required_regions
    ] == [("behavior_region", value, 1) for value in regions.values] + [
        ("failure_mode", value, 1) for value in failure_modes.values
    ]
    assert policy.maximum_mapping_uncertainty_rate == 0.95
    assert policy.limits.max_artifacts <= 256
    assert policy.limits.max_report_bytes <= 4_194_304
    assert policy.limits.max_total_report_bytes <= 16_777_216
    assert policy.limits.max_elapsed_seconds <= 30.0

    test_digest = "f10f27fa48230d93c34826c7e3c03336ea9fa5103c5a0706174c586470403eda"
    policy_digest = hashlib.sha256(POLICY.read_bytes()).hexdigest()
    rows = [
        (
            mapping.selector.check_id,
            mapping.selector.classname,
            mapping.selector.name,
            mapping.concepts,
            mapping.sources,
            mapping.independence_group,
        )
        for mapping in policy.mappings
    ]
    upstream = ({"test.py": test_digest}, "upstream-test.py")
    gate_policy = ({".release-gate.yaml": policy_digest}, "gate-policy")
    assert rows == [
        (
            "tests-and-coverage",
            "test.TestSlugify",
            "test_cyrillic_text",
            {
                "behavior_region": "transliteration",
                "failure_mode": "import_declaration_mismatch",
            },
            *upstream,
        ),
        (
            "tests-and-coverage",
            "test.TestSlugifyUnicode",
            "test_emojis",
            {"behavior_region": "unicode"},
            *upstream,
        ),
        (
            "tests-and-coverage",
            "test.TestSlugify",
            "test_max_length_cutoff_not_required",
            {"behavior_region": "boundary"},
            *upstream,
        ),
        (
            "tests-and-coverage",
            "test.TestSlugify",
            "test_replacements_german_umlaut_custom",
            {"behavior_region": "customization"},
            *upstream,
        ),
        (
            "tests-and-coverage",
            "test.TestCommandParams",
            "test_two_text_sources_fails",
            {"behavior_region": "cli_contract"},
            *upstream,
        ),
        (
            "tests-and-coverage",
            "test.TestUtils",
            "test_smart_truncate_no_max_length",
            {"failure_mode": "public_api_regression"},
            *upstream,
        ),
        (
            "tests-and-coverage",
            "test.TestCommandParams",
            "test_defaults",
            {"failure_mode": "public_api_regression"},
            *upstream,
        ),
        (
            "task-consistency",
            None,
            None,
            {"failure_mode": "incomplete_migration"},
            *gate_policy,
        ),
        ("types", None, None, {"failure_mode": "type_regression"}, *gate_policy),
    ]
    case_mappings = [m for m in policy.mappings if m.selector.name is not None]
    assert all(
        (m.selector.report_id, m.selector.suite) == ("junit", "pytest")
        for m in case_mappings
    )


def test_gate_policy_source_digest_is_the_committed_asset_blob() -> None:
    """The assurance policy trusts the LF bytes Git stores for the gate policy."""

    raw = POLICY.read_bytes()
    assert b"\r\n" not in raw
    digests = {
        digest
        for mapping in load_policy(ASSURANCE_POLICY.read_bytes()).mappings
        for path, digest in mapping.sources.items()
        if path == ".release-gate.yaml"
    }
    assert digests == {hashlib.sha256(raw).hexdigest()}


def test_gate_policy_comments_name_every_check_failure_mode() -> None:
    driver = load_driver()
    text = POLICY.read_text(encoding="utf-8")
    for layer in driver.LAYERS:
        if layer.evidence == "assurance":
            comment_index = text.index(f"- id: {layer.source}")
            comment = text[:comment_index].rstrip().splitlines()[-1]
            assert comment.lstrip().startswith("# Failure mode")
            for mode in layer.failure_modes:
                assert mode in comment
    scope = next(layer for layer in driver.LAYERS if layer.evidence == "scope")
    scope_comment = text[: text.index("\nscope:")].splitlines()[-1]
    for mode in scope.failure_modes:
        assert mode in scope_comment


def test_layer_catalog_matches_the_assurance_policy() -> None:
    driver = load_driver()
    policy = load_policy(ASSURANCE_POLICY.read_bytes())
    [failure_modes] = [
        dimension
        for dimension in policy.concept_schema.dimensions
        if dimension.dimension_id == "failure_mode"
    ]

    assert {layer.label for layer in driver.LAYERS} == set(driver.LAYER_LABELS)
    assert set(failure_modes.values) == driver.MAPPED_FAILURE_MODES
    uncounted = {
        mode
        for layer in driver.LAYERS
        if layer.evidence != "assurance"
        for mode in layer.failure_modes
    }
    # Substituted, unavailable, not-applicable and scope-only failure modes are
    # never assurance values, so the engine cannot report them as covered.
    assert not uncounted & set(failure_modes.values)
    catalogued = {mode for layer in driver.LAYERS for mode in layer.failure_modes}
    assert catalogued == set(driver.FAILURE_MODES)
    for layer in driver.LAYERS:
        if layer.label in ("SUBSTITUTED", "UNAVAILABLE", "N-A"):
            assert layer.evidence != "assurance"
        if layer.label == "SUBSTITUTED":
            assert layer.source


def test_enforce_policy_differs_from_the_asset_only_by_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    enforce = driver._enforce_policy_bytes()
    advisory = ASSURANCE_POLICY.read_bytes()

    assert load_policy(enforce).mode == "enforce"
    assert enforce.replace(b"mode: enforce\n", b"mode: advisory\n") == advisory

    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / ".release-gate-assurance.yaml").write_bytes(advisory + advisory)
    monkeypatch.setattr(driver, "ASSETS", assets)
    with pytest.raises(driver.DemoError, match="exactly once"):
        driver._enforce_policy_bytes()


def test_every_control_scenario_has_a_patch_and_scenarios_use_known_controls() -> None:
    driver = load_driver()

    for scenario in driver.CONTROL_SCENARIOS:
        assert (DEMO / "controls" / f"{scenario}.patch").is_file()
    assert set(driver.DEFAULT_SCENARIOS) <= set(driver.SCENARIOS)
    for scenario in driver.SCENARIOS.values():
        assert scenario.control in driver.CONTROL_SCENARIOS
        if scenario.assessment_status != "COMPLETE":
            assert not scenario.evidence_sufficient and not scenario.unmet
        if scenario.evidence_sufficient:
            assert not scenario.unmet
    enforce_skip = driver.SCENARIOS["skip-evasion-enforce"]
    assert (enforce_skip.gate_verdict, enforce_skip.disposition) == (
        "PASS",
        "NEEDS_HUMAN",
    )
    assert (enforce_skip.gate_box, enforce_skip.disposition_box) == (
        "FALSE_RELEASE",
        "escalated",
    )


def test_reviewed_source_validation_uses_trusted_git_blob_not_checkout_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    repository = tmp_path / "repository"
    repository.mkdir()

    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Demo Test"], cwd=repository, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "demo-test@example.invalid"],
        cwd=repository,
        check=True,
    )
    source = repository / "test.py"
    source.write_bytes(b"first line\nsecond line\n")
    secondary = repository / "support.txt"
    secondary.write_bytes(b"reviewed support\n")
    subprocess.run(["git", "add", "test.py", "support.txt"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "upstream"], cwd=repository, check=True)

    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / ".release-gate-assurance.yaml").write_bytes(ASSURANCE_POLICY.read_bytes())
    source.write_bytes(b"first line\r\nsecond line\r\n")
    expected_sources = {
        "test.py": hashlib.sha256(b"first line\nsecond line\n").hexdigest(),
        "support.txt": hashlib.sha256(b"reviewed support\n").hexdigest(),
    }

    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(driver, "ASSETS", assets)
    monkeypatch.setattr(
        driver,
        "_load_assurance_policy_sources",
        lambda path: [expected_sources, expected_sources.copy()],
    )

    driver._verify_reviewed_source_blobs()


def test_reviewed_source_validation_rejects_stale_policy_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    (repository / "test.py").write_bytes(b"trusted contents\n")
    # The reviewed gate policy is itself a source; keep it valid so only the
    # stale test.py digest is reported.
    (repository / ".release-gate.yaml").write_bytes(POLICY.read_bytes())
    subprocess.run(
        ["git", "add", "test.py", ".release-gate.yaml"], cwd=repository, check=True
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Demo Test",
            "-c",
            "user.email=demo-test@example.invalid",
            "commit",
            "-qm",
            "upstream",
        ],
        cwd=repository,
        check=True,
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / ".release-gate-assurance.yaml").write_bytes(ASSURANCE_POLICY.read_bytes())

    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(driver, "ASSETS", assets)
    monkeypatch.setattr(
        driver,
        "_load_assurance_policy_sources",
        lambda path: [
            mapping.sources for mapping in load_policy(path.read_bytes()).mappings
        ],
    )

    with pytest.raises(driver.DemoError, match=r"test.py.*trusted Git blob contents"):
        driver._verify_reviewed_source_blobs()


def test_reviewed_source_validation_rejects_stale_secondary_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    (repository / "test.py").write_bytes(b"primary\n")
    (repository / "support.txt").write_bytes(b"secondary\n")
    subprocess.run(["git", "add", "test.py", "support.txt"], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Demo Test",
            "-c",
            "user.email=demo-test@example.invalid",
            "commit",
            "-qm",
            "upstream",
        ],
        cwd=repository,
        check=True,
    )
    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(
        driver,
        "_load_assurance_policy_sources",
        lambda path: [
            {
                "test.py": hashlib.sha256(b"primary\n").hexdigest(),
                "support.txt": "0" * 64,
            }
        ],
    )

    with pytest.raises(
        driver.DemoError, match=r"support.txt.*trusted Git blob contents"
    ):
        driver._verify_reviewed_source_blobs()


def test_reviewed_source_validation_rejects_missing_secondary_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    (repository / "test.py").write_bytes(b"primary\n")
    subprocess.run(["git", "add", "test.py"], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Demo Test",
            "-c",
            "user.email=demo-test@example.invalid",
            "commit",
            "-qm",
            "upstream",
        ],
        cwd=repository,
        check=True,
    )
    monkeypatch.setattr(driver, "REPOSITORY", repository)
    monkeypatch.setattr(
        driver,
        "_load_assurance_policy_sources",
        lambda path: [{"support.txt": "0" * 64}],
    )

    with pytest.raises(
        driver.DemoError, match=r"reviewed source support.txt is missing"
    ):
        driver._verify_reviewed_source_blobs()


def test_reviewed_source_validation_rejects_conflicting_digests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = load_driver()
    monkeypatch.setattr(
        driver,
        "_load_assurance_policy_sources",
        lambda path: [{"test.py": "0" * 64}, {"test.py": "1" * 64}],
    )

    with pytest.raises(driver.DemoError, match=r"conflicting.*test.py"):
        driver._verify_reviewed_source_blobs()


def test_assurance_policy_sources_load_through_release_gate_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    monkeypatch.setattr(driver, "_release_gate_python", lambda: Path(sys.executable))
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "src"))

    sources = driver._load_assurance_policy_sources(ASSURANCE_POLICY)

    assert len(sources) == 9
    assert [set(mapping) for mapping in sources] == [{"test.py"}] * 7 + [
        {".release-gate.yaml"}
    ] * 2

    policy = driver._load_assurance_policy(ASSURANCE_POLICY)
    assert ["failure_mode", "type_regression"] in policy["required"]
    assert policy["mappings"][-1]["selector"] == {
        "check_id": "types",
        "report_id": None,
        "suite": None,
        "classname": None,
        "name": None,
    }

    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("mode: advisory\n", encoding="utf-8")
    with pytest.raises(driver.DemoError, match="invalid assurance policy"):
        driver._load_assurance_policy_sources(invalid)


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
        DEMO / "controls" / "omit-tox.patch",
        DEMO / "controls" / "undeclared-dep.patch",
        DEMO / "controls" / "skip-evasion.patch",
        DEMO / "controls" / "changelog-creep.patch",
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

    for dimension in policy.concept_schema.dimensions:
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
    windows_inspect = (
        "demo.py inspect-assurance --result "
        '"C:\\absolute\\path\\to\\assurance\\result.json"'
    )
    assert windows_inspect in normalized
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


def test_readme_documents_failure_modes_and_every_layer_label() -> None:
    driver = load_driver()
    readme = (DEMO / "README.md").read_text(encoding="utf-8")
    normalized = " ".join(readme.split())
    section = readme[
        readme.index("## Failure modes and explicit layer handling") : readme.index(
            "## 7. Reset"
        )
    ]

    for mode in driver.FAILURE_MODES:
        assert f"| `{mode}` |" in section
    for label in driver.LAYER_LABELS:
        assert f"| {label}" in section
    for name in driver.SCENARIOS:
        assert f"| `{name}` |" in section
    for rule in (
        "A check's `PASS` status alone never counts.",
        "Nothing is counted unless `ASSESSMENT_STATUS` is `COMPLETE`.",
        "SUBSTITUTED, UNAVAILABLE, and N-A layers are never counted",
        "An engine claim of coverage without counted evidence is an error.",
    ):
        assert rule in " ".join(section.split())
    for phrase in (
        "demo.py verify --layers",
        "demo.py layers --result",
        "control skip-evasion --enforce",
        "release-gate-demo-base-enforce",
        "UNVERIFIED import_declaration_mismatch",
        "a false release becomes an escalation",
        "### Known issues",
    ):
        assert phrase in normalized
    assert "`.release-gate-assurance.yaml`," in (DEMO / "assets" / "TASK.md").read_text(
        encoding="utf-8"
    )


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

    with pytest.raises(driver.DemoError, match=r"enforce base .* is missing"):
        driver._verify_repository()

    def tag_enforce_base(assurance: bytes, gate_policy: bytes | None = None) -> None:
        (repository / ".release-gate-assurance.yaml").write_bytes(assurance)
        git("add", ".release-gate-assurance.yaml")
        if gate_policy is not None:
            (repository / ".release-gate.yaml").write_bytes(gate_policy)
            git("add", ".release-gate.yaml")
        git("commit", "-qm", "enforce")
        git("tag", "-f", driver.ENFORCE_REF)
        git("reset", "-q", "--hard", driver.BASE_REF)

    tag_enforce_base(driver._enforce_policy_bytes(), POLICY.read_bytes() + b"\n")
    with pytest.raises(driver.DemoError, match="enforce base changed the gate policy"):
        driver._verify_repository()
    tag_enforce_base(driver._enforce_policy_bytes() + b"# extra\n")
    with pytest.raises(
        driver.DemoError, match="differ from the asset only by its mode"
    ):
        driver._verify_repository()
    tag_enforce_base(driver._enforce_policy_bytes())

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
    monkeypatch.setattr(
        driver,
        "_verify_reviewed_source_blobs",
        lambda: git_calls.append(("verify-reviewed-source-blobs",)),
        raising=False,
    )
    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    monkeypatch.setattr(driver, "_create_task_environment", lambda path: None)
    monkeypatch.setattr(driver, "_verify_upstream_tests", lambda: None)

    written: list[bytes] = []
    original_git = fake_git

    def recording_git(*arguments: str, **kwargs: object) -> str:
        if arguments[:1] == ("add",):
            written.append((repository / ".release-gate-assurance.yaml").read_bytes())
        return original_git(*arguments, **kwargs)

    monkeypatch.setattr(driver, "_git", recording_git)

    driver.setup()

    # The advisory policy is staged first; the enforce variant only afterwards.
    assert written[0] == ASSURANCE_POLICY.read_bytes()
    assert written[-1] == driver._enforce_policy_bytes()
    staged = (
        "add",
        ".release-gate.yaml",
        ".release-gate-assurance.yaml",
        ".gitignore",
    )
    assert staged in git_calls
    validation = ("verify-reviewed-source-blobs",)
    commit = ("commit", "--quiet", "-m", "chore: add release gate demo policy")
    tag = ("tag", driver.BASE_REF)
    enforce_commit = (
        "commit",
        "--quiet",
        "-m",
        "chore: enforce release gate demo assurance",
    )
    enforce_tag = ("tag", driver.ENFORCE_REF)
    back_to_base = ("reset", "--quiet", "--hard", driver.BASE_REF)
    # The reviewed sources include .release-gate.yaml, which exists at HEAD
    # only after the policy commit.
    assert (
        git_calls.index(staged)
        < git_calls.index(commit)
        < git_calls.index(validation)
        < git_calls.index(tag)
        < git_calls.index(enforce_commit)
        < git_calls.index(enforce_tag)
        < git_calls.index(back_to_base)
    )
    assert (repository / ".release-gate-assurance.yaml").read_bytes() == (
        driver._enforce_policy_bytes()
    )
    assert [command[-5:] for command in run_calls if "init" in command] == [
        ("init", "--repo", str(repository), "--from-config", str(POLICY))
    ]


def _layer_policy() -> dict[str, object]:
    policy = load_policy(ASSURANCE_POLICY.read_bytes())
    return {
        "mappings": [
            {
                "selector": mapping.selector.model_dump(),
                "concepts": dict(mapping.concepts),
                "sources": dict(mapping.sources),
            }
            for mapping in policy.mappings
        ],
        "required": [
            [region.dimension_id, region.value] for region in policy.required_regions
        ],
    }


def _layer_inputs(
    status: str = "COMPLETE", skipped: tuple[str, ...] = ()
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Build a consistent gate result, manifest and assurance result."""

    policy = _layer_policy()
    artifacts: list[dict[str, object]] = []
    unmet: list[dict[str, object]] = []
    if status == "COMPLETE":
        for mapping in policy["mappings"]:  # type: ignore[union-attr]
            selector = mapping["selector"]
            passed = selector["name"] not in skipped
            artifacts.append(
                {
                    "selector": selector,
                    "status": "PASS" if passed else "SKIPPED",
                    "eligible": passed,
                    "mapping_trusted": True,
                    "concepts": mapping["concepts"] if passed else {},
                }
            )
            if not passed:
                unmet.extend(
                    {"dimension_id": dimension, "value": value}
                    for dimension, value in mapping["concepts"].items()
                )
        artifacts.append(
            {
                "selector": {
                    "check_id": "tests-and-coverage",
                    "report_id": "junit",
                    "suite": "pytest",
                    "classname": "test.TestSlugify",
                    "name": "test_phonetic_conversion_of_eastern_scripts",
                },
                "status": "PASS",
                "eligible": True,
                "mapping_trusted": False,
                "concepts": {},
            }
        )
    assurance = {
        "run_id": "layers",
        "mode": "advisory",
        "gate_verdict": "PASS" if status == "COMPLETE" else "FAIL",
        "disposition": "PASS" if status == "COMPLETE" else "FAIL",
        "assessment_status": status,
        "evidence_sufficient": status == "COMPLETE" and not unmet,
        "artifacts": artifacts,
        "unmet_requirements": unmet,
    }
    gate = {
        "checks": [
            {"id": "tests-and-coverage", "status": "PASS"},
            {"id": "task-consistency", "status": "PASS"},
            {"id": "types", "status": "PASS"},
        ],
        "scope": {
            "status": "PASS",
            "forbidden_paths": [],
            "outside_allowed_paths": [],
            "review_required_paths": [],
        },
    }
    manifest = {
        "executions": [
            {
                "phase": "prepare",
                "control_id": "install-demo-dependencies",
                "side": "candidate",
                "classification": "pass",
            }
        ]
    }
    return assurance, gate, manifest


def _layer_row(report: dict[str, object], label: str, name: str) -> dict[str, object]:
    return next(
        row
        for row in report["layers"]  # type: ignore[union-attr]
        if row["label"] == label and row["layer"].startswith(name)
    )


def test_layer_report_counts_only_eligible_mapped_evidence() -> None:
    driver = load_driver()
    assurance, gate, manifest = _layer_inputs()

    report = driver.build_layer_report(assurance, gate, manifest, _layer_policy())

    assert report["unverified_failure_modes"] == []
    assert report["mapped_failure_modes"] == sorted(driver.MAPPED_FAILURE_MODES)
    assert _layer_row(report, "MAPPED", "unit tests")["counted_failure_modes"] == [
        "public_api_regression",
        "import_declaration_mismatch",
    ]
    for label in ("SUBSTITUTED", "UNAVAILABLE", "N-A"):
        for row in report["layers"]:
            if row["label"] == label:
                assert row["counts_as_evidence"] is False
                assert row["counted_failure_modes"] == []
    substitute = _layer_row(report, "SUBSTITUTED", "backend output")
    assert substitute["result"] == "PASS (substitute)"
    assert _layer_row(report, "SUBSTITUTED", "package build")["result"] == (
        "pass (substitute)"
    )
    assert _layer_row(report, "UNAVAILABLE", "lint")["result"] == "not run"
    assert set(report["unmapped_failure_modes"]) == {
        "scope_creep",
        "test_tampering",
        "policy_tampering",
        "backend_divergence",
    }


def test_layer_report_surfaces_a_skipped_mapped_case() -> None:
    driver = load_driver()
    assurance, gate, manifest = _layer_inputs(skipped=("test_cyrillic_text",))

    report = driver.build_layer_report(assurance, gate, manifest, _layer_policy())

    assert report["unverified_failure_modes"] == ["import_declaration_mismatch"]
    [entry] = [
        item
        for item in report["failure_modes"]
        if item["failure_mode"] == "import_declaration_mismatch"
    ]
    assert entry["evidence"] == [
        "test.TestSlugify::test_cyrillic_text: SKIPPED, not counted"
    ]
    unit_tests = _layer_row(report, "MAPPED", "unit tests")
    # The check still passed; the report must not turn that into coverage.
    assert unit_tests["result"] == "PASS"
    assert unit_tests["counted_failure_modes"] == ["public_api_regression"]


def test_layer_report_counts_nothing_when_assurance_was_not_evaluated() -> None:
    driver = load_driver()
    assurance, gate, manifest = _layer_inputs(status="NOT_EVALUATED")

    report = driver.build_layer_report(assurance, gate, manifest, _layer_policy())

    assert report["counted_evidence"] == 0
    assert report["unverified_failure_modes"] == report["mapped_failure_modes"]
    assert all(entry["evidence"] for entry in report["failure_modes"])
    assert all(
        "not assessed (NOT_EVALUATED)" in item
        for entry in report["failure_modes"]
        for item in entry["evidence"]
    )
    for row in report["layers"]:
        assert row["counted_failure_modes"] == []


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda assurance: assurance.update({"assessment_status": "NOT_EVALUATED"}),
            "counted while assessment NOT_EVALUATED",
        ),
        (
            lambda assurance: assurance["artifacts"][0].update({"eligible": False}),
            "concepts on an ineligible artifact",
        ),
        (
            lambda assurance: assurance["artifacts"][0].update({"status": "SKIPPED"}),
            "concepts on an ineligible artifact",
        ),
        (
            lambda assurance: assurance["artifacts"][0].update(
                {"mapping_trusted": False}
            ),
            "concepts on an ineligible artifact",
        ),
        (
            # Even a trusted, passing substitute must never become evidence.
            lambda assurance: assurance["artifacts"][-1].update(
                {
                    "mapping_trusted": True,
                    "concepts": {"failure_mode": "import_declaration_mismatch"},
                }
            ),
            "substitute .* was counted",
        ),
    ],
)
def test_layer_report_rejects_false_coverage(mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    driver = load_driver()
    assurance, gate, manifest = _layer_inputs()
    mutate(assurance)

    with pytest.raises(driver.DemoError, match=message):
        driver.build_layer_report(assurance, gate, manifest, _layer_policy())


def test_layer_report_rejects_an_engine_claim_without_counted_evidence() -> None:
    driver = load_driver()
    assurance, gate, manifest = _layer_inputs(skipped=("test_cyrillic_text",))
    assurance["unmet_requirements"] = []

    with pytest.raises(driver.DemoError, match="met without counted evidence"):
        driver.build_layer_report(assurance, gate, manifest, _layer_policy())


def test_layer_report_trusts_the_engine_when_support_is_below_its_minimum() -> None:
    driver = load_driver()
    assurance, gate, manifest = _layer_inputs()
    assurance["unmet_requirements"] = [
        {"dimension_id": "failure_mode", "value": "type_regression"}
    ]

    report = driver.build_layer_report(assurance, gate, manifest, _layer_policy())

    assert report["unverified_failure_modes"] == ["type_regression"]


def test_layer_report_shows_scope_violations_without_counting_them() -> None:
    driver = load_driver()
    assurance, gate, manifest = _layer_inputs(status="NOT_EVALUATED")
    gate["scope"] = {
        "status": "NEEDS_HUMAN",
        "forbidden_paths": [],
        "outside_allowed_paths": ["CHANGELOG.md"],
        "review_required_paths": ["CHANGELOG.md"],
    }

    report = driver.build_layer_report(assurance, gate, manifest, _layer_policy())

    scope = _layer_row(report, "MAPPED", "scope rules")
    assert scope["result"] == (
        "NEEDS_HUMAN (outside allowed CHANGELOG.md; review required CHANGELOG.md)"
    )
    assert scope["counts_as_evidence"] is False


def test_layer_command_prints_and_saves_the_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    driver = load_driver()
    assurance, gate, manifest = _layer_inputs(skipped=("test_cyrillic_text",))
    gate_package = tmp_path / "gate"
    gate_package.mkdir()
    gate["manifest_path"] = "manifest.json"
    (gate_package / "result.json").write_text(json.dumps(gate), encoding="utf-8")
    (gate_package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    package = tmp_path / "assurance"
    package.mkdir()
    assurance["gate_result_path"] = str((gate_package / "result.json").resolve())
    (package / "result.json").write_text(json.dumps(assurance), encoding="utf-8")
    (package / "manifest.json").write_text("{}", encoding="utf-8")
    (package / "policy.yaml").write_bytes(ASSURANCE_POLICY.read_bytes())
    monkeypatch.setattr(driver, "WORKBENCH", tmp_path)
    monkeypatch.setattr(driver, "LAYER_REPORTS", tmp_path / "reports")
    monkeypatch.setattr(driver, "_load_assurance_policy", lambda path: _layer_policy())

    assert driver.main(["layers", "--result", str(package / "result.json")]) == 0

    output = capsys.readouterr().out
    assert (
        "[MAPPED     ] unit tests (82 upstream cases): PASS; guards "
        "public_api_regression, import_declaration_mismatch; verified "
        "public_api_regression; UNVERIFIED import_declaration_mismatch"
    ) in output
    assert "[N-A        ] UI, database, and network: not run" in output
    assert "never counted as evidence" in output
    assert "import_declaration_mismatch: UNVERIFIED" in output
    saved = json.loads((tmp_path / "reports" / "layers.json").read_text("utf-8"))
    assert saved["unverified_failure_modes"] == ["import_declaration_mismatch"]


def test_layer_command_never_creates_the_workbench(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Setup refuses an existing workbench, so reporting must not create one."""

    driver = load_driver()
    assurance, gate, manifest = _layer_inputs()
    package = tmp_path / "assurance"
    package.mkdir()
    gate["manifest_path"] = "manifest.json"
    (tmp_path / "result.json").write_text(json.dumps(gate), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assurance["gate_result_path"] = str((tmp_path / "result.json").resolve())
    (package / "result.json").write_text(json.dumps(assurance), encoding="utf-8")
    (package / "manifest.json").write_text("{}", encoding="utf-8")
    workbench = tmp_path / "missing-workbench"
    monkeypatch.setattr(driver, "WORKBENCH", workbench)
    monkeypatch.setattr(driver, "LAYER_REPORTS", workbench / "layer-reports")
    monkeypatch.setattr(driver, "_load_assurance_policy", lambda path: _layer_policy())

    report = driver.layer_report(package / "result.json")

    assert report["unverified_failure_modes"] == []
    assert not workbench.exists()
    assert "layer report: not saved (no demo workbench)" in capsys.readouterr().out


def test_grading_skips_the_oracle_when_both_decisions_escalate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = load_driver()
    oracle_runs: list[bool] = []

    def fake_inspect(path: Path) -> object:
        return type("Summary", (), {"verdict": verdict})()

    monkeypatch.setattr(driver, "_verify_repository", lambda: None)
    monkeypatch.setattr(driver, "inspect_result", fake_inspect)
    monkeypatch.setattr(
        driver, "_oracle_truth", lambda: oracle_runs.append(True) or False
    )

    verdict = "NEEDS_HUMAN"
    assert driver._grade_run(tmp_path, "NEEDS_HUMAN") == ("escalated", "escalated")
    assert driver.grade(tmp_path) == "escalated"
    assert oracle_runs == []

    verdict = "PASS"
    assert driver._grade_run(tmp_path, "NEEDS_HUMAN") == (
        "FALSE_RELEASE",
        "escalated",
    )
    assert oracle_runs == [True]


def test_insufficient_assurance_must_match_the_expected_unmet_requirements() -> None:
    driver = load_driver()
    values = {
        "run_id": "verify-skip-evasion",
        "gate_result_path": "/absolute/gate/result.json",
        "mode": "enforce",
        "gate_verdict": "PASS",
        "disposition": "NEEDS_HUMAN",
        "assessment_status": "COMPLETE",
        "evidence_sufficient": False,
        "reason_codes": ("ASSURANCE_INSUFFICIENT",),
        "coverage": {"mapping_uncertainty_rate": 0.952},
        "unmet_requirements": (
            {"dimension_id": "behavior_region", "value": "transliteration"},
            {"dimension_id": "failure_mode", "value": "import_declaration_mismatch"},
        ),
    }
    expected = driver.SCENARIOS["skip-evasion-enforce"]
    arguments = ("PASS", "NEEDS_HUMAN", "COMPLETE")
    options = {"mode": "enforce", "sufficient": False, "unmet": expected.unmet}

    driver._validate_assurance_control(
        "skip", driver.AssuranceSummary(**values), *arguments, **options
    )
    with pytest.raises(driver.DemoError, match="expected assurance mode enforce"):
        driver._validate_assurance_control(
            "skip",
            driver.AssuranceSummary(**{**values, "mode": "advisory"}),
            *arguments,
            **options,
        )
    with pytest.raises(driver.DemoError, match="expected unmet requirements"):
        driver._validate_assurance_control(
            "skip",
            driver.AssuranceSummary(**{**values, "unmet_requirements": ()}),
            *arguments,
            **options,
        )
    with pytest.raises(driver.DemoError, match="expected insufficient"):
        driver._validate_assurance_control(
            "skip",
            driver.AssuranceSummary(**{**values, "evidence_sufficient": True}),
            *arguments,
            **options,
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
