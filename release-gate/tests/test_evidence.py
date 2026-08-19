from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from release_gate.evidence import (
    FINALIZATION_RESERVE,
    EvidenceError,
    EvidenceRun,
    ensure_preflight_feasible,
    verify_run,
)
from release_gate.timestamps import parse_timestamp, utc_timestamp
from release_gate.trace import TraceRecorder


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize(
    "value",
    [
        "2026-08-18T12:34:56Z",
        "2024-02-29T12:34:56.123456789+14:00",
        "2026-08-18T12:34:56-05:30",
    ],
)
def test_timestamp_profile_accepts_valid_values(value: str) -> None:
    assert parse_timestamp(value).tzinfo is not None


@pytest.mark.parametrize(
    "value",
    [
        "2026-02-29T12:34:56Z",
        "2026-08-18 12:34:56Z",
        "2026-08-18T12:34:60Z",
        "2026-08-18T12:34:56-00:00",
        "2026-08-18T12:34:56+14:01",
    ],
)
def test_timestamp_profile_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_timestamp(value)


def test_timestamp_emitter_is_utc_z() -> None:
    assert utc_timestamp(datetime(2026, 8, 18, tzinfo=UTC)) == (
        "2026-08-18T00:00:00Z"
    )


def test_preflight_budget_reserves_finalization_space() -> None:
    minimum = 7_340_032 + 4
    assert ensure_preflight_feasible(minimum, b"a", b"bbb") == minimum - 4
    with pytest.raises(EvidenceError, match="finalization reserve"):
        ensure_preflight_feasible(minimum - 1, b"a", b"bbb")


def test_trace_is_bounded_and_reserves_terminal_summary() -> None:
    trace = TraceRecorder(max_events=3, max_event_bytes=100)
    trace.add("capture", count=1)
    trace.add("execute", count=2)
    trace.add("ignored", count=3)
    encoded = trace.finish(reason_codes=("EVIDENCE_BUDGET_EXHAUSTED",))
    events = json.loads(encoded)
    assert [event["event"] for event in events] == [
        "capture",
        "execute",
        "summary",
    ]
    assert events[-1]["dropped_events"] == 1


def test_finalize_and_verify_tamper_evident_package(tmp_path: Path) -> None:
    patch = b"diff --git a/x b/x\n"
    config = b'{"checks":[],"version":1}\n'
    started = "2026-08-18T12:00:00Z"
    finished = "2026-08-18T12:00:01Z"
    run = EvidenceRun.create(
        tmp_path,
        "run-1",
        total_bytes=FINALIZATION_RESERVE + len(patch) + len(config) + 3,
        patch=patch,
        effective_config=config,
    )
    run.write_artifact("controls/check/candidate/stdout.log", b"ok\n", "text/plain")
    trace = TraceRecorder()
    trace.add("capture", count=1)
    result = {
        "version": 1,
        "run_id": "run-1",
        "verdict": "PASS",
        "exit_code": 0,
        "reason_codes": [],
        "started_at": started,
        "finished_at": finished,
        "duration_ms": 1000,
        "base_commit": "a" * 40,
        "candidate_tree": "b" * 40,
        "patch_sha256": _sha(patch),
        "config_sha256": _sha(config),
        "scope": {
            "status": "PASS",
            "reason_codes": [],
            "changed_paths": ["x"],
            "outside_allowed_paths": [],
            "forbidden_paths": [],
            "review_required_paths": [],
        },
        "checks": [
            {
                "id": "check",
                "mode": "candidate",
                "severity": "blocking",
                "status": "PASS",
                "reason_codes": [],
                "assertions": [],
            }
        ],
        "manifest_path": "manifest.json",
    }
    execution = {
        "control_id": "check",
        "phase": "check",
        "side": "candidate",
        "argv": ["true"],
        "cwd": ".",
        "environment_keys": ["HOME", "PATH"],
        "started_at": started,
        "finished_at": finished,
        "duration_ms": 1000,
        "classification": "pass",
        "exit_code": 0,
        "timed_out": False,
        "reason_codes": [],
        "metrics": {},
    }
    manifest = {
        "version": 1,
        "run_id": "run-1",
        "hash_algorithm": "sha256",
        "created_at": finished,
        "started_at": started,
        "finished_at": finished,
        "duration_ms": 1000,
        "base_commit": "a" * 40,
        "candidate_tree": "b" * 40,
        "patch_sha256": _sha(patch),
        "config_sha256": _sha(config),
        "engine_version": "0.1.0",
        "platform": {
            "family": "linux",
            "system": "Linux",
            "release": "test",
            "machine": "x86_64",
        },
        "runtime": {
            "implementation": "CPython",
            "version": "3.11.0",
            "executable": "python",
            "executable_sha256": "c" * 64,
        },
        "reason_codes": [],
        "executions": [execution],
    }
    completed = run.finalize(result, manifest, trace.finish())
    assert completed == tmp_path / "run-1"
    verify_run(completed)
    parsed_manifest = json.loads((completed / "manifest.json").read_bytes())
    paths = {artifact["path"] for artifact in parsed_manifest["artifacts"]}
    assert paths == {
        "candidate.patch",
        "effective-config.json",
        "result.json",
        "trace.json",
        "controls/check/candidate/stdout.log",
    }
    assert not (completed / ".incomplete").exists()

    (completed / "candidate.patch").write_bytes(b"tampered")
    with pytest.raises(EvidenceError, match=r"size|digest"):
        verify_run(completed)


def test_run_ids_are_append_only_and_casefold_unique(tmp_path: Path) -> None:
    (tmp_path / "RUN-1").mkdir()
    with pytest.raises(EvidenceError, match="collides"):
        EvidenceRun.create(
            tmp_path,
            "run-1",
            total_bytes=16 * 1024 * 1024,
            patch=b"p",
            effective_config=b"{}",
        )


@pytest.mark.parametrize(
    "path",
    ["../x", "/x", "Manifest.json", "controls/con/file", "a\\b", "a./x"],
)
def test_unsafe_artifact_paths_are_rejected(tmp_path: Path, path: str) -> None:
    run = EvidenceRun.create(
        tmp_path,
        "run-1",
        total_bytes=16 * 1024 * 1024,
        patch=b"p",
        effective_config=b"{}",
    )
    with pytest.raises(EvidenceError):
        run.write_artifact(path, b"x", "text/plain")
