"""End-to-end orchestration for the standalone release gate."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import posixpath
import secrets
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from release_gate import __version__
from release_gate.assertions import AssertionState, evaluate_assertion
from release_gate.evidence import (
    EvidenceBudgetExhausted,
    EvidenceError,
    EvidenceRun,
)
from release_gate.git import CandidateCapture, CaptureError, capture_candidate
from release_gate.models import (
    Check,
    CheckMode,
    GateConfig,
    PlatformName,
    PrepareStep,
    ReportParser,
    ResolvedCommand,
    Scalar,
)
from release_gate.policy import (
    CheckOutcome,
    CheckStatus,
    Verdict,
    aggregate_verdict,
    combine_check,
    evaluate_scope,
    preflight_reasons,
    skipped_check,
)
from release_gate.process import (
    ExecutionClass,
    ExecutionResult,
    run_command,
)
from release_gate.reports import (
    ReportError,
    clear_report_paths,
    collect_report,
)
from release_gate.timestamps import utc_timestamp
from release_gate.trace import TraceRecorder
from release_gate.workspaces import WorkspaceError, clean_workspaces


class GateInputError(ValueError):
    """The requested run has invalid input or configuration."""


@dataclass(frozen=True, slots=True)
class RunOutcome:
    verdict: Verdict
    exit_code: int
    result_path: Path


@dataclass(slots=True)
class _Execution:
    record: dict[str, Any]
    result: ExecutionResult
    reports: dict[str, object | None]
    budget_exhausted: bool = False


def run_gate(
    repository: Path,
    *,
    base: str = "HEAD",
    output: Path | None = None,
    run_id: str | None = None,
) -> RunOutcome:
    """Capture, evaluate, and atomically finalize one gate run."""

    started_wall = datetime.now(UTC)
    started_clock = time.monotonic_ns()
    try:
        capture = capture_candidate(repository, base=base)
    except CaptureError as error:
        raise GateInputError(str(error)) from error
    family = _platform_name()
    config_bytes = _effective_config(capture.config, family)
    root = _evidence_root(capture, output)
    identifier = run_id or _default_run_id(started_wall)
    try:
        evidence = EvidenceRun.create(
            root,
            identifier,
            total_bytes=capture.config.limits.total_bytes,
            patch=capture.patch,
            effective_config=config_bytes,
        )
    except (EvidenceError, OSError) as error:
        raise GateInputError(f"invalid evidence root or run: {error}") from error

    trace = TraceRecorder()
    trace.add("candidate_captured", changed_paths=len(capture.changed_paths))
    scope = evaluate_scope(capture.config.scope, capture.changed_paths)
    launcher_changed = _launcher_changed(capture, family)
    stop_reasons = preflight_reasons(capture.policy_changed, launcher_changed)
    executions: list[dict[str, Any]] = []
    checks: list[CheckOutcome] = []
    run_reasons: set[str] = set(stop_reasons)

    if stop_reasons:
        trace.add("preflight_stopped", reason_codes=list(stop_reasons))
        checks = [skipped_check(check, stop_reasons) for check in capture.config.checks]
        executions.extend(
            _skipped_schedule(capture.config, family, stop_reasons, started_wall)
        )
    else:
        try:
            with clean_workspaces(capture) as workspaces:
                with tempfile.TemporaryDirectory(
                    prefix="release-gate-control-"
                ) as temporary:
                    preparation_failed = _run_preparation(
                        capture.config,
                        family,
                        workspaces.base,
                        workspaces.candidate,
                        Path(temporary),
                        evidence,
                        executions,
                        trace,
                    )
                    if preparation_failed:
                        budget_stopped = (
                            "EVIDENCE_BUDGET_EXHAUSTED" in preparation_failed
                        )
                        stop_reason = (
                            "EVIDENCE_BUDGET_EXHAUSTED"
                            if budget_stopped
                            else "PREPARATION_FAILED"
                        )
                        run_reasons.add(stop_reason)
                        if not budget_stopped:
                            run_reasons.update(preparation_failed)
                        checks = [
                            skipped_check(check, (stop_reason,))
                            for check in capture.config.checks
                        ]
                        executions.extend(
                            _skipped_checks(
                                capture.config,
                                family,
                                (stop_reason,),
                                datetime.now(UTC),
                            )
                        )
                    else:
                        checks = _run_checks(
                            capture.config,
                            family,
                            workspaces.base,
                            workspaces.candidate,
                            Path(temporary),
                            evidence,
                            executions,
                            trace,
                        )
        except (WorkspaceError, OSError) as error:
            raise RuntimeError(f"workspace evaluation failed: {error}") from error

    decision = aggregate_verdict(scope, tuple(checks), run_reasons=tuple(run_reasons))
    finished_wall = datetime.now(UTC)
    duration_ms = max(0, (time.monotonic_ns() - started_clock) // 1_000_000)
    result = _result_document(
        identifier,
        capture,
        config_bytes,
        scope,
        checks,
        decision.verdict,
        decision.reason_codes,
        started_wall,
        finished_wall,
        duration_ms,
    )
    manifest = _manifest_document(
        identifier,
        capture,
        config_bytes,
        decision.reason_codes,
        executions,
        family,
        started_wall,
        finished_wall,
        duration_ms,
    )
    trace.add("verdict_decided", verdict=decision.verdict.value)
    completed = evidence.finalize(
        result,
        manifest,
        trace.finish(reason_codes=decision.reason_codes),
    )
    exit_code = {
        Verdict.PASS: 0,
        Verdict.FAIL: 1,
        Verdict.NEEDS_HUMAN: 2,
    }[decision.verdict]
    return RunOutcome(decision.verdict, exit_code, completed / "result.json")


def _run_preparation(
    config: GateConfig,
    family: PlatformName,
    base: Path,
    candidate: Path,
    temporary: Path,
    evidence: EvidenceRun,
    records: list[dict[str, Any]],
    trace: TraceRecorder,
) -> tuple[str, ...]:
    sides = (
        (("base", base), ("candidate", candidate))
        if config.requires_base_workspace
        else (("candidate", candidate),)
    )
    for index, step in enumerate(config.prepare):
        for side, workspace in sides:
            execution = _execute_control(
                step,
                phase="prepare",
                side=side,
                workspace=workspace,
                family=family,
                temporary=temporary,
                evidence=evidence,
                config=config,
            )
            records.append(execution.record)
            trace.add(
                "control_finished",
                control_id=step.id,
                phase="prepare",
                side=side,
                classification=execution.result.classification.value,
            )
            if execution.result.classification is not ExecutionClass.PASS:
                reason = execution.result.reason_codes
                stop_reason = (
                    "EVIDENCE_BUDGET_EXHAUSTED"
                    if execution.budget_exhausted
                    else "PREPARATION_FAILED"
                )
                now = datetime.now(UTC)
                for remaining in config.prepare[index + 1 :]:
                    for later_side, _ in sides:
                        records.append(
                            _skipped_record(
                                remaining.id,
                                "prepare",
                                later_side,
                                remaining.resolve(family),
                                (stop_reason,),
                                now,
                                family,
                            )
                        )
                return reason or ("REQUIRED_CONTROL_SKIPPED",)
    return ()


def _run_checks(
    config: GateConfig,
    family: PlatformName,
    base: Path,
    candidate: Path,
    temporary: Path,
    evidence: EvidenceRun,
    records: list[dict[str, Any]],
    trace: TraceRecorder,
) -> list[CheckOutcome]:
    outcomes: list[CheckOutcome] = []
    for check in config.checks:
        baseline: _Execution | None = None
        if check.mode is CheckMode.DIFFERENTIAL:
            baseline = _execute_control(
                check,
                phase="check",
                side="base",
                workspace=base,
                family=family,
                temporary=temporary,
                evidence=evidence,
                config=config,
            )
            records.append(baseline.record)
            if baseline.budget_exhausted:
                records.append(
                    _skipped_record(
                        check.id,
                        "check",
                        "candidate",
                        check.resolve(family),
                        ("EVIDENCE_BUDGET_EXHAUSTED",),
                        datetime.now(UTC),
                        family,
                    )
                )
                outcomes.append(
                    skipped_check(check, ("EVIDENCE_BUDGET_EXHAUSTED",))
                )
                _append_budget_skips(
                    config, family, check, outcomes, records, datetime.now(UTC)
                )
                break
        current = _execute_control(
            check,
            phase="check",
            side="candidate",
            workspace=candidate,
            family=family,
            temporary=temporary,
            evidence=evidence,
            config=config,
        )
        records.append(current.record)
        assertions = tuple(
            evaluate_assertion(
                assertion,
                candidate=current.reports,
                baseline=baseline.reports if baseline else None,
            )
            for assertion in check.assertions
        )
        report_errors = {
            reason
            for execution in (baseline, current)
            if execution is not None
            for reason in execution.record.pop("check_reason_codes", [])
        }
        outcome = combine_check(
            check,
            candidate=current.result,
            baseline=baseline.result if baseline else None,
            assertions=assertions,
            diagnostics=tuple(sorted(report_errors)),
        )
        if report_errors:
            outcome = replace(outcome, status=CheckStatus.ERROR)
        outcomes.append(outcome)
        trace.add(
            "check_finished",
            control_id=check.id,
            status=outcome.status.value,
        )
        if current.budget_exhausted:
            _append_budget_skips(
                config, family, check, outcomes, records, datetime.now(UTC)
            )
            break
    return outcomes


def _append_budget_skips(
    config: GateConfig,
    family: PlatformName,
    completed: Check,
    outcomes: list[CheckOutcome],
    records: list[dict[str, Any]],
    now: datetime,
) -> None:
    start = next(
        index
        for index, configured in enumerate(config.checks)
        if configured is completed
    )
    for check in config.checks[start + 1 :]:
        outcomes.append(skipped_check(check, ("EVIDENCE_BUDGET_EXHAUSTED",)))
        sides = (
            ("base", "candidate")
            if check.mode is CheckMode.DIFFERENTIAL
            else ("candidate",)
        )
        for side in sides:
            records.append(
                _skipped_record(
                    check.id,
                    "check",
                    side,
                    check.resolve(family),
                    ("EVIDENCE_BUDGET_EXHAUSTED",),
                    now,
                    family,
                )
            )


def _execute_control(
    control: PrepareStep | Check,
    *,
    phase: str,
    side: str,
    workspace: Path,
    family: PlatformName,
    temporary: Path,
    evidence: EvidenceRun,
    config: GateConfig,
) -> _Execution:
    command = control.resolve(family)
    raw = temporary / control.id / side
    raw.mkdir(parents=True, exist_ok=True)
    report_errors: list[str] = []
    if isinstance(control, Check):
        try:
            clear_report_paths(control.reports, workspace)
        except ReportError as error:
            report_errors.append(error.reason_code)
    started = datetime.now(UTC)
    result = run_command(
        command,
        workspace=workspace,
        artifact_dir=raw,
        stream_limit=config.limits.stream_bytes,
    )
    finished = datetime.now(UTC)
    prefix = f"controls/{control.id}/{side}"
    budget_exhausted = False
    for name, stream in (("stdout", result.stdout), ("stderr", result.stderr)):
        try:
            evidence.write_artifact(
                f"{prefix}/{name}.log",
                stream.path.read_bytes(),
                "application/octet-stream",
                truncated=stream.truncated,
                original_size_bytes=stream.original_size if stream.truncated else None,
                full_sha256=stream.full_sha256 if stream.truncated else None,
            )
        except EvidenceBudgetExhausted:
            budget_exhausted = True
    diagnostics = set(result.reason_codes)
    if result.stdout.truncated or result.stderr.truncated:
        diagnostics.add("STREAM_TRUNCATED")
        result = replace(result, reason_codes=tuple(sorted(diagnostics)))
    reports: dict[str, object | None] = {}
    metrics: dict[str, Scalar] = {}
    if isinstance(control, Check) and not budget_exhausted:
        for report in control.reports:
            try:
                outcome = collect_report(
                    report,
                    workspace=workspace,
                    artifact_dir=raw / "reports",
                    global_limit=config.limits.report_bytes,
                )
                reports[report.id] = outcome.metrics
                diagnostics.update(outcome.reason_codes)
                if outcome.artifact_path:
                    extension = (
                        ".xml"
                        if report.parser is ReportParser.JUNIT_XML
                        else ".json"
                    )
                    try:
                        evidence.write_artifact(
                            f"{prefix}/reports/{report.id}{extension}",
                            outcome.artifact_path.read_bytes(),
                            "application/xml"
                            if extension == ".xml"
                            else "application/json",
                        )
                    except EvidenceBudgetExhausted:
                        budget_exhausted = True
                        report_errors.append("EVIDENCE_BUDGET_EXHAUSTED")
                        break
            except ReportError as error:
                reports[report.id] = None
                report_errors.append(error.reason_code)
        metrics = _referenced_metrics(control, reports)
        permitted = {
            reason
            for reason in diagnostics
            if reason in {"OPTIONAL_REPORT_MISSING", "STREAM_TRUNCATED"}
        }
        if result.classification is not ExecutionClass.PASS:
            permitted.update(result.reason_codes)
        result = replace(result, reason_codes=tuple(sorted(permitted)))
    elif isinstance(control, Check):
        reports.update({report.id: None for report in control.reports})
    if budget_exhausted:
        result = replace(
            result,
            classification=ExecutionClass.ERROR,
            reason_codes=tuple(
                sorted({*result.reason_codes, "EVIDENCE_BUDGET_EXHAUSTED"})
            ),
        )
    record = _execution_record(
        control.id,
        phase,
        side,
        command,
        result,
        metrics,
        started,
        finished,
    )
    if report_errors:
        record["check_reason_codes"] = sorted(set(report_errors))
    return _Execution(
        record=record,
        result=result,
        reports=reports,
        budget_exhausted=budget_exhausted,
    )


def _referenced_metrics(
    check: Check, reports: dict[str, object | None]
) -> dict[str, Scalar]:
    from release_gate.assertions import resolve_pointer

    metrics: dict[str, Scalar] = {}
    for assertion in check.assertions:
        report = reports.get(assertion.report)
        if report is None:
            continue
        try:
            value = resolve_pointer(report, assertion.metric)
        except ValueError:
            continue
        if value is None or isinstance(value, (str, bool, int, float)):
            metrics[f"{assertion.report}#{assertion.metric}"] = value
    return metrics


def _execution_record(
    control_id: str,
    phase: str,
    side: str,
    command: ResolvedCommand,
    result: ExecutionResult,
    metrics: dict[str, Scalar],
    started: datetime,
    finished: datetime,
) -> dict[str, Any]:
    return {
        "control_id": control_id,
        "phase": phase,
        "side": side,
        "argv": list(command.argv),
        "cwd": command.cwd,
        "environment_keys": list(result.environment_names),
        "started_at": utc_timestamp(started),
        "finished_at": utc_timestamp(finished),
        "duration_ms": result.duration_ms,
        "classification": result.classification.value,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "reason_codes": list(result.reason_codes),
        "metrics": metrics,
    }


def _skipped_schedule(
    config: GateConfig,
    family: PlatformName,
    reasons: tuple[str, ...],
    now: datetime,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    prepare_sides = (
        ("base", "candidate")
        if config.requires_base_workspace
        else ("candidate",)
    )
    for step in config.prepare:
        for side in prepare_sides:
            records.append(
                _skipped_record(
                    step.id,
                    "prepare",
                    side,
                    step.resolve(family),
                    reasons,
                    now,
                    family,
                )
            )
    records.extend(_skipped_checks(config, family, reasons, now))
    return records


def _skipped_checks(
    config: GateConfig,
    family: PlatformName,
    reasons: tuple[str, ...],
    now: datetime,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for check in config.checks:
        sides = (
            ("base", "candidate")
            if check.mode is CheckMode.DIFFERENTIAL
            else ("candidate",)
        )
        for side in sides:
            records.append(
                _skipped_record(
                    check.id,
                    "check",
                    side,
                    check.resolve(family),
                    reasons,
                    now,
                    family,
                )
            )
    return records


def _skipped_record(
    control_id: str,
    phase: str,
    side: str,
    command: ResolvedCommand,
    reasons: tuple[str, ...],
    now: datetime,
    family: PlatformName,
) -> dict[str, Any]:
    return {
        "control_id": control_id,
        "phase": phase,
        "side": side,
        "argv": list(command.argv),
        "cwd": command.cwd,
        "environment_keys": list(_environment_names(command, family)),
        "started_at": utc_timestamp(now),
        "finished_at": utc_timestamp(now),
        "duration_ms": 0,
        "classification": "skipped",
        "exit_code": None,
        "timed_out": False,
        "reason_codes": list(reasons),
        "metrics": {},
    }


def _environment_names(
    command: ResolvedCommand, family: PlatformName
) -> tuple[str, ...]:
    names = {*command.environment, *command.inherit_environment, "HOME"}
    if family is PlatformName.WINDOWS:
        names.update({"USERPROFILE", "HOMEDRIVE", "HOMEPATH", "TEMP", "TMP"})
    else:
        names.add("TMPDIR")
    return tuple(sorted(names))


def _result_document(
    run_id: str,
    capture: CandidateCapture,
    config_bytes: bytes,
    scope: Any,
    checks: list[CheckOutcome],
    verdict: Verdict,
    reason_codes: tuple[str, ...],
    started: datetime,
    finished: datetime,
    duration_ms: int,
) -> dict[str, Any]:
    return {
        "version": 1,
        "run_id": run_id,
        "verdict": verdict.value,
        "exit_code": {
            Verdict.PASS: 0,
            Verdict.FAIL: 1,
            Verdict.NEEDS_HUMAN: 2,
        }[verdict],
        "reason_codes": list(reason_codes),
        "started_at": utc_timestamp(started),
        "finished_at": utc_timestamp(finished),
        "duration_ms": duration_ms,
        "base_commit": capture.base_commit,
        "candidate_tree": capture.candidate_tree,
        "patch_sha256": capture.patch_sha256,
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "scope": {
            "status": scope.verdict.value,
            "reason_codes": list(scope.reason_codes),
            "changed_paths": list(scope.changed_paths),
            "outside_allowed_paths": list(scope.outside_allowed_paths),
            "forbidden_paths": list(scope.forbidden_paths),
            "review_required_paths": list(scope.review_required_paths),
        },
        "checks": [
            _check_document(check, capture.config.checks[index])
            for index, check in enumerate(checks)
        ],
        "manifest_path": "manifest.json",
    }


def _check_document(outcome: CheckOutcome, configured: Check) -> dict[str, Any]:
    assertions = []
    evaluated_assertions = (
        () if outcome.status is CheckStatus.SKIPPED else outcome.assertions
    )
    configured_assertions = (
        () if outcome.status is CheckStatus.SKIPPED else configured.assertions
    )
    for assertion, evaluated in zip(
        configured_assertions, evaluated_assertions, strict=True
    ):
        assertions.append(
            {
                "report": assertion.report,
                "metric": assertion.metric,
                "comparison": assertion.comparison.value,
                "operator": assertion.operator.value,
                "expected": assertion.value,
                "actual": evaluated.actual,
                "passed": (
                    None
                    if evaluated.state is AssertionState.ERROR
                    else evaluated.state is AssertionState.PASS
                ),
                "reason_codes": list(evaluated.reason_codes),
            }
        )
    return {
        "id": outcome.id,
        "mode": outcome.mode.value,
        "severity": outcome.severity.value,
        "status": outcome.status.value,
        "reason_codes": list(outcome.reason_codes),
        "assertions": assertions,
    }


def _manifest_document(
    run_id: str,
    capture: CandidateCapture,
    config_bytes: bytes,
    reason_codes: tuple[str, ...],
    executions: list[dict[str, Any]],
    family: PlatformName,
    started: datetime,
    finished: datetime,
    duration_ms: int,
) -> dict[str, Any]:
    executable = Path(sys.executable).resolve(strict=True)
    return {
        "version": 1,
        "run_id": run_id,
        "hash_algorithm": "sha256",
        "created_at": utc_timestamp(datetime.now(UTC)),
        "started_at": utc_timestamp(started),
        "finished_at": utc_timestamp(finished),
        "duration_ms": duration_ms,
        "base_commit": capture.base_commit,
        "candidate_tree": capture.candidate_tree,
        "patch_sha256": capture.patch_sha256,
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "engine_version": __version__,
        "platform": {
            "family": family.value,
            "system": platform.system() or "unknown",
            "release": platform.release() or "unknown",
            "machine": platform.machine() or "unknown",
        },
        "runtime": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": str(executable),
            "executable_sha256": _hash_file(executable),
        },
        "reason_codes": list(reason_codes),
        "executions": executions,
    }


def _effective_config(config: GateConfig, family: PlatformName) -> bytes:
    value = config.model_dump(mode="json", by_alias=True, exclude_none=True)
    value["effective_platform"] = family.value
    # The platform identity is useful evidence, but the config schema is closed;
    # keep the effective representation strictly to the authoritative model.
    value.pop("effective_platform")
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _launcher_changed(capture: CandidateCapture, family: PlatformName) -> bool:
    changed = set(capture.changed_paths)
    for control in (*capture.config.prepare, *capture.config.checks):
        launcher = control.resolve(family).argv[0].replace("\\", "/")
        if os.path.isabs(launcher) or (len(launcher) > 2 and launcher[1] == ":"):
            continue
        if "/" not in launcher:
            continue
        normalized = posixpath.normpath(launcher.removeprefix("./"))
        if normalized in changed:
            return True
    return False


def _evidence_root(capture: CandidateCapture, requested: Path | None) -> Path:
    if requested is None:
        return capture.repository / ".release-gate" / "runs"
    absolute = requested.absolute()
    if absolute.exists() and not absolute.is_dir():
        raise GateInputError(f"evidence root is not a directory: {requested}")
    existing = absolute
    while not existing.exists():
        if existing.parent == existing:
            break
        existing = existing.parent
    try:
        resolved_existing = existing.resolve(strict=True)
    except OSError as error:
        raise GateInputError(f"unable to resolve evidence root: {requested}") from error
    suffix = absolute.relative_to(existing)
    resolved = resolved_existing / suffix
    protected = (capture.repository, capture.git_dir, capture.git_common_dir)
    for path in protected:
        if _overlaps(resolved, path):
            raise GateInputError("custom evidence root overlaps the source repository")
    return resolved


def _overlaps(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        pass
    try:
        right.relative_to(left)
        return True
    except ValueError:
        return False


def _platform_name() -> PlatformName:
    if os.name == "nt":
        return PlatformName.WINDOWS
    if sys.platform == "darwin":
        return PlatformName.MACOS
    return PlatformName.LINUX


def _default_run_id(started: datetime) -> str:
    return started.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(6)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
