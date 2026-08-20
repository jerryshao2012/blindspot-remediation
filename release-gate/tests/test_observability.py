from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def summary(
    run_id: str,
    finished_at: str,
    verdict: str = "PASS",
    config: str = "a" * 64,
) -> dict[str, str]:
    return {
        "run_id": run_id,
        "finished_at": finished_at,
        "verdict": verdict,
        "config_sha256": config,
    }


def valid_result(run_id: str) -> dict[str, object]:
    return {
        "version": 1,
        "run_id": run_id,
        "verdict": "PASS",
        "exit_code": 0,
        "reason_codes": [],
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:00Z",
        "duration_ms": 0,
        "base_commit": "a" * 40,
        "candidate_tree": "b" * 40,
        "patch_sha256": "c" * 64,
        "config_sha256": "a" * 64,
        "scope": {
            "status": "PASS",
            "reason_codes": [],
            "changed_paths": [],
            "outside_allowed_paths": [],
            "forbidden_paths": [],
            "review_required_paths": [],
        },
        "checks": [
            {
                "id": "tests",
                "mode": "candidate",
                "severity": "blocking",
                "status": "PASS",
                "reason_codes": [],
                "assertions": [],
            }
        ],
        "manifest_path": "manifest.json",
    }


def write_valid_run(root: Path, run_id: str, *, digest: str | None = None) -> Path:
    run = root / run_id
    run.mkdir()
    result_bytes = json.dumps(valid_result(run_id)).encode()
    (run / "result.json").write_bytes(result_bytes)
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "run_id": run_id,
                "artifacts": [
                    {
                        "path": "result.json",
                        "size_bytes": len(result_bytes),
                        "sha256": digest or hashlib.sha256(result_bytes).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return run


def test_build_report_has_warmup_windows_and_stable_generation() -> None:
    from release_gate.observability import build_report_from_summaries

    source = [
        summary("two", "2026-01-02T00:00:00Z", "FAIL"),
        summary("one", "2026-01-01T00:00:00Z", "PASS"),
        summary("three", "2026-01-03T00:00:00Z", "NEEDS_HUMAN", "b" * 64),
    ]
    first = build_report_from_summaries(source)
    second = build_report_from_summaries(list(reversed(source)))

    assert first == second
    assert first["generated_at"] == "2026-01-03T00:00:00Z"
    assert len(first["generation_id"]) == 64
    assert [item["run_id"] for item in first["series"]] == ["one", "two", "three"]
    assert first["series"][1]["config_changed"] is False
    assert first["series"][2]["config_changed"] is True
    assert first["series"][2]["windows"]["10"] == {
        "sample_size": 3,
        "counts": {"releasing": 1, "failing": 1, "human_review": 1},
        "rates": {
            "releasing": 1 / 3,
            "failing": 1 / 3,
            "human_review": 1 / 3,
        },
    }


def test_report_keeps_199_sources_100_latest_series_and_prior_context() -> None:
    from release_gate.observability import build_report_from_summaries

    source = [
        summary(
            f"run-{number:03}", f"2026-01-01T00:{number // 60:02}:{number % 60:02}Z"
        )
        for number in range(205)
    ]
    report = build_report_from_summaries(source)

    assert len(report["source_runs"]) == 199
    assert report["source_runs"][0]["run_id"] == "run-006"
    assert len(report["series"]) == 100
    assert report["series"][0]["run_id"] == "run-105"
    assert report["series"][0]["windows"]["100"]["sample_size"] == 100
    assert report["diagnostics"]["truncated"] is True


def test_conflicting_duplicates_are_skipped_and_diagnosed() -> None:
    from release_gate.observability import WarningCategory, build_report_from_summaries

    report = build_report_from_summaries(
        [
            summary("one", "2026-01-01T00:00:00Z"),
            summary("one", "2026-01-02T00:00:00Z", "FAIL"),
        ]
    )

    assert report["diagnostics"]["skipped_runs"] == 1
    assert WarningCategory.CONFLICTING_RUN.value in report["diagnostics"]["warnings"]
    assert report["source_runs"] == [summary("one", "2026-01-01T00:00:00Z")]


def test_conflicting_duplicate_resolution_is_input_order_independent() -> None:
    from release_gate.observability import build_report_from_summaries

    earlier = summary("same", "2026-01-01T00:00:00Z", "PASS")
    later = summary("same", "2026-01-02T00:00:00Z", "FAIL")

    assert build_report_from_summaries([earlier, later]) == build_report_from_summaries(
        [later, earlier]
    )


def test_renderers_are_safe_accessible_and_self_contained() -> None:
    from release_gate.observability import (
        build_report_from_summaries,
        render_html,
        render_json,
    )

    report = build_report_from_summaries(
        [summary("safe-run", "2026-01-01T00:00:00Z", config="b" * 64)]
    )
    report["series"][0]["run_id"] = "run-<x>"
    html = render_html(report)

    assert json.loads(render_json(report)) == report
    assert len(html) <= 512 * 1024
    assert b"run-&lt;x&gt;" in html
    assert b"<svg" in html and b'role="img"' in html
    assert b"Rolling 10-run trend" in html and b"Rolling 100-run trend" in html
    assert report["generation_id"].encode() in html
    assert b"https://" not in html and b"http://" not in html
    assert b"<script src=" not in html


def test_history_accepts_only_complete_digest_matched_runs_and_cache(
    tmp_path: Path,
) -> None:
    from release_gate.observability import collect_history

    root = tmp_path / "evidence"
    root.mkdir()
    run = root / "safe-run"
    run.mkdir()
    run.rmdir()
    write_valid_run(root, "safe-run")
    broken = root / "broken"
    broken.mkdir()
    (broken / ".incomplete").write_text("", encoding="utf-8")

    collected = collect_history(
        root, cache={"source_runs": [summary("cached", "2025-01-01T00:00:00Z")]}
    )

    assert [item.run_id for item in collected.source_runs] == ["cached", "safe-run"]
    assert collected.skipped_runs == 1


def test_history_skips_bad_runs_without_losing_valid_cache_or_evidence(
    tmp_path: Path,
) -> None:
    from release_gate.observability import WarningCategory, collect_history

    root = tmp_path / "evidence"
    root.mkdir()
    write_valid_run(root, "valid")
    write_valid_run(root, "digest-bad", digest="0" * 64)
    malformed = root / "malformed"
    malformed.mkdir()
    (malformed / "result.json").write_text("{", encoding="utf-8")
    (malformed / "manifest.json").write_text("{", encoding="utf-8")
    oversized = root / "oversized"
    oversized.mkdir()
    (oversized / "result.json").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    (oversized / "manifest.json").write_text("{}", encoding="utf-8")
    linked = root / "linked"
    linked.mkdir()
    (linked / "result.json").symlink_to(root / "valid" / "result.json")
    (linked / "manifest.json").symlink_to(root / "valid" / "manifest.json")
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("not json", encoding="utf-8")

    collected = collect_history(root, cache=cache_path)

    assert [item.run_id for item in collected.source_runs] == ["valid"]
    assert collected.skipped_runs == 5
    assert WarningCategory.CACHE_INVALID in collected.warnings
    assert WarningCategory.RUN_DIGEST_MISMATCH in collected.warnings
    assert WarningCategory.MALFORMED_RUN in collected.warnings
    assert WarningCategory.RUN_TOO_LARGE in collected.warnings
    assert WarningCategory.RUN_DIRECTORY_UNSAFE in collected.warnings


def test_history_dedupes_conflicting_cache_and_recovered_run(tmp_path: Path) -> None:
    from release_gate.observability import WarningCategory, collect_history

    root = tmp_path / "evidence"
    root.mkdir()
    write_valid_run(root, "same")
    collected = collect_history(
        root,
        cache={"source_runs": [summary("same", "2026-01-02T00:00:00Z", "FAIL")]},
    )

    assert [item.run_id for item in collected.source_runs] == ["same"]
    assert collected.skipped_runs == 1
    assert WarningCategory.CONFLICTING_RUN in collected.warnings


def test_history_collection_is_bounded_to_latest_199_summaries(tmp_path: Path) -> None:
    from release_gate.observability import collect_history

    root = tmp_path / "evidence"
    root.mkdir()
    cache = {
        "source_runs": [
            summary(f"r{number}", f"2026-01-01T00:00:{number % 60:02}Z")
            for number in range(200)
        ]
    }

    collected = collect_history(root, cache=cache)

    assert len(collected.source_runs) == 199
    assert collected.truncated is True


def test_gate_decisions_schema_validates_report() -> None:
    from release_gate.observability import build_report_from_summaries

    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "schemas" / "gate-decisions-v1.schema.json").read_text()
    )
    report = build_report_from_summaries([summary("one", "2026-01-01T00:00:00Z")])

    assert (
        list(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
                report
            )
        )
        == []
    )
