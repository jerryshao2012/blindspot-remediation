"""
Hidden-oracle interfaces and deterministic implementation for X1.

SECURITY / ASSURANCE BOUNDARY
-----------------------------

Only Component 5 should receive HiddenOraclePort.

Do NOT inject this dependency into:

    ChangeExecutionService
    EvidencePlanner
    EvidenceDiversityMapper
    ReleaseGateService
    WorkflowIntegration

The strongest version of this separation eventually uses infrastructure
controls:

    separate credentials
    separate artifact location
    separate execution mount
    explicit network/storage policy

rather than relying only on Python module boundaries.

B5 establishes the software contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from hashlib import sha256

from .contracts import (
    BenchmarkCase,
    OracleAcceptability,
    OracleAssessment,
    PipelineCandidate,
)


class HiddenOraclePort(ABC):
    """
    Authoritative hidden evaluation boundary.
    """

    @abstractmethod
    def assess(
        self,
        *,
        benchmark_case: BenchmarkCase,
        candidate: PipelineCandidate,
    ) -> OracleAssessment:
        """
        Evaluate one exact candidate against hidden benchmark criteria.

        Implementations must verify candidate identity where relevant.

        This method must not mutate the candidate.
        """
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class HiddenX1Definition:
    """
    Hidden definition for one synthetic X1 benchmark case.

    The online pipeline never receives this object.

    `required_fragment` and `forbidden_fragments` are intentionally simple
    because B5's first benchmark validates the campaign machinery.

    A mature benchmark should normally evaluate behavior through hidden
    executable tests/properties rather than relying primarily on text
    matching.
    """

    case_id: str
    required_fragment: str
    forbidden_fragments: tuple[str, ...]
    oracle_version: str = "x1-hidden-oracle-1.0.0"


class DeterministicHiddenX1Oracle(
    HiddenOraclePort
):
    """
    Deterministic hidden oracle for the first synthetic X1 campaign.

    This implementation is intentionally transparent in source code for the
    purposes of demonstrating the architecture.

    In a genuine qualification environment, the ONLINE pipeline must not have
    filesystem or credential access to hidden oracle definitions.

    The important B5 contract is therefore:

        campaign runner has oracle
        online pipeline does not.
    """

    def __init__(
        self,
        *,
        definitions: tuple[HiddenX1Definition, ...],
    ) -> None:
        if not definitions:
            raise ValueError(
                "At least one hidden oracle definition is required."
            )

        self._definitions = {
            definition.case_id: definition
            for definition in definitions
        }

        if len(self._definitions) != len(definitions):
            raise ValueError(
                "Duplicate hidden oracle case IDs are not permitted."
            )

    def assess(
        self,
        *,
        benchmark_case: BenchmarkCase,
        candidate: PipelineCandidate,
    ) -> OracleAssessment:

        case_id = benchmark_case.public_task.case_id

        try:
            definition = self._definitions[case_id]
        except KeyError as exc:
            return OracleAssessment(
                case_id=case_id,
                candidate_id=candidate.candidate_id,
                candidate_sha256=candidate.candidate_sha256,
                acceptability=(
                    OracleAcceptability.ORACLE_ERROR
                ),
                passed_hidden_checks=0,
                failed_hidden_checks=0,
                reason_codes=(
                    "hidden_definition_missing",
                ),
                oracle_version="unknown",
            )

        actual_digest = sha256(
            candidate.content.encode("utf-8")
        ).hexdigest()

        if actual_digest != candidate.candidate_sha256:
            return OracleAssessment(
                case_id=case_id,
                candidate_id=candidate.candidate_id,
                candidate_sha256=candidate.candidate_sha256,
                acceptability=(
                    OracleAcceptability.ORACLE_ERROR
                ),
                passed_hidden_checks=0,
                failed_hidden_checks=0,
                reason_codes=(
                    "candidate_hash_mismatch",
                ),
                oracle_version=definition.oracle_version,
            )

        checks: list[tuple[str, bool]] = []

        checks.append(
            (
                "required_fragment_present",
                (
                    definition.required_fragment
                    in candidate.content
                ),
            )
        )

        for index, forbidden in enumerate(
            definition.forbidden_fragments
        ):
            checks.append(
                (
                    f"forbidden_fragment_absent:{index}",
                    forbidden not in candidate.content,
                )
            )

        passed = sum(
            1
            for _, result in checks
            if result
        )

        failed = len(checks) - passed

        failed_reasons = tuple(
            name
            for name, result in checks
            if not result
        )

        acceptability = (
            OracleAcceptability.ACCEPTABLE
            if failed == 0
            else OracleAcceptability.UNACCEPTABLE
        )

        return OracleAssessment(
            case_id=case_id,
            candidate_id=candidate.candidate_id,
            candidate_sha256=candidate.candidate_sha256,
            acceptability=acceptability,
            passed_hidden_checks=passed,
            failed_hidden_checks=failed,
            reason_codes=failed_reasons,
            oracle_version=definition.oracle_version,
        )

