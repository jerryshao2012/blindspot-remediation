"""End-to-end integration tests for the Release Gate repair workflow."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from release_gate.cli import main
from release_gate.git import _base_git_environment
from release_gate.repair.models import FinalApproval


def _init_repo(path: Path) -> str:
    env = _base_git_environment()
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        env=env,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "IntegrationTest"],
        check=True,
        env=env,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
        env=env,
    )

    python_exe = sys.executable.replace("\\", "/")
    policy = f"""\\
version: 1
scope:
  allowed_paths: ["**"]
  forbidden_paths: []
  review_required_paths: [".release-gate.yaml"]
prepare: []
checks:
  - id: math-check
    mode: candidate
    severity: blocking
    argv: ["{python_exe}", "test_math.py"]
"""
    (path / ".release-gate.yaml").write_text(policy, encoding="utf-8")
    (path / ".gitignore").write_text("/.release-gate/runs/\n", encoding="utf-8")
    (path / "app.py").write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
    (path / "test_math.py").write_text(
        "from app import add\nassert add(2, 3) == 5\n", encoding="utf-8"
    )

    # Optional base-trusted playbook
    playbook_dir = path / ".release-gate" / "repair"
    playbook_dir.mkdir(parents=True, exist_ok=True)
    playbook_content = """\
version: 1
checks:
  math-check:
    guidance: "Fix addition logic in app.py."
    extra_approved_paths: ["app.py"]
"""
    (playbook_dir / "math.yaml").write_text(playbook_content, encoding="utf-8")

    subprocess.run(["git", "-C", str(path), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "Base commit with initial app"],
        check=True,
        env=env,
    )

    return (
        subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            env=env,
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )


def test_repair_integration_e2e_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    # 1. Developer introduces broken feature edit (C0)
    (repo / "app.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    # 2. Run repair-start via CLI
    assert main(["repair-start", "--repo", str(repo), "--base", "HEAD"]) == 0
    start_out = capsys.readouterr().out
    assert "REPAIR_STATE: awaiting_approval" in start_out
    assert "NEXT_ACTION: approve_or_cancel" in start_out

    session_dir = None
    approval_request_path = None
    for line in start_out.splitlines():
        if line.startswith("REPAIR_SESSION: "):
            session_dir = Path(line.removeprefix("REPAIR_SESSION: "))
        elif line.startswith("REPAIR_REQUEST: "):
            approval_request_path = Path(line.removeprefix("REPAIR_REQUEST: "))

    assert session_dir is not None and session_dir.exists()
    assert approval_request_path is not None and approval_request_path.exists()
    req_doc = json.loads(approval_request_path.read_text(encoding="utf-8"))
    assert "math-check" in req_doc["failed_check_ids"]

    # 3. Approve repair via CLI
    approval_file = tmp_path / "approval.json"
    approval_file.write_text(
        json.dumps({"session_id": req_doc["session_id"]}), encoding="utf-8"
    )

    assert (
        main(
            [
                "repair-approve",
                "--session",
                str(session_dir),
                "--approval",
                str(approval_file),
            ]
        )
        == 0
    )
    approve_out = capsys.readouterr().out
    assert "REPAIR_STATE: repairing" in approve_out
    assert "NEXT_ACTION: edit_workspace" in approve_out

    # 4. Request workspace info via CLI
    assert main(["repair-request", "--session", str(session_dir)]) == 0
    req_out = capsys.readouterr().out
    workspace_path = None
    for line in req_out.splitlines():
        if line.startswith("WORKSPACE: "):
            workspace_path = Path(line.removeprefix("WORKSPACE: "))
    assert workspace_path is not None and workspace_path.exists()

    # Verify source worktree has NOT been touched
    assert (repo / "app.py").read_text(
        encoding="utf-8"
    ) == "def add(a, b):\n    return a - b\n"

    # 5. Fix bug in isolated workspace
    (workspace_path / "app.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )

    # 6. Evaluate repair via CLI
    assert main(["repair-evaluate", "--session", str(session_dir)]) == 0
    eval_out = capsys.readouterr().out
    assert "REPAIR_STATE: awaiting_final_approval" in eval_out
    assert "NEXT_ACTION: final_approval_and_apply" in eval_out

    # Read session to get candidate tree and patch digest
    session_json = json.loads(
        (session_dir / "repair-session-v1.json").read_text(encoding="utf-8")
    )
    c1_attempt = session_json["attempts"][1]
    assert c1_attempt["verdict"] == "PASS"

    # 7. Apply passing repair via CLI
    final_approval = FinalApproval(
        session_id=session_json["session_id"],
        final_candidate_tree=c1_attempt["candidate_tree"],
        final_patch_digest=c1_attempt["patch_digest"],
        approved_at="2026-08-21T21:40:00Z",
    )
    final_approval_file = tmp_path / "final_approval.json"
    final_approval_file.write_text(
        json.dumps(final_approval.to_dict()), encoding="utf-8"
    )

    assert (
        main(
            [
                "repair-apply",
                "--session",
                str(session_dir),
                "--approval",
                str(final_approval_file),
            ]
        )
        == 0
    )
    apply_out = capsys.readouterr().out
    assert "REPAIR_STATE: applied" in apply_out
    assert "NEXT_ACTION: none" in apply_out

    # 8. Verify source repo now contains the fix and passes release-gate run
    assert (repo / "app.py").read_text(
        encoding="utf-8"
    ) == "def add(a, b):\n    return a + b\n"
    assert main(["run", "--repo", str(repo), "--base", "HEAD"]) == 0
    run_out = capsys.readouterr().out
    assert "VERDICT: PASS" in run_out


def test_repair_integration_multi_attempt_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "app.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )

    assert main(["repair-start", "--repo", str(repo), "--base", "HEAD"]) == 0
    start_out = capsys.readouterr().out
    session_dir = next(
        Path(line.removeprefix("REPAIR_SESSION: "))
        for line in start_out.splitlines()
        if line.startswith("REPAIR_SESSION: ")
    )
    approval_request = next(
        Path(line.removeprefix("REPAIR_REQUEST: "))
        for line in start_out.splitlines()
        if line.startswith("REPAIR_REQUEST: ")
    )
    session_id = json.loads(approval_request.read_text(encoding="utf-8"))["session_id"]

    approval_file = tmp_path / "approval.json"
    approval_file.write_text(json.dumps({"session_id": session_id}), encoding="utf-8")
    assert (
        main(
            [
                "repair-approve",
                "--session",
                str(session_dir),
                "--approval",
                str(approval_file),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["repair-request", "--session", str(session_dir)]) == 0
    request_out = capsys.readouterr().out
    workspace = next(
        Path(line.removeprefix("WORKSPACE: "))
        for line in request_out.splitlines()
        if line.startswith("WORKSPACE: ")
    )

    # C1 is still eligible for repair but does not pass.
    (workspace / "app.py").write_text(
        "def add(a, b):\n    return a * b\n", encoding="utf-8"
    )
    assert main(["repair-evaluate", "--session", str(session_dir)]) == 0
    first_eval = capsys.readouterr().out
    assert "REPAIR_STATE: repairing" in first_eval
    assert "NEXT_ACTION: edit_workspace" in first_eval

    # C2 fixes the same failure within the controller's two-repair budget.
    assert main(["repair-request", "--session", str(session_dir)]) == 0
    request_out = capsys.readouterr().out
    workspace = next(
        Path(line.removeprefix("WORKSPACE: "))
        for line in request_out.splitlines()
        if line.startswith("WORKSPACE: ")
    )
    (workspace / "app.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    assert main(["repair-evaluate", "--session", str(session_dir)]) == 0
    second_eval = capsys.readouterr().out
    assert "REPAIR_STATE: awaiting_final_approval" in second_eval
    assert "NEXT_ACTION: final_approval_and_apply" in second_eval

    session = json.loads(
        (session_dir / "repair-session-v1.json").read_text(encoding="utf-8")
    )
    assert [attempt["candidate_label"] for attempt in session["attempts"]] == [
        "C0",
        "C1",
        "C2",
    ]
    assert session["attempts"][1]["verdict"] == "FAIL"
    assert session["attempts"][2]["verdict"] == "PASS"
    assert (session_dir / "C1.patch").exists()
    assert (session_dir / "C2.patch").exists()
    assert (repo / "app.py").read_text(encoding="utf-8") == (
        "def add(a, b):\n    return a - b\n"
    )

    final_approval = FinalApproval(
        session_id=session["session_id"],
        final_candidate_tree=session["attempts"][2]["candidate_tree"],
        final_patch_digest=session["attempts"][2]["patch_digest"],
        approved_at="2026-08-21T22:10:00Z",
    )
    final_approval_file = tmp_path / "final_approval.json"
    final_approval_file.write_text(
        json.dumps(final_approval.to_dict()), encoding="utf-8"
    )
    assert (
        main(
            [
                "repair-apply",
                "--session",
                str(session_dir),
                "--approval",
                str(final_approval_file),
            ]
        )
        == 0
    )
    apply_out = capsys.readouterr().out
    assert "REPAIR_STATE: applied" in apply_out
    assert "NEXT_ACTION: none" in apply_out
    assert (repo / "app.py").read_text(encoding="utf-8") == (
        "def add(a, b):\n    return a + b\n"
    )
    assert main(["run", "--repo", str(repo), "--base", "HEAD"]) == 0
    assert "VERDICT: PASS" in capsys.readouterr().out


def test_repair_integration_repeated_candidate_stops_without_retry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "app.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )

    assert main(["repair-start", "--repo", str(repo), "--base", "HEAD"]) == 0
    start_out = capsys.readouterr().out
    session_dir = next(
        Path(line.removeprefix("REPAIR_SESSION: "))
        for line in start_out.splitlines()
        if line.startswith("REPAIR_SESSION: ")
    )
    approval_request = next(
        Path(line.removeprefix("REPAIR_REQUEST: "))
        for line in start_out.splitlines()
        if line.startswith("REPAIR_REQUEST: ")
    )
    session_id = json.loads(approval_request.read_text(encoding="utf-8"))["session_id"]
    approval_file = tmp_path / "approval.json"
    approval_file.write_text(json.dumps({"session_id": session_id}), encoding="utf-8")
    assert (
        main(
            [
                "repair-approve",
                "--session",
                str(session_dir),
                "--approval",
                str(approval_file),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["repair-request", "--session", str(session_dir)]) == 0
    request_out = capsys.readouterr().out
    workspace = next(
        Path(line.removeprefix("WORKSPACE: "))
        for line in request_out.splitlines()
        if line.startswith("WORKSPACE: ")
    )
    (workspace / "app.py").write_text(
        "def add(a, b):\n    return a * b\n", encoding="utf-8"
    )
    assert main(["repair-evaluate", "--session", str(session_dir)]) == 0
    first_eval = capsys.readouterr().out
    assert "REPAIR_STATE: repairing" in first_eval
    assert "NEXT_ACTION: edit_workspace" in first_eval

    assert main(["repair-request", "--session", str(session_dir)]) == 0
    capsys.readouterr()
    assert main(["repair-evaluate", "--session", str(session_dir)]) == 0
    repeated_eval = capsys.readouterr().out
    assert "REPAIR_STATE: stopped" in repeated_eval
    assert "NEXT_ACTION: none" in repeated_eval

    session = json.loads(
        (session_dir / "repair-session-v1.json").read_text(encoding="utf-8")
    )
    assert session["stop_reason"] == "repeated_candidate"
    assert [attempt["candidate_label"] for attempt in session["attempts"]] == [
        "C0",
        "C1",
    ]
    assert not (session_dir / "C2.patch").exists()
    assert (repo / "app.py").read_text(encoding="utf-8") == (
        "def add(a, b):\n    return a - b\n"
    )


def test_repair_integration_needs_human_stops_without_retry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    # Ineligible candidate change: modifying .release-gate.yaml (policy file changed)
    (repo / ".release-gate.yaml").write_text(
        "version: 1\nscope:\n  allowed_paths: ['**']\nprepare: []\nchecks: []\n",
        encoding="utf-8",
    )

    assert main(["repair-start", "--repo", str(repo), "--base", "HEAD"]) == 0
    start_out = capsys.readouterr().out
    assert "REPAIR_STATE: stopped" in start_out
    assert "NEXT_ACTION: none" in start_out
    assert "REPAIR_REQUEST:" not in start_out
