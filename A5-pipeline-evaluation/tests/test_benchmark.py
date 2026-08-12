import hashlib
import json
from pathlib import Path

from ai_engineering_evaluation.benchmark import BenchmarkFactory
from ai_engineering_evaluation.models import (
    HiddenOracle,
    OracleType,
)


def test_valid_benchmark_loads(
    tmp_path: Path,
) -> None:
    task = tmp_path / "task.json"

    task.write_text(
        json.dumps(
            {
                "task": "Correct the known deterministic defect."
            }
        ),
        encoding="utf-8",
    )

    oracle = HiddenOracle(
        oracle_id="oracle-1",
        oracle_version="1",
        oracle_type=OracleType.COMMAND,
        command=["python", "-m", "pytest", "-q"],
    )

    oracle_path = tmp_path / "oracle.json"

    oracle_bytes = (
        oracle.model_dump_json(indent=2) + "\n"
    ).encode("utf-8")

    oracle_path.write_bytes(oracle_bytes)

    cases = [
        {
            "case_id": "case-1",
            "task_type": "X1",
            "difficulty": "small",
            "task_payload_uri": task.resolve().as_uri(),
            "starting_repository_uri": tmp_path.resolve().as_uri(),
            "starting_commit": "a" * 40,
            "oracle_uri": oracle_path.resolve().as_uri(),
            "oracle_sha256": hashlib.sha256(
                oracle_bytes
            ).hexdigest(),
            "tags": ["unit-test"],
        }
    ]

    cases_path = tmp_path / "cases.json"

    cases_path.write_text(
        json.dumps(cases),
        encoding="utf-8",
    )

    benchmark = BenchmarkFactory().load_and_validate(
        benchmark_id="test-benchmark",
        benchmark_version="1",
        cases_path=cases_path,
    )

    assert benchmark.validated
    assert len(benchmark.cases) == 1
