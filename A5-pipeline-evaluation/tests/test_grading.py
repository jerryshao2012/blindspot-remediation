import hashlib
from pathlib import Path

from ai_engineering_evaluation.grading import (
    DeterministicOracleGrader,
)
from ai_engineering_evaluation.models import (
    ExpectedFile,
    HiddenOracle,
    OracleOutcome,
    OracleType,
)


def test_file_oracle_accepts_correct_candidate(
    tmp_path: Path,
) -> None:
    content = b"correct implementation\n"

    candidate = tmp_path / "result.txt"
    candidate.write_bytes(content)

    oracle = HiddenOracle(
        oracle_id="oracle-1",
        oracle_version="1",
        oracle_type=OracleType.FILE_SHA256,
        expected_files=[
            ExpectedFile(
                relative_path="result.txt",
                sha256=hashlib.sha256(content).hexdigest(),
            )
        ],
    )

    grade = DeterministicOracleGrader().grade(
        workspace=tmp_path,
        oracle=oracle,
    )

    assert grade.outcome == OracleOutcome.CORRECT


def test_file_oracle_rejects_wrong_candidate(
    tmp_path: Path,
) -> None:
    expected = b"correct implementation\n"
    actual = b"incorrect implementation\n"

    candidate = tmp_path / "result.txt"
    candidate.write_bytes(actual)

    oracle = HiddenOracle(
        oracle_id="oracle-1",
        oracle_version="1",
        oracle_type=OracleType.FILE_SHA256,
        expected_files=[
            ExpectedFile(
                relative_path="result.txt",
                sha256=hashlib.sha256(expected).hexdigest(),
            )
        ],
    )

    grade = DeterministicOracleGrader().grade(
        workspace=tmp_path,
        oracle=oracle,
    )

    assert grade.outcome == OracleOutcome.INCORRECT
