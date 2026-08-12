"""
Benchmark construction and validation.

This POC deliberately does not ask an LLM to manufacture a benchmark and then
immediately declare that benchmark to be ground truth.

AI-generated benchmark candidates can be useful.

They are not automatically validated golden cases.

The BenchmarkFactory therefore validates benchmark definitions and oracle
integrity before producing a ValidatedGoldenBenchmark.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from .errors import BenchmarkValidationError, OracleIntegrityError
from .models import (
    BenchmarkCase,
    HiddenOracle,
    ValidatedGoldenBenchmark,
)

import hashlib


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class BenchmarkFactory:
    """
    Build a validated benchmark from explicit benchmark-case definitions.

    For the POC, task payloads and hidden oracles use local file:// URIs.

    Azure Blob access should later be introduced behind a repository abstraction
    rather than spreading Azure SDK calls throughout the evaluation code.
    """

    FACTORY_VERSION = "0.1.0"

    def load_and_validate(
        self,
        *,
        benchmark_id: str,
        benchmark_version: str,
        cases_path: Path,
    ) -> ValidatedGoldenBenchmark:
        try:
            raw = json.loads(cases_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise BenchmarkValidationError(
                f"Unable to load benchmark cases from {cases_path}: {exc}"
            ) from exc

        if not isinstance(raw, list):
            raise BenchmarkValidationError(
                "Benchmark case file must contain a JSON list."
            )

        try:
            cases = tuple(
                BenchmarkCase.model_validate(item)
                for item in raw
            )
        except Exception as exc:
            raise BenchmarkValidationError(
                f"Benchmark case schema validation failed: {exc}"
            ) from exc

        notes: list[str] = []

        for case in cases:
            self._validate_case(case)
            notes.append(
                f"{case.case_id}: task and oracle integrity validated."
            )

        return ValidatedGoldenBenchmark(
            benchmark_id=benchmark_id,
            benchmark_version=benchmark_version,
            created_at=datetime.now(timezone.utc),
            cases=cases,
            validated=True,
            validation_notes=tuple(notes),
        )

    def load_oracle(self, case: BenchmarkCase) -> HiddenOracle:
        content = self._read_file_uri(case.oracle_uri)

        calculated = sha256_bytes(content)

        if calculated != case.oracle_sha256:
            raise OracleIntegrityError(
                f"Oracle digest mismatch for case {case.case_id!r}. "
                f"Expected {case.oracle_sha256}; calculated {calculated}."
            )

        try:
            return HiddenOracle.model_validate_json(content)
        except Exception as exc:
            raise OracleIntegrityError(
                f"Hidden oracle for case {case.case_id!r} is invalid: {exc}"
            ) from exc

    def _validate_case(self, case: BenchmarkCase) -> None:
        task_content = self._read_file_uri(case.task_payload_uri)

        if not task_content:
            raise BenchmarkValidationError(
                f"Task payload for {case.case_id!r} is empty."
            )

        oracle = self.load_oracle(case)

        # This is intentionally modest validation.
        #
        # A later BenchmarkQualificationService can perform stronger checks:
        #
        #   * verify defect exists before repair;
        #   * verify gold patch solves defect;
        #   * verify tests are neither trivial nor impossible;
        #   * inspect task ambiguity;
        #   * estimate task difficulty;
        #   * detect duplicate benchmark cases.
        #
        # Those are substantive benchmark-quality operations rather than simple
        # schema validation and should not be pretended to exist in this POC.

        if not oracle.oracle_id:
            raise BenchmarkValidationError(
                f"Case {case.case_id!r} has no oracle identity."
            )

    @staticmethod
    def _read_file_uri(uri: str) -> bytes:
        parsed = urlparse(uri)

        if parsed.scheme != "file":
            raise BenchmarkValidationError(
                "Component 5 POC currently accepts file:// benchmark "
                f"artifacts only. Received {uri!r}."
            )

        path = Path(unquote(parsed.path))

        try:
            return path.read_bytes()
        except OSError as exc:
            raise BenchmarkValidationError(
                f"Unable to read benchmark artifact {uri!r}: {exc}"
            ) from exc
