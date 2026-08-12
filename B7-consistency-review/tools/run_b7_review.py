"""
Developer/CI entrypoint for the B7 static architecture review.
Usage:
    python tools/run_b7_review.py
Exit codes:
    0
        static B7 review passed
    1
        static B7 violations found
    2
        review could not be executed
This command deliberately does NOT run an AI evaluation campaign.
"""
from __future__ import annotations
from pathlib import Path
from l1_automation.architecture.b7_review import (
    format_b7_review,
    run_b7_static_review,
)
def main() -> int:
    repository_root = (
        Path(__file__)
        .resolve()
        .parents[1]
    )
    package_root = (
        repository_root
        / "src"
        / "l1_automation"
    )
    try:
        report = run_b7_static_review(
            package_root=package_root
        )
    except (
        FileNotFoundError,
        NotADirectoryError,
        RuntimeError,
    ) as exc:
        print(
            "B7 STATIC ARCHITECTURE REVIEW: ERROR"
        )
        print(
            str(exc)
        )
        return 2
    print(
        format_b7_review(
            report
        )
    )
    return (
        0
        if report.passed
        else 1
    )
if __name__ == "__main__":
    raise SystemExit(
        main()
    )

