from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest
import yaml

import release_gate.cli as cli
from release_gate import __version__
from release_gate.cli import main
from release_gate.config import MAX_CONFIG_BYTES, load_config

_VALID_POLICY = b"""\
version: 1
scope:
  allowed_paths: ["**"]
  review_required_paths: ["/.release-gate.yaml"]
checks:
  - id: tests
    mode: candidate
    severity: blocking
    argv: ["python", "-m", "pytest"]
"""


def test_version_comes_from_package_and_is_exposed_by_cli(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--version"]) == 0
    result = capsys.readouterr()
    assert result.out == f"release-gate {__version__}\n"
    assert result.err == ""

    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert project["project"]["dynamic"] == ["version"]
    assert "version" not in project["project"]
    assert project["tool"]["hatch"]["version"]["path"] == (
        "src/release_gate/__init__.py"
    )


def test_run_requires_explicit_base_at_argument_parser(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", "--repo", str(tmp_path)]) == 3
    result = capsys.readouterr()
    assert result.out == ""
    assert result.err.startswith("ERROR: ")
    assert "--base" in result.err
    assert "required" in result.err


def test_init_creates_valid_generic_draft_and_gitignore(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del capsys
    assert main(["init", "--repo", str(tmp_path)]) == 0

    policy = tmp_path / ".release-gate.yaml"
    assert policy.exists()
    value = yaml.safe_load(policy.read_text(encoding="utf-8"))
    assert value["checks"][0]["argv"] == ["release-gate-configure-me"]
    assert value["scope"]["allowed_paths"] == ["**"]
    assert load_config(policy).version == 1
    assert (
        "/.release-gate/runs/"
        in (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    )


def test_init_preserves_existing_gitignore_content(tmp_path: Path) -> None:
    ignore = tmp_path / ".gitignore"
    ignore.write_text("dist/\n", encoding="utf-8")

    assert main(["init", "--repo", str(tmp_path)]) == 0

    assert ignore.read_text(encoding="utf-8") == "dist/\n/.release-gate/runs/\n"


def test_init_from_config_preserves_exact_approved_bytes(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source = tmp_path / "approved.yaml"
    approved = _VALID_POLICY.replace(b"version: 1\n", b"# approved\r\nversion: 1\r\n")
    source.write_bytes(approved)

    assert main(["init", "--repo", str(repository), "--from-config", str(source)]) == 0

    assert (repository / ".release-gate.yaml").read_bytes() == approved
    assert (repository / ".gitignore").read_bytes() == b"/.release-gate/runs/\n"
    assert list(repository.glob(".release-gate-init-*")) == []


@pytest.mark.parametrize(
    "source_bytes",
    [
        b"version: 2\n",
        b"version: [\n",
        b"not utf-8: \xff\n",
    ],
)
def test_init_from_invalid_source_does_not_mutate_target(
    tmp_path: Path, source_bytes: bytes
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source = tmp_path / "invalid.yaml"
    source.write_bytes(source_bytes)

    assert main(["init", "--repo", str(repository), "--from-config", str(source)]) == 3
    assert not (repository / ".release-gate.yaml").exists()
    assert not (repository / ".gitignore").exists()


def test_init_from_oversized_source_does_not_mutate_target(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source = tmp_path / "oversized.yaml"
    source.write_bytes(b"#" * (MAX_CONFIG_BYTES + 1))

    assert main(["init", "--repo", str(repository), "--from-config", str(source)]) == 3
    assert not (repository / ".release-gate.yaml").exists()
    assert not (repository / ".gitignore").exists()


def test_init_from_config_rejects_directory_source_without_mutation(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source = tmp_path / "source-directory"
    source.mkdir()

    assert main(["init", "--repo", str(repository), "--from-config", str(source)]) == 3
    assert not (repository / ".release-gate.yaml").exists()
    assert not (repository / ".gitignore").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX FIFO semantics")
def test_init_from_config_rejects_fifo_without_blocking_or_mutation(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source = tmp_path / "source.fifo"
    os.mkfifo(source)

    assert main(["init", "--repo", str(repository), "--from-config", str(source)]) == 3
    assert not (repository / ".release-gate.yaml").exists()
    assert not (repository / ".gitignore").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX special-file path")
def test_init_from_config_rejects_character_device_without_mutation(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    assert (
        main(
            [
                "init",
                "--repo",
                str(repository),
                "--from-config",
                os.devnull,
            ]
        )
        == 3
    )
    assert not (repository / ".release-gate.yaml").exists()
    assert not (repository / ".gitignore").exists()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not portable")
def test_init_from_config_rejects_symlink_source_without_mutation(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    target = tmp_path / "target.yaml"
    target.write_bytes(_VALID_POLICY)
    source = tmp_path / "source.yaml"
    source.symlink_to(target)

    assert main(["init", "--repo", str(repository), "--from-config", str(source)]) == 3
    assert not (repository / ".release-gate.yaml").exists()
    assert not (repository / ".gitignore").exists()


def test_init_from_config_rejects_existing_policy_before_gitignore_mutation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    policy = tmp_path / ".release-gate.yaml"
    ignore = tmp_path / ".gitignore"
    policy.write_bytes(b"owned by user\n")
    ignore.write_bytes(b"dist/\n")

    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert policy.read_bytes() == b"owned by user\n"
    assert ignore.read_bytes() == b"dist/\n"


def test_init_rejects_symlink_gitignore_without_touching_target(
    tmp_path: Path,
) -> None:
    if os.name == "nt":
        pytest.skip("symlink creation is not generally available on Windows")
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    real_ignore = tmp_path / "owned-ignore"
    real_ignore.write_bytes(b"owned\n")
    (tmp_path / ".gitignore").symlink_to(real_ignore)

    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert real_ignore.read_bytes() == b"owned\n"
    assert not (tmp_path / ".release-gate.yaml").exists()


def test_init_rejects_non_regular_gitignore_without_policy_mutation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    (tmp_path / ".gitignore").mkdir()

    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert (tmp_path / ".gitignore").is_dir()
    assert not (tmp_path / ".release-gate.yaml").exists()


def test_init_does_not_duplicate_existing_ignore_entry(tmp_path: Path) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(b"dist/\r\n/.release-gate/runs/\r\n")

    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 0
    assert ignore.read_bytes() == b"dist/\r\n/.release-gate/runs/\r\n"


@pytest.mark.parametrize(
    "initial",
    [b"dist/\n", b"dist/\n/.release-gate/runs/\n", None],
    ids=["append", "existing-entry", "absent"],
)
def test_init_holds_exclusive_ignore_lock_through_policy_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    initial: bytes | None,
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    if initial is not None:
        ignore.write_bytes(initial)
    observed = False

    def assert_contended(event: str, path: Path) -> None:
        nonlocal observed
        if event != "before-policy-publish":
            return
        descriptor = os.open(path.parent / ".gitignore", os.O_RDWR)
        try:
            with pytest.raises(cli.ConfigError, match="locked by another process"):
                cli._acquire_advisory_lock(descriptor, path.parent / ".gitignore")
            observed = True
        finally:
            os.close(descriptor)

    monkeypatch.setattr(cli, "_transaction_hook", assert_contended)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 0
    assert observed


@pytest.mark.parametrize(
    "initial",
    [b"dist/\n", b"dist/\n/.release-gate/runs/\n"],
    ids=["append", "existing-entry-no-op"],
)
@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows denies replacing an open locked file; contention is covered",
)
def test_init_rejects_ignore_replacement_at_publication_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    initial: bytes,
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(initial)

    def replace_ignore(event: str, path: Path) -> None:
        if event != "before-policy-publish":
            return
        replacement = path.parent / "replacement-ignore"
        replacement.write_bytes(b"concurrent replacement\n")
        os.replace(replacement, path.parent / ".gitignore")

    monkeypatch.setattr(cli, "_transaction_hook", replace_ignore)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert ignore.read_bytes() == b"concurrent replacement\n"
    assert not (tmp_path / ".release-gate.yaml").exists()


def test_init_rejects_ignore_byte_change_at_publication_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(b"dist/\n")

    def append_without_lock(event: str, path: Path) -> None:
        if event == "before-policy-publish":
            with (path.parent / ".gitignore").open("ab") as stream:
                stream.write(b"concurrent bytes\n")

    monkeypatch.setattr(cli, "_transaction_hook", append_without_lock)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert ignore.read_bytes() == (b"dist/\n/.release-gate/runs/\nconcurrent bytes\n")
    assert not (tmp_path / ".release-gate.yaml").exists()


def test_init_fails_safely_when_ignore_lock_is_contended(tmp_path: Path) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(b"owned\n")
    descriptor = os.open(ignore, os.O_RDWR)
    cli._acquire_advisory_lock(descriptor, ignore)
    try:
        assert (
            main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
        )
    finally:
        cli._release_advisory_lock(descriptor)
        os.close(descriptor)
    assert ignore.read_bytes() == b"owned\n"
    assert not (tmp_path / ".release-gate.yaml").exists()


def test_init_rolls_back_policy_and_ignore_after_append_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(b"dist/\n")

    def fail_after_ignore_write(event: str, path: Path) -> None:
        del path
        if event == "after-ignore-write":
            raise OSError("injected append failure")

    monkeypatch.setattr(
        cli, "_transaction_hook", fail_after_ignore_write, raising=False
    )
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert ignore.read_bytes() == b"dist/\n"
    assert not (tmp_path / ".release-gate.yaml").exists()


def test_init_preserves_concurrent_data_when_ignore_rollback_proof_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(b"dist/\n")

    def append_later_data_then_fail(event: str, path: Path) -> None:
        if event == "after-ignore-write":
            with path.open("ab") as stream:
                stream.write(b"later writer\n")
            raise OSError("injected append failure")

    monkeypatch.setattr(
        cli, "_transaction_hook", append_later_data_then_fail, raising=False
    )
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert ignore.read_bytes() == (b"dist/\n/.release-gate/runs/\nlater writer\n")
    assert not (tmp_path / ".release-gate.yaml").exists()


def test_init_rechecks_after_rollback_hook_before_truncating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(b"dist/\n")

    def fail_then_append_at_rollback_boundary(event: str, path: Path) -> None:
        if event == "before-policy-publish":
            raise OSError("injected publication failure")
        if event == "before-ignore-rollback":
            with (path.parent / ".gitignore").open("ab") as stream:
                stream.write(b"later writer\n")

    monkeypatch.setattr(cli, "_transaction_hook", fail_then_append_at_rollback_boundary)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert ignore.read_bytes() == (b"dist/\n/.release-gate/runs/\nlater writer\n")
    assert not (tmp_path / ".release-gate.yaml").exists()


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows denies replacing an open locked file; contention is covered",
)
def test_init_preserves_replacement_at_rollback_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(b"dist/\n")

    def fail_then_replace_at_rollback(event: str, path: Path) -> None:
        if event == "before-policy-publish":
            raise OSError("injected publication failure")
        if event == "before-ignore-rollback":
            replacement = path.parent / "replacement"
            replacement.write_bytes(b"later replacement\n")
            os.replace(replacement, path.parent / ".gitignore")

    monkeypatch.setattr(cli, "_transaction_hook", fail_then_replace_at_rollback)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert ignore.read_bytes() == b"later replacement\n"
    assert not (tmp_path / ".release-gate.yaml").exists()


def test_init_rolls_back_partial_ignore_append_through_locked_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(b"dist/\n")
    real_write_all = cli._write_all

    def fail_partial_write(
        descriptor: int, data: bytes, journal: cli._WriteJournal
    ) -> None:
        if data == cli._EVIDENCE_IGNORE_BYTES:
            journal.written = os.write(descriptor, data[:4])
            raise OSError("injected partial write")
        real_write_all(descriptor, data, journal)

    monkeypatch.setattr(cli, "_write_all", fail_partial_write)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert ignore.read_bytes() == b"dist/\n"
    assert not (tmp_path / ".release-gate.yaml").exists()


def test_init_never_rolls_back_concurrently_published_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    ignore = tmp_path / ".gitignore"
    ignore.write_bytes(b"dist/\n")
    policy = tmp_path / ".release-gate.yaml"

    def publish_other_policy(event: str, path: Path) -> None:
        if event == "before-policy-publish":
            path.write_bytes(b"later owner\n")

    monkeypatch.setattr(cli, "_transaction_hook", publish_other_policy)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert policy.read_bytes() == b"later owner\n"
    assert ignore.read_bytes() == b"dist/\n"


def test_init_keeps_created_empty_ignore_when_safe_unlink_cannot_be_proven(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)

    def fail_publication(event: str, path: Path) -> None:
        del path
        if event == "before-policy-publish":
            raise OSError("injected publication failure")

    monkeypatch.setattr(cli, "_transaction_hook", fail_publication)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert (tmp_path / ".gitignore").read_bytes() == b""
    assert not (tmp_path / ".release-gate.yaml").exists()
    assert list(tmp_path.glob(".release-gate-init-*")) == []


def test_init_stage_cleanup_preserves_unproven_concurrent_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)

    def add_unproven_stage_file_then_fail(event: str, path: Path) -> None:
        if event != "before-ignore-write":
            return
        stages = list(path.parent.glob(".release-gate-init-*"))
        assert len(stages) == 1
        (stages[0] / "concurrent").write_bytes(b"preserve me\n")
        raise OSError("injected failure")

    monkeypatch.setattr(cli, "_transaction_hook", add_unproven_stage_file_then_fail)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    stages = list(tmp_path.glob(".release-gate-init-*"))
    assert len(stages) == 1
    assert (stages[0] / "concurrent").read_bytes() == b"preserve me\n"
    assert not (stages[0] / "policy").exists()
    assert not (tmp_path / ".release-gate.yaml").exists()
    assert not (tmp_path / ".gitignore").exists()


def test_init_stage_cleanup_never_removes_replacement_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    moved_stage: Path | None = None

    def replace_stage_directory(event: str, path: Path) -> None:
        nonlocal moved_stage
        if event != "before-stage-rmdir":
            return
        moved_stage = path.with_name(f"{path.name}-moved")
        os.replace(path, moved_stage)
        path.mkdir()

    monkeypatch.setattr(cli, "_transaction_hook", replace_stage_directory)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 0
    assert moved_stage is not None
    assert moved_stage.is_dir()
    replacement_stages = [
        path for path in tmp_path.glob(".release-gate-init-*") if path != moved_stage
    ]
    assert len(replacement_stages) == 1
    assert replacement_stages[0].is_dir()
    assert list(replacement_stages[0].iterdir()) == []
    assert (tmp_path / ".release-gate.yaml").read_bytes() == _VALID_POLICY


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows denies replacing the pinned open staging file",
)
def test_init_rejects_replaced_policy_stage_source_and_preserves_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)
    replacement_bytes = b"concurrent staged data\n"

    def replace_staged_policy(event: str, path: Path) -> None:
        if event != "before-policy-publish":
            return
        stages = list(path.parent.glob(".release-gate-init-*"))
        assert len(stages) == 1
        replacement = stages[0] / "replacement"
        replacement.write_bytes(replacement_bytes)
        os.replace(replacement, stages[0] / "policy")

    monkeypatch.setattr(cli, "_transaction_hook", replace_staged_policy)
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    stages = list(tmp_path.glob(".release-gate-init-*"))
    assert len(stages) == 1
    assert (stages[0] / "policy").read_bytes() == replacement_bytes
    assert not (tmp_path / ".release-gate.yaml").exists()
    assert (tmp_path / ".gitignore").read_bytes() == b""


def test_init_preserves_policy_when_policy_rollback_proof_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)

    def replace_policy_then_fail(event: str, path: Path) -> None:
        if event == "before-ignore-write":
            policy = path.parent / ".release-gate.yaml"
            policy.write_bytes(b"later owner\n")
            raise OSError("injected append failure")

    monkeypatch.setattr(
        cli, "_transaction_hook", replace_policy_then_fail, raising=False
    )
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert (tmp_path / ".release-gate.yaml").read_bytes() == b"later owner\n"
    assert not (tmp_path / ".gitignore").exists()


def test_init_rechecks_policy_and_rolls_back_ignore_after_unproven_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "approved.yaml"
    source.write_bytes(_VALID_POLICY)

    def replace_policy_without_raising(event: str, path: Path) -> None:
        if event == "before-ignore-write":
            (path.parent / ".release-gate.yaml").write_bytes(b"later owner\n")

    monkeypatch.setattr(
        cli, "_transaction_hook", replace_policy_without_raising, raising=False
    )
    assert main(["init", "--repo", str(tmp_path), "--from-config", str(source)]) == 3
    assert (tmp_path / ".release-gate.yaml").read_bytes() == b"later owner\n"
    assert not (tmp_path / ".gitignore").exists()


def test_init_refuses_to_overwrite_existing_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del capsys
    policy = tmp_path / ".release-gate.yaml"
    policy.write_text("owned by user\n", encoding="utf-8")

    assert main(["init", "--repo", str(tmp_path)]) == 3
    assert policy.read_text(encoding="utf-8") == "owned by user\n"


def test_validate_reads_working_copy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del capsys
    assert main(["init", "--repo", str(tmp_path)]) == 0
    assert main(["validate", "--repo", str(tmp_path)]) == 0

    policy = tmp_path / ".release-gate.yaml"
    policy.write_text("version: 2\n", encoding="utf-8")
    assert main(["validate", "--repo", str(tmp_path)]) == 3


def test_validate_output_and_diagnostics_use_stable_streams(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init", "--repo", str(tmp_path)]) == 0
    capsys.readouterr()

    assert main(["validate", "--repo", str(tmp_path)]) == 0
    valid = capsys.readouterr()
    assert valid.out == f"VALID: {tmp_path / '.release-gate.yaml'}\n"
    assert valid.err == ""

    (tmp_path / ".release-gate.yaml").write_text("not: valid\n", encoding="utf-8")
    assert main(["validate", "--repo", str(tmp_path)]) == 3
    invalid = capsys.readouterr()
    assert invalid.out == ""
    assert invalid.err.startswith("ERROR: ")


def test_invalid_cli_usage_returns_exit_3(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["unknown-command"]) == 3
    result = capsys.readouterr()
    assert result.out == ""
    assert result.err.startswith("ERROR: ")
