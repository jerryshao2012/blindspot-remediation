"""
Ensure repository changes preserve the B7 static architecture invariants.
This test is intentionally inexpensive and deterministic.
It should be suitable for ordinary pull-request CI.
"""
from __future__ import annotations
from pathlib import Path
from l1_automation.architecture.b7_review import (
    format_b7_review,
    run_b7_static_review,
)
def test_repository_passes_b7_static_review() -> None:
    package_root = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "src"
        / "l1_automation"
    )
    report = run_b7_static_review(
        package_root=package_root
    )
    assert report.passed, (
        format_b7_review(
            report
        )
    )

