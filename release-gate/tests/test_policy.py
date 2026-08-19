from __future__ import annotations

from pathlib import Path

import pytest

from release_gate.assertions import AssertionOutcome, AssertionState
from release_gate.models import Check, CheckMode, FrozenDict, Scope, Severity
from release_gate.policy import (
    CheckStatus,
    Verdict,
    aggregate_verdict,
    combine_check,
    evaluate_scope,
    preflight_reasons,
    skipped_check,
)
from release_gate.process import ExecutionClass, ExecutionResult, StreamEvidence


def execution(
    classification: ExecutionClass, reason: tuple[str, ...] = ()
) -> ExecutionResult:
    empty = StreamEvidence(
        path=Path("log"),
        size=0,
        original_size=0,
        sha256="0" * 64,
        full_sha256="0" * 64,
        truncated=False,
    )
    return ExecutionResult(
        classification=classification,
        reason_codes=reason,
        exit_code=0 if classification is ExecutionClass.PASS else 1,
        timed_out=False,
        duration_ms=1,
        stdout=empty,
        stderr=empty,
        environment_names=(),
    )


def check(
    *,
    mode: CheckMode = CheckMode.CANDIDATE,
    severity: Severity = Severity.BLOCKING,
) -> Check:
    return Check(
        id="tests",
        mode=mode,
        severity=severity,
        argv=("test-tool",),
        environment=FrozenDict(),
    )


@pytest.mark.parametrize(
    ("pattern", "matching", "not_matching"),
    [
        ("*.md", "docs/readme.md", "docs/readme.txt"),
        ("/foo", "foo/x", "x/foo"),
        ("/*.md", "readme.md", "docs/readme.md"),
        ("/docs/", "docs/x.md", "x/docs/x.md"),
        ("foo/", "x/foo/file", "x/food/file"),
        ("a/**/b", "a/x/y/b", "x/a/y/b"),
        ("a/**", "a/x/y", "x/a/y"),
        ("file[0-9].txt", "x/file2.txt", "x/filex.txt"),
    ],
)
def test_scope_uses_gitwildmatch_semantics(
    pattern: str, matching: str, not_matching: str
) -> None:
    outcome = evaluate_scope(Scope(allowed_paths=(pattern,)), (matching, not_matching))
    assert matching not in outcome.outside_allowed_paths
    assert not_matching in outcome.outside_allowed_paths


def test_scope_retains_overlapping_fail_and_review_findings() -> None:
    scope = Scope(
        allowed_paths=("src/**",),
        forbidden_paths=("src/forbidden/**",),
        review_required_paths=("src/forbidden/review.py",),
    )
    outcome = evaluate_scope(
        scope,
        ("src/ok.py", "outside.txt", "src/forbidden/review.py"),
    )

    assert outcome.verdict is Verdict.NEEDS_HUMAN
    assert outcome.outside_allowed_paths == ("outside.txt",)
    assert outcome.forbidden_paths == ("src/forbidden/review.py",)
    assert outcome.review_required_paths == ("src/forbidden/review.py",)
    assert outcome.reason_codes == (
        "PATH_FORBIDDEN",
        "PATH_OUTSIDE_ALLOWED",
        "PATH_REVIEW_REQUIRED",
    )


@pytest.mark.parametrize(
    ("base", "candidate", "expected"),
    [
        (ExecutionClass.PASS, ExecutionClass.PASS, CheckStatus.PASS),
        (ExecutionClass.PASS, ExecutionClass.FAIL, CheckStatus.FAIL),
        (ExecutionClass.FAIL, ExecutionClass.FAIL, CheckStatus.PASS),
        (ExecutionClass.FAIL, ExecutionClass.PASS, CheckStatus.PASS),
        (ExecutionClass.ERROR, ExecutionClass.PASS, CheckStatus.ERROR),
        (ExecutionClass.PASS, ExecutionClass.ERROR, CheckStatus.ERROR),
    ],
)
def test_differential_exit_semantics(
    base: ExecutionClass, candidate: ExecutionClass, expected: CheckStatus
) -> None:
    outcome = combine_check(
        check(mode=CheckMode.DIFFERENTIAL),
        baseline=execution(
            base, ("COMMAND_FAILED",) if base is ExecutionClass.FAIL else ()
        ),
        candidate=execution(
            candidate,
            ("COMMAND_FAILED",) if candidate is ExecutionClass.FAIL else (),
        ),
    )
    assert outcome.status is expected


def test_assertion_failure_and_error_override_exit_pass() -> None:
    failed = AssertionOutcome(
        state=AssertionState.FAIL,
        actual=1,
        reason_codes=("ASSERTION_FAILED",),
    )
    errored = AssertionOutcome(
        state=AssertionState.ERROR,
        actual=None,
        reason_codes=("ASSERTION_OPERAND_ERROR",),
    )
    fail_outcome = combine_check(
        check(), candidate=execution(ExecutionClass.PASS), assertions=(failed,)
    )
    error_outcome = combine_check(
        check(), candidate=execution(ExecutionClass.PASS), assertions=(failed, errored)
    )
    assert fail_outcome.status is CheckStatus.FAIL
    assert error_outcome.status is CheckStatus.ERROR


@pytest.mark.parametrize(
    ("severity", "status", "expected"),
    [
        (Severity.BLOCKING, CheckStatus.FAIL, Verdict.FAIL),
        (Severity.ADVISORY, CheckStatus.FAIL, Verdict.NEEDS_HUMAN),
        (Severity.INFORMATIONAL, CheckStatus.FAIL, Verdict.PASS),
        (Severity.BLOCKING, CheckStatus.ERROR, Verdict.NEEDS_HUMAN),
        (Severity.ADVISORY, CheckStatus.ERROR, Verdict.NEEDS_HUMAN),
        (Severity.INFORMATIONAL, CheckStatus.ERROR, Verdict.NEEDS_HUMAN),
        (Severity.INFORMATIONAL, CheckStatus.SKIPPED, Verdict.NEEDS_HUMAN),
    ],
)
def test_verdict_matrix(
    severity: Severity, status: CheckStatus, expected: Verdict
) -> None:
    configured = check(severity=severity)
    if status is CheckStatus.SKIPPED:
        outcome = skipped_check(configured, ("PREPARATION_FAILED",))
    else:
        classification = {
            CheckStatus.FAIL: ExecutionClass.FAIL,
            CheckStatus.ERROR: ExecutionClass.ERROR,
        }[status]
        reason = {
            CheckStatus.FAIL: ("COMMAND_FAILED",),
            CheckStatus.ERROR: ("COMMAND_TIMED_OUT",),
        }[status]
        outcome = combine_check(
            configured,
            candidate=execution(classification, reason),
        )
    decision = aggregate_verdict(
        evaluate_scope(Scope(allowed_paths=("**",)), ("src/x",)), (outcome,)
    )
    assert decision.verdict is expected


def test_needs_human_always_outranks_fail() -> None:
    blocking_fail = combine_check(
        check(severity=Severity.BLOCKING),
        candidate=execution(ExecutionClass.FAIL, ("COMMAND_FAILED",)),
    )
    informational_error = combine_check(
        check(severity=Severity.INFORMATIONAL),
        candidate=execution(ExecutionClass.ERROR, ("COMMAND_TIMED_OUT",)),
    )
    decision = aggregate_verdict(
        evaluate_scope(Scope(allowed_paths=("**",)), ("src/x",)),
        (blocking_fail, informational_error),
    )
    assert decision.verdict is Verdict.NEEDS_HUMAN
    assert decision.reason_codes == ("COMMAND_FAILED", "COMMAND_TIMED_OUT")


@pytest.mark.parametrize(
    ("policy_changed", "launcher_changed", "expected"),
    [
        (False, False, ()),
        (True, False, ("POLICY_FILE_CHANGED",)),
        (False, True, ("CONTROL_LAUNCHER_REVIEW",)),
        (
            True,
            True,
            ("CONTROL_LAUNCHER_REVIEW", "POLICY_FILE_CHANGED"),
        ),
    ],
)
def test_invariant_preflight_reasons(
    policy_changed: bool, launcher_changed: bool, expected: tuple[str, ...]
) -> None:
    assert preflight_reasons(policy_changed, launcher_changed) == expected


def test_skipped_check_preserves_identity_and_narrow_reason() -> None:
    configured = check(mode=CheckMode.DIFFERENTIAL, severity=Severity.ADVISORY)
    outcome = skipped_check(configured, ("POLICY_FILE_CHANGED",))
    assert outcome.id == configured.id
    assert outcome.mode is configured.mode
    assert outcome.severity is configured.severity
    assert outcome.status is CheckStatus.SKIPPED
    assert outcome.reason_codes == ("POLICY_FILE_CHANGED",)
