from __future__ import annotations

import hashlib
import json
import sys

import pytest
import yaml
from test_engine import git, repository

from release_gate.cli import main
from release_gate.evidence import verify_run


def setup_repo(tmp_path, *, xml=None, mode="enforce", mapped=True, minimum=1):
    source = "reviewed test source\n"
    command = [sys.executable, "-c", "print('ok')"]
    if xml is not None:
        command = [
            sys.executable,
            "-c",
            f"from pathlib import Path; Path('junit.xml').write_text({xml!r})",
        ]
    repo = repository(tmp_path, command)
    (repo / "tests.txt").write_text(source)
    gate = yaml.safe_load((repo / ".release-gate.yaml").read_text())
    if xml is not None:
        gate["checks"][0]["reports"] = [
            {"id": "junit", "path": "junit.xml", "parser": "junit-xml"}
        ]
    (repo / ".release-gate.yaml").write_text(yaml.safe_dump(gate))
    selector = {"check_id": "tests"}
    if xml is not None:
        selector.update(
            report_id="junit", suite="suite", classname="C", name="boundary"
        )
    policy = {
        "version": 1,
        "mode": mode,
        "concept_schema": {
            "schema_id": "example",
            "schema_version": "1",
            "dimensions": [
                {
                    "dimension_id": "behavior",
                    "name": "Behavior",
                    "definition": "Reviewed behavior",
                    "values": ["boundary", "normal"],
                }
            ],
        },
        "mappings": [
            {
                "selector": selector,
                "concepts": {"behavior": "boundary"},
                "sources": {"tests.txt": hashlib.sha256(source.encode()).hexdigest()},
                "independence_group": "seed",
            }
        ]
        if mapped
        else [],
        "required_regions": [
            {
                "dimension_id": "behavior",
                "value": "boundary",
                "minimum_independent_support": minimum,
            }
        ],
        "maximum_mapping_uncertainty_rate": 0.0,
    }
    (repo / ".release-gate-assurance.yaml").write_text(yaml.safe_dump(policy))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "reviewed assurance policy")
    (repo / "tracked.txt").write_text("new candidate\n")
    return repo


def assure(repo, tmp_path):
    output = tmp_path / "evidence"
    code = main(
        [
            "assure",
            "--repo",
            str(repo),
            "--base",
            "HEAD",
            "--output",
            str(output),
            "--run-id",
            "assured",
        ]
    )
    path = output / "_assurance" / "assured" / "result.json"
    return code, json.loads(path.read_text()) if path.exists() else None


@pytest.mark.parametrize(
    "mode,mapped,expected",
    [("enforce", True, 0), ("enforce", False, 2), ("advisory", False, 0)],
)
def test_assurance_enforcement(tmp_path, mode, mapped, expected):
    repo = setup_repo(tmp_path, mode=mode, mapped=mapped)
    code, result = assure(repo, tmp_path)
    assert code == expected
    assert result["gate_verdict"] == "PASS"
    assert result["assessment_status"] == "COMPLETE"
    assert result["evidence_sufficient"] is mapped
    verify_run(tmp_path / "evidence" / "assured")


@pytest.mark.parametrize(
    "body,expected", [("", 0), ("<skipped/>", 2), ("<failure/>", 2), ("<error/>", 2)]
)
def test_junit_case_requires_pass(tmp_path, body, expected):
    xml = (
        '<testsuite name="suite" tests="1">'
        f'<testcase classname="C" name="boundary">{body}</testcase>'
        "</testsuite>"
    )
    repo = setup_repo(tmp_path, xml=xml)
    code, result = assure(repo, tmp_path)
    assert code == expected
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["selector"]["name"] == "boundary"


def test_duplicate_case_identity_cannot_support_region(tmp_path):
    case = '<testcase classname="C" name="boundary"/>'
    repo = setup_repo(
        tmp_path, xml=f'<testsuite name="suite" tests="2">{case}{case}</testsuite>'
    )
    code, result = assure(repo, tmp_path)
    assert code == 2
    assert not result["evidence_sufficient"]


@pytest.mark.parametrize("changed", ["tests.txt", ".release-gate-assurance.yaml"])
def test_candidate_cannot_reuse_changed_reviewed_mapping(tmp_path, changed):
    repo = setup_repo(tmp_path)
    with (repo / changed).open("a") as f:
        f.write("# changed\n")
    code, result = assure(repo, tmp_path)
    assert code == 2
    assert not result["evidence_sufficient"]


def test_missing_policy_is_input_error(tmp_path):
    repo = repository(tmp_path, [sys.executable, "-c", "print('ok')"])
    code, result = assure(repo, tmp_path)
    assert code == 3
    assert result is None


def test_minimum_independent_support_is_enforced(tmp_path):
    repo = setup_repo(tmp_path, minimum=2)
    code, result = assure(repo, tmp_path)
    assert code == 2
    assert result["unmet_requirements"][0]["independent_support"] == 1


def test_mapper_is_installable_domain_neutral_package():
    import importlib.util

    assert importlib.util.find_spec("conceptual_diversity_mapper") is not None


def update_base_policy(repo, update):
    path = repo / ".release-gate-assurance.yaml"
    policy = yaml.safe_load(path.read_text())
    update(policy)
    path.write_text(yaml.safe_dump(policy))
    git(repo, "add", str(path))
    git(repo, "commit", "-qm", "review policy revision")


@pytest.mark.parametrize("mode,expected", [("enforce", 2), ("advisory", 0)])
def test_mapper_failure_is_explicit(tmp_path, monkeypatch, mode, expected):
    from release_gate.assurance import service

    repo = setup_repo(tmp_path, mode=mode)

    def broken(*args):
        raise RuntimeError("mapper unavailable")

    monkeypatch.setattr(service, "assess", broken)
    code, result = assure(repo, tmp_path)
    assert code == expected
    assert result["assessment_status"] == "UNAVAILABLE"
    assert not result["evidence_sufficient"]


@pytest.mark.parametrize(
    "limit,value",
    [
        ("max_artifacts", 1),
        ("max_report_bytes", 1),
        ("max_total_report_bytes", 1),
        ("max_elapsed_seconds", 0.000001),
    ],
)
def test_assessment_limits_fail_closed(tmp_path, limit, value):
    case = '<testcase classname="C" name="boundary"/>'
    repo = setup_repo(
        tmp_path, xml=f'<testsuite name="suite" tests="2">{case}{case}</testsuite>'
    )
    update_base_policy(repo, lambda p: p.update(limits={limit: value}))
    code, result = assure(repo, tmp_path)
    assert code == 2
    assert result["assessment_status"] == "UNAVAILABLE"


def test_finalization_failure_never_returns_success(tmp_path, monkeypatch):
    from release_gate.assurance import service

    repo = setup_repo(tmp_path)

    def broken(*args):
        raise OSError("disk full")

    monkeypatch.setattr(service, "persist", broken)
    code, result = assure(repo, tmp_path)
    assert code == 4
    assert result is None


@pytest.mark.parametrize("severity,expected", [("blocking", 1), ("advisory", 2)])
def test_nonpassing_gate_does_not_invoke_mapper(
    tmp_path, monkeypatch, severity, expected
):
    from release_gate.assurance import service

    repo = setup_repo(tmp_path)
    path = repo / ".release-gate.yaml"
    policy = yaml.safe_load(path.read_text())
    policy["checks"][0].update(
        argv=[sys.executable, "-c", "raise SystemExit(1)"], severity=severity
    )
    path.write_text(yaml.safe_dump(policy))
    git(repo, "add", str(path))
    git(repo, "commit", "-qm", "failing control")

    def forbidden(*args):
        pytest.fail("mapper must not run for a nonpassing gate")

    monkeypatch.setattr(service, "assess", forbidden)
    code, result = assure(repo, tmp_path)
    assert code == expected
    assert result["assessment_status"] == "NOT_EVALUATED"


def test_differential_pass_does_not_prove_candidate_success(tmp_path):
    repo = setup_repo(tmp_path)
    path = repo / ".release-gate.yaml"
    policy = yaml.safe_load(path.read_text())
    policy["checks"][0].update(
        mode="differential", argv=[sys.executable, "-c", "raise SystemExit(1)"]
    )
    path.write_text(yaml.safe_dump(policy))
    git(repo, "add", str(path))
    git(repo, "commit", "-qm", "differential control")
    code, result = assure(repo, tmp_path)
    assert code == 2
    assert result["gate_verdict"] == "PASS"
    assert result["artifacts"][0]["eligible"] is False


def test_changed_policy_blocks_even_advisory(tmp_path):
    repo = setup_repo(tmp_path, mode="advisory")
    (repo / ".release-gate-assurance.yaml").write_text("mode: advisory\n")
    code, result = assure(repo, tmp_path)
    assert code == 2
    assert "ASSURANCE_POLICY_CHANGED" in result["reason_codes"]


def test_assessment_worker_has_hard_deadline():
    from release_gate.assurance import service

    assert hasattr(service, "assess_bounded")
    # Deadline is already exhausted; no subprocess should be started.
    with pytest.raises(ValueError, match="deadline"):
        service.assess_bounded(None, [], "candidate", 0)


def test_result_package_can_be_verified_and_tampering_is_rejected(tmp_path):
    from release_gate.assurance import service

    assert hasattr(service, "verify_assurance")
    repo = setup_repo(tmp_path)
    assure(repo, tmp_path)
    package = tmp_path / "evidence/_assurance/assured"
    service.verify_assurance(package)
    (package / "policy.yaml").write_text("tampered")
    with pytest.raises(ValueError):
        service.verify_assurance(package)


@pytest.mark.parametrize(
    "attributes",
    [
        'status="unknown"',
        'status="failed"',
        'status="error"',
        'result="Skipped"',
        'result="unknown"',
    ],
)
def test_unknown_or_nonpassing_junit_outcome_never_supports_region(
    tmp_path, attributes
):
    xml = (
        '<testsuite name="suite" tests="1">'
        f'<testcase classname="C" name="boundary" {attributes}/>'
        "</testsuite>"
    )
    repo = setup_repo(tmp_path, xml=xml)
    code, result = assure(repo, tmp_path)
    assert code == 2
    assert not result["artifacts"][0]["eligible"]


def test_normalization_runs_inside_bounded_worker(tmp_path, monkeypatch):
    from release_gate.assurance import service

    repo = setup_repo(tmp_path)

    def forbidden(*args):
        pytest.fail("normalization ran in the unbounded parent process")

    monkeypatch.setattr(service, "normalize", forbidden)
    code, result = assure(repo, tmp_path)
    assert code == 0
    assert result["evidence_sufficient"]
