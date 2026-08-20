from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from release_gate.cli import main
from release_gate.evidence import EvidenceError, EvidenceRun, verify_run


def git(repo: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *arguments], capture_output=True, check=True
    )


def repository(
    tmp_path: Path, command: list[str], *, severity: str = "blocking"
) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "--initial-branch=main")
    git(repo, "config", "user.email", "gate@example.invalid")
    git(repo, "config", "user.name", "Release Gate Test")
    argv = json.dumps(command)
    policy = f"""\
version: 1
scope:
  allowed_paths: ["**"]
  review_required_paths: ["/.release-gate.yaml"]
checks:
  - id: tests
    mode: candidate
    severity: {severity}
    argv: {argv}
"""
    (repo / ".release-gate.yaml").write_text(policy, encoding="utf-8")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    (repo / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    return repo


@pytest.mark.parametrize(
    ("command", "severity", "exit_code", "verdict", "status"),
    [
        ([sys.executable, "-c", "print('ok')"], "blocking", 0, "PASS", "PASS"),
        (
            [sys.executable, "-c", "raise SystemExit(1)"],
            "blocking",
            1,
            "FAIL",
            "FAIL",
        ),
        (
            [sys.executable, "-c", "raise SystemExit(1)"],
            "advisory",
            2,
            "NEEDS_HUMAN",
            "FAIL",
        ),
    ],
)
def test_run_produces_three_way_verdict_and_verified_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: list[str],
    severity: str,
    exit_code: int,
    verdict: str,
    status: str,
) -> None:
    repo = repository(tmp_path, command, severity=severity)
    output = tmp_path / "evidence"
    assert (
        main(
            [
                "run",
                "--repo",
                str(repo),
                "--base",
                "HEAD",
                "--output",
                str(output),
                "--run-id",
                "test-run",
            ]
        )
        == exit_code
    )
    printed = capsys.readouterr()
    assert f"VERDICT: {verdict}\n" in printed.out
    run = output / "test-run"
    result = json.loads((run / "result.json").read_bytes())
    assert result["verdict"] == verdict
    assert result["checks"][0]["status"] == status
    assert (run / "controls/tests/candidate/stdout.log").exists()
    verify_run(run)


def test_run_publishes_verified_snapshot_and_stable_dashboard(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repository(tmp_path, [sys.executable, "-c", "print('ok')"])
    output = tmp_path / "custom-evidence"

    assert main(
        [
            "run", "--repo", str(repo), "--base", "HEAD", "--output", str(output),
            "--run-id", "observed",
        ]
    ) == 0
    captured = capsys.readouterr()
    snapshot = output / "observed/observability/gate-decisions.html"
    dashboard = output / "_observability/index.html"
    data = output / "_observability/gate-decisions-v1.json"
    assert snapshot.exists() and dashboard.exists() and data.exists()
    assert b'"run_id":"observed"' in snapshot.read_bytes()
    assert f"SNAPSHOT: {snapshot.absolute()}\n" in captured.err
    assert f"DASHBOARD: {dashboard.absolute()}\n" in captured.err
    assert f"OBSERVABILITY_DATA: {data.absolute()}\n" in captured.err
    assert captured.out == (
        f"VERDICT: PASS\nRESULT: {output / 'observed' / 'result.json'}\n"
    )
    verify_run(output / "observed")


def test_finalization_failure_never_publishes_stable_observability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repository(tmp_path, [sys.executable, "-c", "print('ok')"])
    output = tmp_path / "evidence"

    def fail_finalize(
        self: EvidenceRun,
        result: dict[str, object],
        manifest: dict[str, object],
        trace: bytes,
    ) -> Path:
        raise EvidenceError("finalization failed")

    monkeypatch.setattr(EvidenceRun, "finalize", fail_finalize)
    assert main(
        ["run", "--repo", str(repo), "--base", "HEAD", "--output", str(output)]
    ) == 4
    assert not (output / "_observability/gate-decisions-v1.json").exists()
    assert not (output / "_observability/index.html").exists()


def test_shared_custom_root_rolls_up_all_three_gate_verdicts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "shared-evidence"
    cases = (
        ([sys.executable, "-c", "print('ok')"], "blocking", "PASS"),
        ([sys.executable, "-c", "raise SystemExit(1)"], "blocking", "FAIL"),
        ([sys.executable, "-c", "raise SystemExit(1)"], "advisory", "NEEDS_HUMAN"),
    )
    for index, (command, severity, verdict) in enumerate(cases):
        case_root = tmp_path / f"case-{index}"
        case_root.mkdir()
        repo = repository(case_root, command, severity=severity)
        assert main(
            [
                "run", "--repo", str(repo), "--base", "HEAD", "--output", str(output),
                "--run-id", f"verdict-{index}",
            ]
        ) == index
        captured = capsys.readouterr()
        assert captured.out.startswith(f"VERDICT: {verdict}\n")
    report = json.loads((output / "_observability/gate-decisions-v1.json").read_bytes())
    assert [item["verdict"] for item in report["source_runs"]] == [
        "PASS", "FAIL", "NEEDS_HUMAN"
    ]
    assert report["series"][-1]["windows"]["10"]["counts"] == {
        "releasing": 1, "failing": 1, "human_review": 1
    }
    assert report["series"][-1]["windows"]["100"]["sample_size"] == 3


def test_policy_change_stops_commands_and_needs_human(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repository(tmp_path, [sys.executable, "-c", "print('should-not-run')"])
    policy = repo / ".release-gate.yaml"
    policy.write_text(policy.read_text() + "\n# candidate edit\n", encoding="utf-8")
    output = tmp_path / "evidence"

    assert main(
        [
            "run",
            "--repo",
            str(repo),
            "--base",
            "HEAD",
            "--output",
            str(output),
            "--run-id",
            "policy-edit",
        ]
    ) == 2
    capsys.readouterr()
    result = json.loads((output / "policy-edit/result.json").read_bytes())
    manifest = json.loads((output / "policy-edit/manifest.json").read_bytes())
    assert result["verdict"] == "NEEDS_HUMAN"
    assert result["checks"][0]["status"] == "SKIPPED"
    assert "POLICY_FILE_CHANGED" in result["reason_codes"]
    assert manifest["executions"][0]["classification"] == "skipped"
    assert not (output / "policy-edit/controls/tests/candidate/stdout.log").exists()
    verify_run(output / "policy-edit")


def test_invalid_candidate_returns_exit_3_without_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repository(tmp_path, [sys.executable, "-c", "print('ok')"])
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    output = tmp_path / "evidence"
    assert main(
        ["run", "--repo", str(repo), "--base", "HEAD", "--output", str(output)]
    ) == 3
    assert "empty candidate" in capsys.readouterr().err
    assert not output.exists()


def test_invalid_output_file_returns_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repository(tmp_path, [sys.executable, "-c", "print('ok')"])
    output = tmp_path / "not-a-directory"
    output.write_text("owned\n", encoding="utf-8")
    assert main(
        ["run", "--repo", str(repo), "--base", "HEAD", "--output", str(output)]
    ) == 3
    assert "evidence root" in capsys.readouterr().err
    assert output.read_text(encoding="utf-8") == "owned\n"


def test_preparation_failure_skips_check_and_preserves_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = repository(tmp_path, [sys.executable, "-c", "print('unused')"])
    policy = f"""\
version: 1
scope:
  allowed_paths: ["**"]
  review_required_paths: ["/.release-gate.yaml"]
prepare:
  - id: setup
    argv: {json.dumps([sys.executable, "-c", "raise SystemExit(1)"])}
checks:
  - id: tests
    mode: candidate
    severity: blocking
    argv: {json.dumps([sys.executable, "-c", "print('unused')"])}
    reports:
      - id: metrics
        parser: json-metrics
        path: metrics.json
    assertions:
      - report: metrics
        metric: /score
        comparison: candidate
        operator: gte
        value: 1
"""
    (repo / ".release-gate.yaml").write_text(policy, encoding="utf-8")
    git(repo, "add", ".release-gate.yaml")
    git(repo, "commit", "-qm", "configure preparation")
    (repo / "tracked.txt").write_text("another candidate\n", encoding="utf-8")
    output = tmp_path / "evidence"

    assert main(
        [
            "run",
            "--repo",
            str(repo),
            "--base",
            "HEAD",
            "--output",
            str(output),
            "--run-id",
            "prep",
        ]
    ) == 2
    capsys.readouterr()
    result = json.loads((output / "prep/result.json").read_bytes())
    manifest = json.loads((output / "prep/manifest.json").read_bytes())
    assert result["checks"][0]["status"] == "SKIPPED"
    assert result["checks"][0]["assertions"] == []
    assert "PREPARATION_FAILED" in result["reason_codes"]
    assert [item["classification"] for item in manifest["executions"]] == [
        "fail",
        "skipped",
    ]
    verify_run(output / "prep")


def test_json_report_assertion_is_recorded_and_enforced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = "from pathlib import Path;Path('metrics.json').write_text('{\"score\":7}')"
    repo = repository(tmp_path, [sys.executable, "-c", code])
    policy = f"""\
version: 1
scope:
  allowed_paths: ["**"]
  review_required_paths: ["/.release-gate.yaml"]
checks:
  - id: metrics
    mode: candidate
    severity: blocking
    argv: {json.dumps([sys.executable, "-c", code])}
    reports:
      - id: score
        parser: json-metrics
        path: metrics.json
    assertions:
      - report: score
        metric: /score
        comparison: candidate
        operator: gte
        value: 7
"""
    (repo / ".release-gate.yaml").write_text(policy, encoding="utf-8")
    git(repo, "add", ".release-gate.yaml")
    git(repo, "commit", "-qm", "configure metrics")
    (repo / "tracked.txt").write_text("metrics candidate\n", encoding="utf-8")
    output = tmp_path / "evidence"

    assert main(
        [
            "run",
            "--repo",
            str(repo),
            "--base",
            "HEAD",
            "--output",
            str(output),
            "--run-id",
            "metrics",
        ]
    ) == 0
    capsys.readouterr()
    result = json.loads((output / "metrics/result.json").read_bytes())
    manifest = json.loads((output / "metrics/manifest.json").read_bytes())
    assert result["checks"][0]["assertions"][0]["passed"] is True
    assert manifest["executions"][0]["metrics"] == {"score#/score": 7}
    assert (output / "metrics/controls/metrics/candidate/reports/score.json").exists()
    verify_run(output / "metrics")


def test_differential_check_runs_base_then_candidate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = (
        "from pathlib import Path;"
        "raise SystemExit(1 if Path('tracked.txt').read_text()"
        ".startswith('candidate') else 0)"
    )
    repo = repository(tmp_path, [sys.executable, "-c", code])
    policy = (repo / ".release-gate.yaml").read_text().replace(
        "mode: candidate", "mode: differential"
    )
    (repo / ".release-gate.yaml").write_text(policy, encoding="utf-8")
    git(repo, "add", ".release-gate.yaml")
    git(repo, "commit", "-qm", "configure differential")
    (repo / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    output = tmp_path / "evidence"

    assert main(
        [
            "run",
            "--repo",
            str(repo),
            "--base",
            "HEAD",
            "--output",
            str(output),
            "--run-id",
            "diff",
        ]
    ) == 1
    capsys.readouterr()
    manifest = json.loads((output / "diff/manifest.json").read_bytes())
    assert [entry["side"] for entry in manifest["executions"]] == [
        "base",
        "candidate",
    ]
    assert [entry["classification"] for entry in manifest["executions"]] == [
        "pass",
        "fail",
    ]
    verify_run(output / "diff")


def test_node_repository_produces_verified_pass_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable")
    repo = repository(tmp_path, [node, "-e", "console.log('ok')"])
    output = tmp_path / "evidence"

    assert main(
        [
            "run",
            "--repo",
            str(repo),
            "--base",
            "HEAD",
            "--output",
            str(output),
            "--run-id",
            "node-pass",
        ]
    ) == 0
    capsys.readouterr()
    result = json.loads((output / "node-pass/result.json").read_bytes())
    assert result["verdict"] == "PASS"
    verify_run(output / "node-pass")


def test_runtime_evidence_budget_exhaustion_finalizes_needs_human(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = "import sys;sys.stdout.buffer.write(b'x'*10000000)"
    repo = repository(tmp_path, [sys.executable, "-c", code])
    policy_path = repo / ".release-gate.yaml"
    policy = policy_path.read_text(encoding="utf-8").replace(
        "checks:\n",
        "limits:\n"
        "  stream_bytes: 10485760\n"
        "  total_bytes: 16777216\n"
        "checks:\n",
    )
    policy_path.write_text(policy, encoding="utf-8")
    git(repo, "add", ".release-gate.yaml")
    git(repo, "commit", "-qm", "configure bounded evidence")
    (repo / "tracked.txt").write_text("budget candidate\n", encoding="utf-8")
    output = tmp_path / "evidence"

    assert main(
        [
            "run",
            "--repo",
            str(repo),
            "--base",
            "HEAD",
            "--output",
            str(output),
            "--run-id",
            "budget",
        ]
    ) == 2
    capsys.readouterr()
    run = output / "budget"
    result = json.loads((run / "result.json").read_bytes())
    assert result["verdict"] == "NEEDS_HUMAN"
    assert result["checks"][0]["status"] == "ERROR"
    assert "EVIDENCE_BUDGET_EXHAUSTED" in result["reason_codes"]
    verify_run(run)
