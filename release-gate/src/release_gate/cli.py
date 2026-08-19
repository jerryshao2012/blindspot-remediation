"""Command-line entry point for the standalone release gate."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from release_gate.config import ConfigError, load_config
from release_gate.engine import GateInputError, run_gate

_POLICY_NAME = ".release-gate.yaml"
_EVIDENCE_IGNORE = "/.release-gate/runs/"
_INITIAL_POLICY = """\
version: 1

scope:
  allowed_paths:
    - "**"
  forbidden_paths: []
  review_required_paths:
    - "/.release-gate.yaml"

prepare: []

checks:
  - id: configure-me
    mode: candidate
    severity: advisory
    argv: ["release-gate-configure-me"]
"""


class _UsageError(ValueError):
    pass


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _UsageError(message)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and return a stable release-gate exit code."""

    parser = _build_parser()
    try:
        arguments = parser.parse_args(argv)
        if arguments.command == "init":
            return _init(Path(arguments.repo))
        if arguments.command == "validate":
            return _validate(Path(arguments.repo))
        if arguments.command == "run":
            outcome = run_gate(
                Path(arguments.repo),
                base=arguments.base,
                output=Path(arguments.output) if arguments.output else None,
                run_id=arguments.run_id,
            )
            print(f"VERDICT: {outcome.verdict.value}")
            print(f"RESULT: {outcome.result_path}")
            return outcome.exit_code
        raise _UsageError("a command is required")
    except _UsageError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 3
    except ConfigError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 3
    except GateInputError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 3
    except Exception as error:
        print(f"ERROR: internal release-gate failure: {error}", file=sys.stderr)
        return 4


def _build_parser() -> _ArgumentParser:
    parser = _ArgumentParser(prog="release-gate")
    commands = parser.add_subparsers(dest="command")
    for name in ("init", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--repo", default=".", metavar="PATH")
    run = commands.add_parser("run")
    run.add_argument("--repo", default=".", metavar="PATH")
    run.add_argument("--base", default="HEAD", metavar="REF")
    run.add_argument("--output", metavar="PATH")
    run.add_argument("--run-id", metavar="ID")
    return parser


def _repository(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ConfigError(f"{path}: repository path does not exist") from error
    if not resolved.is_dir():
        raise ConfigError(f"{resolved}: repository path is not a directory")
    return resolved


def _init(path: Path) -> int:
    repository = _repository(path)
    policy = repository / _POLICY_NAME
    try:
        with policy.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(_INITIAL_POLICY)
    except FileExistsError as error:
        raise ConfigError(
            f"{policy}: policy already exists; refusing to overwrite"
        ) from error
    except OSError as error:
        raise ConfigError(
            f"{policy}: unable to create policy: {error.strerror}"
        ) from error

    try:
        _ensure_evidence_is_ignored(repository / ".gitignore")
        load_config(policy)
    except Exception:
        policy.unlink(missing_ok=True)
        raise
    print(f"INITIALIZED: {policy}")
    return 0


def _ensure_evidence_is_ignored(path: Path) -> None:
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as error:
        raise ConfigError(f"{path}: unable to read Git ignore file") from error
    if _EVIDENCE_IGNORE in existing.splitlines():
        return
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    try:
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{prefix}{_EVIDENCE_IGNORE}\n")
    except OSError as error:
        raise ConfigError(f"{path}: unable to update Git ignore file") from error


def _validate(path: Path) -> int:
    policy = _repository(path) / _POLICY_NAME
    load_config(policy)
    print(f"VALID: {policy}")
    return 0
