from __future__ import annotations

import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path

import psutil
import pytest

from release_gate import process as process_module
from release_gate.models import ExitClasses, FrozenDict, ResolvedCommand
from release_gate.process import (
    ExecutionClass,
    _resolve_argv_for_cwd,
    classify_exit,
    run_command,
)


def command(
    code: str,
    *,
    timeout: int = 10,
    inherited: tuple[str, ...] = (),
    environment: dict[str, str] | None = None,
    exit_classes: ExitClasses | None = None,
) -> ResolvedCommand:
    return ResolvedCommand(
        argv=(sys.executable, "-c", code),
        cwd=".",
        timeout=timeout,
        inherit_environment=inherited,
        environment=FrozenDict(environment or {}),
        exit_classes=exit_classes or ExitClasses(),
    )


@pytest.mark.parametrize(
    ("exit_code", "expected", "reason"),
    [
        (0, ExecutionClass.PASS, ()),
        (1, ExecutionClass.FAIL, ("COMMAND_FAILED",)),
        (2, ExecutionClass.ERROR, ("COMMAND_EXIT_ERROR",)),
        (7, ExecutionClass.ERROR, ("COMMAND_EXIT_UNCLASSIFIED",)),
        (0xC0000005, ExecutionClass.ERROR, ("COMMAND_EXIT_ERROR",)),
        (-signal.SIGTERM, ExecutionClass.ERROR, ("COMMAND_SIGNALLED",)),
    ],
)
def test_classifies_every_process_result(
    exit_code: int,
    expected: ExecutionClass,
    reason: tuple[str, ...],
) -> None:
    classes = ExitClasses.model_validate(
        {"pass": [0], "fail": [1], "error": [2, 0xC0000005]}
    )
    assert classify_exit(exit_code, classes) == (expected, reason)


def test_runs_direct_argv_with_spaces_and_classifies_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace with spaces"
    workspace.mkdir()
    logs = tmp_path / "logs"
    spec = command(
        "import sys; print(sys.argv[1]); print('problem', file=sys.stderr); sys.exit(1)"
    )
    spec = spec.model_copy(update={"argv": (*spec.argv, "argument with spaces")})

    result = run_command(
        spec, workspace=workspace, artifact_dir=logs, stream_limit=1024
    )

    assert result.classification is ExecutionClass.FAIL
    assert result.exit_code == 1
    assert result.timed_out is False
    assert result.reason_codes == ("COMMAND_FAILED",)
    assert result.stdout.path.read_text() == "argument with spaces\n"
    assert result.stderr.path.read_text() == "problem\n"


def test_windows_resolves_workspace_relative_executable_before_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "isolated candidate"
    workspace.mkdir()
    argv = (
        ".release-gate-venv/Scripts/python.exe",
        "-m",
        "pytest",
    )
    monkeypatch.setattr(process_module.os, "name", "nt")

    resolved = _resolve_argv_for_cwd(argv, workspace)

    assert resolved == (
        str((workspace / argv[0]).resolve()),
        "-m",
        "pytest",
    )


def test_missing_executable_and_missing_inherited_environment_are_errors(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    missing_tool = ResolvedCommand(
        argv=("release-gate-definitely-missing",),
        cwd=".",
        timeout=10,
        environment=FrozenDict(),
        inherit_environment=(),
        exit_classes=ExitClasses(),
    )
    spawned = run_command(
        missing_tool,
        workspace=workspace,
        artifact_dir=tmp_path / "missing-tool",
        stream_limit=100,
    )
    assert spawned.classification is ExecutionClass.ERROR
    assert spawned.exit_code is None
    assert spawned.reason_codes == ("COMMAND_SPAWN_FAILED",)

    missing_env = command("print('never')", inherited=("MISSING_GATE_VARIABLE",))
    inherited = run_command(
        missing_env,
        workspace=workspace,
        artifact_dir=tmp_path / "missing-env",
        stream_limit=100,
        host_environment={},
    )
    assert inherited.classification is ExecutionClass.ERROR
    assert inherited.exit_code is None
    assert inherited.reason_codes == ("INHERITED_ENVIRONMENT_MISSING",)


def test_environment_is_closed_and_engine_home_wins(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    code = (
        "import json, os; "
        "print(json.dumps({k: os.environ.get(k) for k in "
        "['HOME','TMPDIR','ALLOWED','LITERAL','SECRET']}))"
    )
    spec = command(
        code,
        inherited=("ALLOWED", "LITERAL"),
        environment={"LITERAL": "configured"},
    )
    result = run_command(
        spec,
        workspace=workspace,
        artifact_dir=tmp_path / "logs",
        stream_limit=4096,
        host_environment={
            "ALLOWED": "inherited",
            "LITERAL": "host",
            "SECRET": "must-not-pass",
        },
    )
    values = json.loads(result.stdout.path.read_text())

    assert values["ALLOWED"] == "inherited"
    assert values["LITERAL"] == "configured"
    assert values["SECRET"] is None
    assert values["HOME"]
    assert values["TMPDIR"]
    assert not Path(values["HOME"]).exists()
    assert result.environment_names == ("ALLOWED", "HOME", "LITERAL", "TMPDIR")


def test_streams_are_drained_hashed_and_retained_to_limit(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    stdout = b"a" * 4097
    stderr = b"b" * 4099
    code = f"import os; os.write(1, {stdout!r}); os.write(2, {stderr!r})"

    result = run_command(
        command(code),
        workspace=workspace,
        artifact_dir=tmp_path / "logs",
        stream_limit=1024,
    )

    assert result.classification is ExecutionClass.PASS
    assert result.stdout.path.read_bytes() == stdout[:1024]
    assert result.stdout.original_size == len(stdout)
    assert result.stdout.truncated is True
    assert result.stdout.full_sha256 == hashlib.sha256(stdout).hexdigest()
    assert result.stderr.path.read_bytes() == stderr[:1024]
    assert result.stderr.original_size == len(stderr)
    assert result.stderr.full_sha256 == hashlib.sha256(stderr).hexdigest()


@pytest.mark.skipif(os.name == "nt", reason="POSIX signal semantics")
def test_signal_is_an_infrastructure_error(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = run_command(
        command("import os, signal; os.kill(os.getpid(), signal.SIGTERM)"),
        workspace=workspace,
        artifact_dir=tmp_path / "logs",
        stream_limit=100,
    )

    assert result.classification is ExecutionClass.ERROR
    assert result.exit_code == -signal.SIGTERM
    assert result.timed_out is False
    assert result.reason_codes == ("COMMAND_SIGNALLED",)


@pytest.mark.skipif(os.name == "nt", reason="POSIX helper uses SIGTERM")
def test_timeout_kills_descendant_process_tree(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    code = (
        "import subprocess, sys, time; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        "print(child.pid, flush=True); time.sleep(60)"
    )
    started = time.monotonic()
    result = run_command(
        command(code, timeout=1),
        workspace=workspace,
        artifact_dir=tmp_path / "logs",
        stream_limit=100,
    )

    assert time.monotonic() - started < 8
    assert result.classification is ExecutionClass.ERROR
    assert result.exit_code is None
    assert result.timed_out is True
    assert result.reason_codes == ("COMMAND_TIMED_OUT",)
    child_pid = int(result.stdout.path.read_text().strip())
    for _ in range(30):
        if not psutil.pid_exists(child_pid):
            break
        time.sleep(0.05)
    assert not psutil.pid_exists(child_pid)


def test_rejects_cwd_that_resolves_outside_clone(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "escape").symlink_to(outside, target_is_directory=True)
    spec = command("print('never')").model_copy(update={"cwd": "escape"})

    result = run_command(
        spec,
        workspace=workspace,
        artifact_dir=tmp_path / "logs",
        stream_limit=100,
    )

    assert result.classification is ExecutionClass.ERROR
    assert result.reason_codes == ("COMMAND_SPAWN_FAILED",)
    assert result.exit_code is None
