"""
Deterministic hidden-oracle grading.

This module deliberately contains no LLM call.

The online AI may propose a solution.

The offline grader determines whether that solution actually satisfies the
known benchmark oracle.

This independence is one of the strongest protections against correlated
LLM blind spots.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .errors import GradingError
from .models import HiddenOracle, OracleOutcome, OracleType


class OracleGrade:
    """Simple internal grading result."""

    def __init__(
        self,
        outcome: OracleOutcome,
        notes: tuple[str, ...],
    ) -> None:
        self.outcome = outcome
        self.notes = notes


class DeterministicOracleGrader:
    """
    Execute the hidden oracle against a candidate workspace.

    IMPORTANT SECURITY NOTE

    Oracle commands execute code.

    In production they must run inside a disposable isolated container with:

        no production credentials
        no host filesystem access
        restricted networking
        bounded CPU/memory
        execution timeout

    The Python implementation below assumes its workspace is already inside
    such an evaluation container.
    """

    def grade(
        self,
        *,
        workspace: Path,
        oracle: HiddenOracle,
    ) -> OracleGrade:
        workspace = workspace.resolve()

        if not workspace.is_dir():
            raise GradingError(
                f"Candidate workspace does not exist: {workspace}"
            )

        notes: list[str] = []
        success = True

        if oracle.oracle_type in {
            OracleType.COMMAND,
            OracleType.COMPOSITE,
        }:
            command_success, command_note = self._grade_command(
                workspace=workspace,
                oracle=oracle,
            )
            success = success and command_success
            notes.append(command_note)

        if oracle.oracle_type in {
            OracleType.FILE_SHA256,
            OracleType.COMPOSITE,
        }:
            file_success, file_notes = self._grade_files(
                workspace=workspace,
                oracle=oracle,
            )
            success = success and file_success
            notes.extend(file_notes)

        return OracleGrade(
            outcome=(
                OracleOutcome.CORRECT
                if success
                else OracleOutcome.INCORRECT
            ),
            notes=tuple(notes),
        )

    @staticmethod
    def _grade_command(
        *,
        workspace: Path,
        oracle: HiddenOracle,
    ) -> tuple[bool, str]:
        try:
            completed = subprocess.run(
                oracle.command,
                cwd=workspace,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=oracle.timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return (
                False,
                f"Oracle command exceeded {oracle.timeout_seconds} seconds.",
            )
        except OSError as exc:
            raise GradingError(
                f"Unable to execute oracle command: {exc}"
            ) from exc

        success = completed.returncode == oracle.expected_exit_code

        return (
            success,
            "Oracle command returned "
            f"{completed.returncode}; expected "
            f"{oracle.expected_exit_code}.",
        )

    @staticmethod
    def _grade_files(
        *,
        workspace: Path,
        oracle: HiddenOracle,
    ) -> tuple[bool, list[str]]:
        success = True
        notes: list[str] = []

        for expected in oracle.expected_files:
            candidate = (workspace / expected.relative_path).resolve()

            try:
                candidate.relative_to(workspace)
            except ValueError:
                raise GradingError(
                    "Oracle expected-file path escaped workspace."
                )

            if not candidate.is_file():
                success = False
                notes.append(
                    f"Expected file missing: {expected.relative_path}"
                )
                continue

            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()

            if digest != expected.sha256:
                success = False
                notes.append(
                    f"Digest mismatch: {expected.relative_path}"
                )
            else:
                notes.append(
                    f"Digest verified: {expected.relative_path}"
                )

        return success, notes
