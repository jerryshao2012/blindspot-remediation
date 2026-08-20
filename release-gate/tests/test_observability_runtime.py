from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


def _summary(run_id: str) -> dict[str, object]:
    return {
        "version": 1,
        "run_id": run_id,
        "verdict": "PASS",
        "exit_code": 0,
        "reason_codes": [],
        "started_at": "2026-08-19T00:00:00Z",
        "finished_at": "2026-08-19T00:00:01Z",
        "duration_ms": 1000,
        "base_commit": "a" * 40,
        "candidate_tree": "b" * 40,
        "patch_sha256": "c" * 64,
        "config_sha256": "d" * 64,
        "scope": {
            "status": "PASS", "reason_codes": [], "changed_paths": [],
            "outside_allowed_paths": [], "forbidden_paths": [],
            "review_required_paths": [],
        },
        "checks": [],
        "manifest_path": "manifest.json",
    }


def test_refresh_creates_pinned_namespace_and_publishes_matching_renderers(
    tmp_path: Path,
) -> None:
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    root.mkdir()
    with RefreshSession.acquire(root, _summary("run-one")) as session:
        assert session.locked
        assert session.namespace == root / "_observability"
        result = session.publish()

    assert result.data_path == root / "_observability/gate-decisions-v1.json"
    assert result.dashboard_path == root / "_observability/index.html"
    data = json.loads(result.data_path.read_bytes())
    assert data["generation_id"].encode() in result.dashboard_path.read_bytes()
    assert not (root / "_observability/.refresh.lock").is_symlink()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not portable")
def test_refresh_rejects_casefold_and_symlink_namespace(tmp_path: Path) -> None:
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()
    (root / "_OBSERVABILITY").mkdir()
    result = RefreshSession.acquire(root, _summary("run-one"))
    assert ObservabilityWarning.PATH_UNSAFE in result.warnings

    (root / "_OBSERVABILITY").rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "_observability").symlink_to(outside, target_is_directory=True)
    result = RefreshSession.acquire(root, _summary("run-one"))
    assert ObservabilityWarning.PATH_UNSAFE in result.warnings


def test_refresh_lock_busy_is_a_non_gating_outcome(tmp_path: Path) -> None:
    from release_gate.observability_runtime import (
        ObservabilityWarning,
        RefreshSession,
    )

    root = tmp_path / "evidence"
    root.mkdir()
    with RefreshSession.acquire(root, _summary("first")) as first:
        assert first.locked
        second = RefreshSession.acquire(root, _summary("second"), timeout_seconds=0)
        assert ObservabilityWarning.LOCK_BUSY in second.warnings
        assert not second.locked


def test_stale_or_corrupt_cache_is_recovered_by_rescan(tmp_path: Path) -> None:
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    namespace = root / "_observability"
    namespace.mkdir(parents=True)
    (namespace / "gate-decisions-v1.json").write_text("not json", encoding="utf-8")
    with RefreshSession.acquire(root, _summary("run-one")) as session:
        result = session.publish()
    assert json.loads(result.data_path.read_bytes())["source_runs"] == []
    assert "OBSERVABILITY_HISTORY_INVALID" in result.warning_codes


def test_partial_replace_failure_leaves_the_other_file_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import release_gate.observability_runtime as runtime
    from release_gate.observability_runtime import RefreshSession

    root = tmp_path / "evidence"
    root.mkdir()
    original = runtime.os.replace
    calls = 0

    def fail_second(
        source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        target: str | bytes | os.PathLike[str] | os.PathLike[bytes],
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("replace denied")
        original(source, target)

    monkeypatch.setattr(runtime.os, "replace", fail_second)
    with RefreshSession.acquire(root, _summary("run-one")) as session:
        result = session.publish()
    assert "OBSERVABILITY_PUBLISH_FAILED" in result.warning_codes
    assert result.data_path is not None or result.dashboard_path is not None
