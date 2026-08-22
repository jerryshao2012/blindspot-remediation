"""Tests for repair controller state machine and session lifecycle."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from release_gate.git import _base_git_environment
from release_gate.repair.controller import (
    apply_repair,
    approve_repair,
    cancel_repair,
    evaluate_repair,
    request_repair,
    start_repair,
)
from release_gate.repair.models import (
    FinalApproval,
    RepairState,
    RepairStopReason,
)


def _init_failing_repo(path: Path) -> str:
    env = _base_git_environment()
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        env=env,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"], check=True, env=env
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
        env=env,
    )

    policy = """\
version: 1
scope:
  allowed_paths: ["**"]
  forbidden_paths: []
  review_required_paths: [".release-gate.yaml"]
prepare: []
checks:
  - id: unit-tests
    mode: candidate
    severity: blocking
    argv: ["python3", "test_calc.py"]
"""
    (path / ".release-gate.yaml").write_text(policy, encoding="utf-8")
    (path / ".gitignore").write_text("/.release-gate/runs/\n", encoding="utf-8")
    (path / "calc.py").write_text(
        "def multiply(a, b): return a * b\n", encoding="utf-8"
    )
    (path / "test_calc.py").write_text(
        "from calc import multiply\nassert multiply(2, 3) == 6\n", encoding="utf-8"
    )

    subprocess.run(["git", "-C", str(path), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "Initial"], check=True, env=env
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


def test_repair_lifecycle_from_start_to_apply(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_failing_repo(repo)

    # Introduce bug in calc.py
    (repo / "calc.py").write_text("def multiply(a, b): return a + b\n")

    # 1. Start repair
    outcome = start_repair(repo, base="HEAD")
    assert outcome.state is RepairState.AWAITING_APPROVAL
    assert outcome.next_action == "approve_or_cancel"
    assert outcome.session_dir.exists()

    # 2. Approve repair
    approval_doc = {"session_id": outcome.session_id, "approved": True}
    approval_file = tmp_path / "approval.json"
    approval_file.write_text(json.dumps(approval_doc))

    approved_outcome = approve_repair(outcome.session_dir, approval_file)
    assert approved_outcome.state is RepairState.REPAIRING
    assert approved_outcome.next_action == "edit_workspace"

    # 3. Request workspace info
    req_info = request_repair(outcome.session_dir)
    workspace_path = Path(req_info["workspace_path"])
    assert workspace_path.exists()
    assert (
        workspace_path / "calc.py"
    ).read_text() == "def multiply(a, b): return a + b\n"

    # 4. Perform fix in workspace
    (workspace_path / "calc.py").write_text("def multiply(a, b): return a * b\n")

    # 5. Evaluate repair candidate
    eval_outcome = evaluate_repair(outcome.session_dir)
    assert eval_outcome.state is RepairState.AWAITING_FINAL_APPROVAL
    assert eval_outcome.next_action == "final_approval_and_apply"
    assert len(eval_outcome.session.attempts) == 2  # C0 and C1
    assert eval_outcome.session.attempts[1].verdict == "PASS"

    # 6. Apply passing repair
    final_app = FinalApproval(
        session_id=outcome.session_id,
        final_candidate_tree=eval_outcome.session.attempts[1].candidate_tree,
        final_patch_digest=eval_outcome.session.attempts[1].patch_digest,
        approved_at="2026-08-21T21:35:00Z",
    )
    final_app_file = tmp_path / "final_approval.json"
    final_app_file.write_text(json.dumps(final_app.to_dict()))

    applied_outcome = apply_repair(outcome.session_dir, final_app_file)
    assert applied_outcome.state is RepairState.APPLIED
    assert applied_outcome.next_action == "none"

    # Verify source repo is fixed
    assert (repo / "calc.py").read_text() == "def multiply(a, b): return a * b\n"


def test_repair_budget_exhaustion(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_failing_repo(repo)

    (repo / "calc.py").write_text("def multiply(a, b): return a + b\n")

    outcome = start_repair(repo, base="HEAD")
    approval_file = tmp_path / "approval.json"
    approval_file.write_text(json.dumps({"session_id": outcome.session_id}))
    approve_repair(outcome.session_dir, approval_file)

    req_info = request_repair(outcome.session_dir)
    workspace_path = Path(req_info["workspace_path"])

    # Attempt 1 (C1): Still broken edit
    (workspace_path / "calc.py").write_text("def multiply(a, b): return a - b\n")
    eval1 = evaluate_repair(outcome.session_dir)
    assert eval1.state is RepairState.REPAIRING

    # Attempt 2 (C2): Still broken edit
    (workspace_path / "calc.py").write_text("def multiply(a, b): return a ^ b\n")
    eval2 = evaluate_repair(outcome.session_dir)
    assert eval2.state is RepairState.STOPPED
    assert eval2.session.stop_reason is RepairStopReason.ATTEMPT_BUDGET_EXHAUSTED
    assert eval2.next_action == "none"


def test_repair_start_already_pass_stops(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_failing_repo(repo)

    # Candidate in source already passes
    (repo / "calc.py").write_text("def multiply(a, b): return a * b\n# comment\n")
    outcome = start_repair(repo, base="HEAD")
    assert outcome.state is RepairState.STOPPED
    assert outcome.session.stop_reason is RepairStopReason.ALREADY_PASS
    assert outcome.next_action == "none"


def test_repair_cancel(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_failing_repo(repo)

    (repo / "calc.py").write_text("def multiply(a, b): return a + b\n")
    outcome = start_repair(repo, base="HEAD")
    cancelled = cancel_repair(outcome.session_dir)
    assert cancelled.state is RepairState.CANCELLED
    assert cancelled.session.stop_reason is RepairStopReason.CANCELLED_BY_USER
    assert cancelled.next_action == "none"
