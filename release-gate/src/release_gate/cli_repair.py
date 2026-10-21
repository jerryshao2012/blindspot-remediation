"""CLI handlers for the bounded repair protocol."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

from release_gate.repair.controller import (
    apply_repair,
    approve_repair,
    cancel_repair,
    evaluate_repair,
    finalize_repair,
    request_repair,
    start_repair,
)
from release_gate.repair.workspace import RepairWorkspaceError


def handle_repair(arguments: Namespace) -> int:
    """Run one repair protocol command and preserve its CLI output contract."""
    try:
        if arguments.command == "repair-start":
            outcome = start_repair(
                Path(arguments.repo),
                base=arguments.base,
                output=Path(arguments.output) if arguments.output else None,
                session_id=arguments.session_id,
            )
            print(f"REPAIR_SESSION: {outcome.session_dir.absolute()}")
            print(f"REPAIR_STATE: {outcome.state.value}")
            print(f"NEXT_ACTION: {outcome.next_action}")
            if outcome.approval_request_path and outcome.approval_request_path.exists():
                print(f"REPAIR_REQUEST: {outcome.approval_request_path.absolute()}")
            if outcome.summary_path and outcome.summary_path.exists():
                print(f"REPAIR_SUMMARY: {outcome.summary_path.absolute()}")
            return 0
        if arguments.command == "repair-approve":
            outcome = approve_repair(
                Path(arguments.session),
                Path(arguments.approval),
            )
            _print_outcome(outcome)
            return 0
        if arguments.command == "repair-request":
            info = request_repair(Path(arguments.session))
            print(f"REPAIR_SESSION: {Path(arguments.session).absolute()}")
            print(f"REPAIR_STATE: {info['state']}")
            print(f"NEXT_ACTION: {info['next_action']}")
            print(f"WORKSPACE: {info['workspace_path']}")
            print(f"APPROVED_PATHS: {', '.join(info['approved_paths'])}")
            print(f"FAILED_CHECKS: {', '.join(info['failed_check_ids'])}")
            if info.get("guidance"):
                print(f"GUIDANCE: {info['guidance']}")
            return 0
        if arguments.command == "repair-evaluate":
            outcome = evaluate_repair(Path(arguments.session))
            _print_outcome(outcome)
            return 0
        if arguments.command == "repair-finalize":
            outcome = finalize_repair(Path(arguments.session))
            _print_outcome(outcome)
            return 0
        if arguments.command == "repair-apply":
            outcome = apply_repair(
                Path(arguments.session),
                Path(arguments.approval),
            )
            _print_outcome(outcome)
            return 0
        if arguments.command == "repair-cancel":
            outcome = cancel_repair(Path(arguments.session))
            _print_outcome(outcome)
            return 0
    except (ValueError, FileNotFoundError, RepairWorkspaceError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 3
    return 3


def _print_outcome(outcome: Any) -> None:
    print(f"REPAIR_SESSION: {outcome.session_dir.absolute()}")
    print(f"REPAIR_STATE: {outcome.state.value}")
    print(f"NEXT_ACTION: {outcome.next_action}")
    if outcome.summary_path and outcome.summary_path.exists():
        print(f"REPAIR_SUMMARY: {outcome.summary_path.absolute()}")
