"""
First controlled synthetic X1 benchmark.

WHY SYNTHETIC?
--------------

For the first POC we need cases for which:

    - the requested behavior is unambiguous;
    - hidden truth can be constructed reliably;
    - execution can be deterministic;
    - expected failure modes are known.

Synthetic cases are useful for validating evaluation machinery.

They must NOT be presented as proof of performance on all real L1 work.

The benchmark below therefore carries an explicit synthetic identity.

WHY MULTIPLE CASE TYPES?
------------------------

A benchmark containing many copies of the same trivial addition defect would
inflate N without adding much diversity.

The first B5 benchmark deliberately varies simple operators and boundary
conditions.

This is still a development benchmark rather than a production qualification
benchmark.
"""

from __future__ import annotations

from .contracts import (
    BenchmarkCase,
    PublicTaskPackage,
)

from .oracle import (
    HiddenX1Definition,
)


BENCHMARK_ID = "synthetic-x1-development"

BENCHMARK_VERSION = "1.0.0"


X1_BENCHMARK_CASES: tuple[
    BenchmarkCase,
    ...
] = (

    BenchmarkCase(
        public_task=PublicTaskPackage(
            case_id="X1-001",
            task_type="X1",
            repository_id=(
                "synthetic/x1-addition"
            ),
            baseline_revision="baseline-001",
            instruction=(
                "Correct calculate(a, b) so that the function returns "
                "the sum of a and b rather than subtracting b."
            ),
            public_metadata={
                "language": "python",
                "difficulty": "development-smoke",
            },
        ),
        benchmark_case_version="1.0.0",
    ),

    BenchmarkCase(
        public_task=PublicTaskPackage(
            case_id="X1-002",
            task_type="X1",
            repository_id=(
                "synthetic/x1-upper-bound"
            ),
            baseline_revision="baseline-002",
            instruction=(
                "Correct within_limit(value, limit) so that a value "
                "equal to the inclusive limit is accepted."
            ),
            public_metadata={
                "language": "python",
                "difficulty": "development-smoke",
            },
        ),
        benchmark_case_version="1.0.0",
    ),

    BenchmarkCase(
        public_task=PublicTaskPackage(
            case_id="X1-003",
            task_type="X1",
            repository_id=(
                "synthetic/x1-empty-list"
            ),
            baseline_revision="baseline-003",
            instruction=(
                "Correct first_or_none(values) so that an empty sequence "
                "returns None instead of raising an index error."
            ),
            public_metadata={
                "language": "python",
                "difficulty": "development-smoke",
            },
        ),
        benchmark_case_version="1.0.0",
    ),

    BenchmarkCase(
        public_task=PublicTaskPackage(
            case_id="X1-004",
            task_type="X1",
            repository_id=(
                "synthetic/x1-discount-floor"
            ),
            baseline_revision="baseline-004",
            instruction=(
                "Correct apply_discount so that the returned monetary "
                "amount can never be negative."
            ),
            public_metadata={
                "language": "python",
                "difficulty": "development-smoke",
            },
        ),
        benchmark_case_version="1.0.0",
    ),
)


X1_HIDDEN_DEFINITIONS: tuple[
    HiddenX1Definition,
    ...
] = (

    HiddenX1Definition(
        case_id="X1-001",
        required_fragment="return a + b",
        forbidden_fragments=(
            "return a - b",
        ),
    ),

    HiddenX1Definition(
        case_id="X1-002",
        required_fragment="value <= limit",
        forbidden_fragments=(
            "value < limit",
        ),
    ),

    HiddenX1Definition(
        case_id="X1-003",
        required_fragment=(
            "return values[0] if values else None"
        ),
        forbidden_fragments=(
            "return values[0]\n",
        ),
    ),

    HiddenX1Definition(
        case_id="X1-004",
        required_fragment=(
            "return max(0, amount - discount)"
        ),
        forbidden_fragments=(
            "return amount - discount",
        ),
    ),
)

