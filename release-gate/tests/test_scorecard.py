from __future__ import annotations

import hashlib
import json
import sys

import yaml
from test_engine import git, repository

from release_gate.cli import main
from release_gate.scorecard import build_scorecard

# Writes a two-case JUnit report; the "boundary" case skips once flag.txt exists.
JUNIT_COMMAND = (
    "from pathlib import Path; skip = Path('flag.txt').exists(); "
    "body = '<skipped/>' if skip else ''; "
    "Path('junit.xml').write_text("
    'f\'<testsuite name="suite" tests="2" skipped="{int(skip)}">\''
    'f\'<testcase classname="C" name="boundary">{body}</testcase>\''
    '\'<testcase classname="C" name="other"/></testsuite>\')'
)


def skip_repo(tmp_path, *, assured=True):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "--initial-branch=main")
    git(repo, "config", "user.email", "gate@example.invalid")
    git(repo, "config", "user.name", "Release Gate Test")
    gate = {
        "version": 1,
        "scope": {
            "allowed_paths": ["**"],
            "review_required_paths": ["/.release-gate.yaml"],
        },
        "checks": [
            {
                "id": "tests",
                "mode": "differential",
                "severity": "blocking",
                "argv": [sys.executable, "-c", JUNIT_COMMAND],
                "reports": [
                    {"id": "junit", "path": "junit.xml", "parser": "junit-xml"}
                ],
                "assertions": [
                    {
                        "report": "junit",
                        "metric": "/failures",
                        "comparison": "candidate-minus-baseline",
                        "operator": "lte",
                        "value": 0,
                    }
                ],
            }
        ],
    }
    (repo / ".release-gate.yaml").write_text(yaml.safe_dump(gate))
    source = "reviewed test source\n"
    (repo / "tests.txt").write_text(source)
    if assured:
        policy = {
            "version": 1,
            "mode": "advisory",
            "concept_schema": {
                "schema_id": "example",
                "schema_version": "1",
                "dimensions": [
                    {
                        "dimension_id": "behavior",
                        "name": "Behavior",
                        "definition": "Reviewed behavior",
                        "values": ["boundary"],
                    }
                ],
            },
            "mappings": [
                {
                    "selector": {
                        "check_id": "tests",
                        "report_id": "junit",
                        "suite": "suite",
                        "classname": "C",
                        "name": "boundary",
                    },
                    "concepts": {"behavior": "boundary"},
                    "sources": {
                        "tests.txt": hashlib.sha256(source.encode()).hexdigest()
                    },
                }
            ],
            "required_regions": [
                {
                    "dimension_id": "behavior",
                    "value": "boundary",
                    "minimum_independent_support": 1,
                }
            ],
            "maximum_mapping_uncertainty_rate": 1.0,
        }
        (repo / ".release-gate-assurance.yaml").write_text(yaml.safe_dump(policy))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    (repo / "flag.txt").write_text("skip\n")
    return repo


def gate(repo, tmp_path, command="run"):
    output = tmp_path / "evidence"
    arguments = [command, "--repo", str(repo), "--base", "HEAD"]
    main([*arguments, "--output", str(output), "--run-id", "scored"])
    return output / "scored"


def test_skipped_case_is_scored_although_gate_passes(tmp_path):
    run = gate(skip_repo(tmp_path), tmp_path, "assure")
    card = build_scorecard(run)
    assert card["verdict"] == "PASS"
    assert (card["d_tests"], card["d_failures"], card["d_skipped"]) == (0, 0, 1)
    assert (card["topics_met"], card["topics_total"]) == (0, 1)
    assert card["flags"] == ""


def test_run_without_assurance_has_no_topics(tmp_path, capsys):
    run = gate(skip_repo(tmp_path, assured=False), tmp_path)
    capsys.readouterr()
    assert main(["score", "--run", str(run)]) == 0
    card = json.loads(capsys.readouterr().out)
    assert card["d_skipped"] == 1
    assert card["topics_met"] is None and card["topics_total"] is None


def test_candidate_check_has_no_deltas(tmp_path):
    repo = repository(tmp_path, [sys.executable, "-c", "print('ok')"])
    card = build_scorecard(gate(repo, tmp_path))
    assert card["verdict"] == "PASS"
    assert card["d_tests"] is None and card["coverage"] is None
    assert card["changed_paths"] == 1


def test_tampered_run_is_rejected(tmp_path):
    run = gate(skip_repo(tmp_path, assured=False), tmp_path)
    result = run / "result.json"
    result.write_text(result.read_text().replace('"PASS"', '"FAIL"', 1))
    assert main(["score", "--run", str(run)]) == 3
