"""Bounded direct-argv execution on the trusted host."""

from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

import psutil

from release_gate.models import ExitClasses, ResolvedCommand


class ExecutionClass(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class StreamEvidence:
    path: Path
    size: int
    original_size: int
    sha256: str
    full_sha256: str
    truncated: bool


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    classification: ExecutionClass
    reason_codes: tuple[str, ...]
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    stdout: StreamEvidence
    stderr: StreamEvidence
    environment_names: tuple[str, ...]


def classify_exit(
    exit_code: int, classes: ExitClasses
) -> tuple[ExecutionClass, tuple[str, ...]]:
    """Classify one normalized subprocess return code."""

    if exit_code < 0:
        return ExecutionClass.ERROR, ("COMMAND_SIGNALLED",)
    if exit_code in classes.passed:
        return ExecutionClass.PASS, ()
    if exit_code in classes.fail:
        return ExecutionClass.FAIL, ("COMMAND_FAILED",)
    if exit_code in classes.error:
        return ExecutionClass.ERROR, ("COMMAND_EXIT_ERROR",)
    return ExecutionClass.ERROR, ("COMMAND_EXIT_UNCLASSIFIED",)


def run_command(
    command: ResolvedCommand,
    *,
    workspace: Path,
    artifact_dir: Path,
    stream_limit: int,
    host_environment: dict[str, str] | None = None,
) -> ExecutionResult:
    """Execute a command without a shell and retain bounded stream prefixes."""

    if stream_limit < 1:
        raise ValueError("stream_limit must be positive")
    artifact_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stdout_path = artifact_dir / "stdout.log"
    stderr_path = artifact_dir / "stderr.log"
    _prepare_log(stdout_path)
    _prepare_log(stderr_path)
    started = time.monotonic_ns()
    host = dict(os.environ if host_environment is None else host_environment)

    with tempfile.TemporaryDirectory(
        prefix="release-gate-runtime-", dir=artifact_dir
    ) as runtime:
        runtime_root = Path(runtime)
        environment, missing = _build_environment(command, host, runtime_root)
        environment_names = tuple(sorted(environment))
        if missing:
            return _pre_spawn_error(
                started,
                stdout_path,
                stderr_path,
                environment_names,
                "INHERITED_ENVIRONMENT_MISSING",
            )
        cwd = _safe_cwd(workspace, command.cwd)
        if cwd is None:
            return _pre_spawn_error(
                started,
                stdout_path,
                stderr_path,
                environment_names,
                "COMMAND_SPAWN_FAILED",
            )

        creation_flags = 0
        if os.name == "nt":
            creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            process = subprocess.Popen(
                command.argv,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                creationflags=creation_flags,
                start_new_session=os.name != "nt",
            )
        except (OSError, ValueError):
            return _pre_spawn_error(
                started,
                stdout_path,
                stderr_path,
                environment_names,
                "COMMAND_SPAWN_FAILED",
            )

        assert process.stdout is not None
        assert process.stderr is not None
        captured: dict[str, StreamEvidence] = {}
        stdout_thread = threading.Thread(
            target=_drain,
            args=(process.stdout, stdout_path, stream_limit, captured, "stdout"),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=_drain,
            args=(process.stderr, stderr_path, stream_limit, captured, "stderr"),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        timed_out = False
        interrupted = False
        exit_code: int | None
        try:
            exit_code = process.wait(timeout=command.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_process_tree(process)
            exit_code = None
        except KeyboardInterrupt:
            interrupted = True
            _terminate_process_tree(process)
            exit_code = None
        else:
            _terminate_remaining_group(process)
        finally:
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
            if stdout_thread.is_alive() or stderr_thread.is_alive():
                _terminate_process_tree(process)
                stdout_thread.join(timeout=2)
                stderr_thread.join(timeout=2)

        stdout_evidence = captured.get("stdout") or _stream_evidence(stdout_path, b"")
        stderr_evidence = captured.get("stderr") or _stream_evidence(stderr_path, b"")
        duration_ms = _duration_ms(started)
        if timed_out:
            return ExecutionResult(
                classification=ExecutionClass.ERROR,
                reason_codes=("COMMAND_TIMED_OUT",),
                exit_code=None,
                timed_out=True,
                duration_ms=duration_ms,
                stdout=stdout_evidence,
                stderr=stderr_evidence,
                environment_names=environment_names,
            )
        if interrupted:
            return ExecutionResult(
                classification=ExecutionClass.ERROR,
                reason_codes=("OPERATOR_INTERRUPTED",),
                exit_code=None,
                timed_out=False,
                duration_ms=duration_ms,
                stdout=stdout_evidence,
                stderr=stderr_evidence,
                environment_names=environment_names,
            )
        assert exit_code is not None
        classification, reasons = classify_exit(exit_code, command.exit_classes)
        return ExecutionResult(
            classification=classification,
            reason_codes=reasons,
            exit_code=exit_code,
            timed_out=False,
            duration_ms=duration_ms,
            stdout=stdout_evidence,
            stderr=stderr_evidence,
            environment_names=environment_names,
        )


def _prepare_log(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
        path.touch(mode=0o600, exist_ok=False)
    except OSError as error:
        raise RuntimeError(f"unable to create stream evidence: {path}") from error


def _build_environment(
    command: ResolvedCommand, host: dict[str, str], runtime_root: Path
) -> tuple[dict[str, str], tuple[str, ...]]:
    missing = tuple(name for name in command.inherit_environment if name not in host)
    environment = {
        name: host[name] for name in command.inherit_environment if name in host
    }
    environment.update(command.environment)
    home = runtime_root / "home"
    temporary = runtime_root / "tmp"
    home.mkdir(mode=0o700)
    temporary.mkdir(mode=0o700)
    environment["HOME"] = str(home)
    if os.name == "nt":
        drive, tail = os.path.splitdrive(str(home))
        environment.update(
            {
                "USERPROFILE": str(home),
                "HOMEDRIVE": drive,
                "HOMEPATH": tail or os.sep,
                "TEMP": str(temporary),
                "TMP": str(temporary),
            }
        )
    else:
        environment["TMPDIR"] = str(temporary)
    return environment, missing


def _safe_cwd(workspace: Path, relative: str) -> Path | None:
    try:
        root = workspace.resolve(strict=True)
        cwd = (root / relative).resolve(strict=True)
        cwd.relative_to(root)
    except (OSError, ValueError):
        return None
    return cwd if cwd.is_dir() else None


def _pre_spawn_error(
    started: int,
    stdout_path: Path,
    stderr_path: Path,
    environment_names: tuple[str, ...],
    reason: str,
) -> ExecutionResult:
    return ExecutionResult(
        classification=ExecutionClass.ERROR,
        reason_codes=(reason,),
        exit_code=None,
        timed_out=False,
        duration_ms=_duration_ms(started),
        stdout=_stream_evidence(stdout_path, b""),
        stderr=_stream_evidence(stderr_path, b""),
        environment_names=environment_names,
    )


def _drain(
    pipe: BinaryIO,
    path: Path,
    limit: int,
    captured: dict[str, StreamEvidence],
    key: str,
) -> None:
    full_digest = hashlib.sha256()
    retained_digest = hashlib.sha256()
    original_size = 0
    retained_size = 0
    with path.open("wb") as stream:
        while True:
            chunk = pipe.read(64 * 1024)
            if not chunk:
                break
            full_digest.update(chunk)
            original_size += len(chunk)
            keep = chunk[: max(0, limit - retained_size)]
            if keep:
                stream.write(keep)
                retained_digest.update(keep)
                retained_size += len(keep)
    pipe.close()
    captured[key] = StreamEvidence(
        path=path,
        size=retained_size,
        original_size=original_size,
        sha256=retained_digest.hexdigest(),
        full_sha256=full_digest.hexdigest(),
        truncated=original_size > retained_size,
    )


def _stream_evidence(path: Path, content: bytes) -> StreamEvidence:
    digest = hashlib.sha256(content).hexdigest()
    return StreamEvidence(
        path=path,
        size=len(content),
        original_size=len(content),
        sha256=digest,
        full_sha256=digest,
        truncated=False,
    )


def _duration_ms(started: int) -> int:
    return max(0, (time.monotonic_ns() - started) // 1_000_000)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    try:
        parent = psutil.Process(process.pid)
        descendants = parent.children(recursive=True)
    except psutil.Error:
        descendants = []
    for child in descendants:
        try:
            child.terminate()
        except psutil.Error:
            pass
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except (OSError, ProcessLookupError):
        pass
    _, alive = psutil.wait_procs(descendants, timeout=1)
    for child in alive:
        try:
            child.kill()
        except psutil.Error:
            pass
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except (OSError, ProcessLookupError):
            pass
        process.wait(timeout=2)


def _terminate_remaining_group(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        return
