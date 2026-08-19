"""Pure scope, check, and three-way verdict policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pathspec import PathSpec

from release_gate.assertions import AssertionOutcome, AssertionState
from release_gate.models import Check, CheckMode, Scope, Severity
from release_gate.process import ExecutionClass, ExecutionResult


class Verdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_HUMAN = "NEEDS_HUMAN"


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class ScopeOutcome:
    verdict: Verdict
    changed_paths: tuple[str, ...]
    outside_allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    review_required_paths: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    id: str
    mode: CheckMode
    severity: Severity
    status: CheckStatus
    reason_codes: tuple[str, ...]
    assertions: tuple[AssertionOutcome, ...]


@dataclass(frozen=True, slots=True)
class GateDecision:
    verdict: Verdict
    reason_codes: tuple[str, ...]


def evaluate_scope(scope: Scope, changed_paths: tuple[str, ...]) -> ScopeOutcome:
    """Classify every changed path with Git-wildmatch semantics."""

    changed = tuple(dict.fromkeys(changed_paths))
    allowed_spec = PathSpec.from_lines("gitwildmatch", scope.allowed_paths)
    forbidden_spec = PathSpec.from_lines("gitwildmatch", scope.forbidden_paths)
    review_spec = PathSpec.from_lines("gitwildmatch", scope.review_required_paths)
    outside = tuple(path for path in changed if not allowed_spec.match_file(path))
    forbidden = tuple(path for path in changed if forbidden_spec.match_file(path))
    review = tuple(path for path in changed if review_spec.match_file(path))
    reasons: list[str] = []
    if forbidden:
        reasons.append("PATH_FORBIDDEN")
    if outside:
        reasons.append("PATH_OUTSIDE_ALLOWED")
    if review:
        reasons.append("PATH_REVIEW_REQUIRED")
    if review:
        verdict = Verdict.NEEDS_HUMAN
    elif outside or forbidden:
        verdict = Verdict.FAIL
    else:
        verdict = Verdict.PASS
    return ScopeOutcome(
        verdict=verdict,
        changed_paths=changed,
        outside_allowed_paths=outside,
        forbidden_paths=forbidden,
        review_required_paths=review,
        reason_codes=tuple(sorted(reasons)),
    )


def combine_check(
    check: Check,
    *,
    candidate: ExecutionResult,
    baseline: ExecutionResult | None = None,
    assertions: tuple[AssertionOutcome, ...] = (),
    diagnostics: tuple[str, ...] = (),
) -> CheckOutcome:
    """Combine process, report, and assertion outcomes for one check."""

    status, reasons = _execution_status(check, baseline, candidate)
    assertion_reasons = {
        reason for outcome in assertions for reason in outcome.reason_codes
    }
    if any(outcome.state is AssertionState.ERROR for outcome in assertions):
        status = CheckStatus.ERROR
    elif status is not CheckStatus.ERROR and any(
        outcome.state is AssertionState.FAIL for outcome in assertions
    ):
        status = CheckStatus.FAIL
    reasons.update(assertion_reasons)
    reasons.update(diagnostics)
    if status is CheckStatus.PASS:
        reasons.intersection_update({"OPTIONAL_REPORT_MISSING", "STREAM_TRUNCATED"})
    return CheckOutcome(
        id=check.id,
        mode=check.mode,
        severity=check.severity,
        status=status,
        reason_codes=tuple(sorted(reasons)),
        assertions=assertions,
    )


def skipped_check(check: Check, reasons: tuple[str, ...]) -> CheckOutcome:
    """Retain a configured check that a scheduling stop prevented."""

    if not reasons:
        reasons = ("REQUIRED_CONTROL_SKIPPED",)
    return CheckOutcome(
        id=check.id,
        mode=check.mode,
        severity=check.severity,
        status=CheckStatus.SKIPPED,
        reason_codes=tuple(sorted(set(reasons))),
        assertions=(),
    )


def aggregate_verdict(
    scope: ScopeOutcome,
    checks: tuple[CheckOutcome, ...],
    *,
    run_reasons: tuple[str, ...] = (),
) -> GateDecision:
    """Aggregate with the invariant ``NEEDS_HUMAN > FAIL > PASS`` order."""

    needs_human = scope.verdict is Verdict.NEEDS_HUMAN
    failed = scope.verdict is Verdict.FAIL
    contributing = set(scope.reason_codes)
    contributing.update(run_reasons)
    if run_reasons:
        needs_human = True
    for outcome in checks:
        if outcome.status in (CheckStatus.ERROR, CheckStatus.SKIPPED):
            needs_human = True
            contributing.update(_verdict_reasons(outcome.reason_codes))
        elif outcome.status is CheckStatus.FAIL:
            if outcome.severity is Severity.ADVISORY:
                needs_human = True
                contributing.update(_verdict_reasons(outcome.reason_codes))
            elif outcome.severity is Severity.BLOCKING:
                failed = True
                contributing.update(_verdict_reasons(outcome.reason_codes))
    if needs_human:
        verdict = Verdict.NEEDS_HUMAN
    elif failed:
        verdict = Verdict.FAIL
    else:
        verdict = Verdict.PASS
        contributing.clear()
    return GateDecision(verdict=verdict, reason_codes=tuple(sorted(contributing)))


def preflight_reasons(policy_changed: bool, launcher_changed: bool) -> tuple[str, ...]:
    reasons: list[str] = []
    if launcher_changed:
        reasons.append("CONTROL_LAUNCHER_REVIEW")
    if policy_changed:
        reasons.append("POLICY_FILE_CHANGED")
    return tuple(sorted(reasons))


def _execution_status(
    check: Check,
    baseline: ExecutionResult | None,
    candidate: ExecutionResult,
) -> tuple[CheckStatus, set[str]]:
    if check.mode is CheckMode.CANDIDATE:
        return _status_from_execution(candidate), set(candidate.reason_codes)
    if baseline is None:
        return CheckStatus.ERROR, {"REQUIRED_CONTROL_SKIPPED"}
    if (
        baseline.classification is ExecutionClass.ERROR
        or candidate.classification is ExecutionClass.ERROR
    ):
        reasons = {
            *(
                baseline.reason_codes
                if baseline.classification is ExecutionClass.ERROR
                else ()
            ),
            *(
                candidate.reason_codes
                if candidate.classification is ExecutionClass.ERROR
                else ()
            ),
        }
        return CheckStatus.ERROR, reasons
    regressed = (
        baseline.classification is ExecutionClass.PASS
        and candidate.classification is ExecutionClass.FAIL
    )
    if regressed:
        return CheckStatus.FAIL, set(candidate.reason_codes or ("COMMAND_FAILED",))
    diagnostics = {
        reason
        for reason in (*baseline.reason_codes, *candidate.reason_codes)
        if reason in {"OPTIONAL_REPORT_MISSING", "STREAM_TRUNCATED"}
    }
    return CheckStatus.PASS, diagnostics


def _status_from_execution(execution: ExecutionResult) -> CheckStatus:
    return {
        ExecutionClass.PASS: CheckStatus.PASS,
        ExecutionClass.FAIL: CheckStatus.FAIL,
        ExecutionClass.ERROR: CheckStatus.ERROR,
        ExecutionClass.SKIPPED: CheckStatus.SKIPPED,
    }[execution.classification]


def _verdict_reasons(reasons: tuple[str, ...]) -> set[str]:
    return {
        reason
        for reason in reasons
        if reason not in {"OPTIONAL_REPORT_MISSING", "STREAM_TRUNCATED"}
    }
