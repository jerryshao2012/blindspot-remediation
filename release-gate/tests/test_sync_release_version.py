from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from release_gate import __version__

PRODUCT = Path(__file__).resolve().parents[1]
REPOSITORY = PRODUCT.parent
SCRIPT = PRODUCT / "scripts" / "sync_release_version.py"
CI = REPOSITORY / ".github" / "workflows" / "release-gate-ci.yml"


def _run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def _copy_checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    shutil.copytree(
        PRODUCT,
        checkout / "release-gate",
        ignore=shutil.ignore_patterns(
            ".venv",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
            "dist",
            "workbench",
        ),
    )
    workflows = checkout / ".github" / "workflows"
    workflows.mkdir(parents=True)
    for name in ("release-gate-ci.yml", "release-gate-release.yml"):
        shutil.copyfile(REPOSITORY / ".github" / "workflows" / name, workflows / name)
    return checkout


def test_release_version_check_passes_for_the_repository() -> None:
    result = _run(REPOSITORY, "--check")

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"RELEASE VERSION IN SYNC: {__version__}\n"
    assert result.stderr == ""


def test_release_version_check_reports_drift_without_writing(tmp_path: Path) -> None:
    checkout = _copy_checkout(tmp_path)
    compatibility = (
        checkout
        / "release-gate"
        / "skills"
        / "release-gate"
        / "references"
        / "compatibility.json"
    )
    drifted = compatibility.read_text(encoding="utf-8").replace(
        __version__, "9.9.9"
    )
    compatibility.write_text(drifted, encoding="utf-8")

    result = _run(checkout, "--check")

    assert result.returncode != 0
    assert "release version drift" in result.stderr
    assert "compatibility.json" in result.stderr
    assert "run scripts/sync_release_version.py" in result.stderr
    assert compatibility.read_text(encoding="utf-8") == drifted


def test_release_version_sync_repairs_drift_and_renames_template(
    tmp_path: Path,
) -> None:
    checkout = _copy_checkout(tmp_path)
    qualification = checkout / "release-gate" / "qualification"
    current = qualification / f"release-gate-v{__version__}-rc.1.pending.json"
    stale = qualification / "release-gate-v9.9.9-rc.1.pending.json"
    stale.write_text(
        current.read_text(encoding="utf-8").replace(__version__, "9.9.9"),
        encoding="utf-8",
    )
    current.unlink()
    compatibility = (
        checkout
        / "release-gate"
        / "skills"
        / "release-gate"
        / "references"
        / "compatibility.json"
    )
    compatibility.write_text(
        compatibility.read_text(encoding="utf-8").replace(__version__, "9.9.9"),
        encoding="utf-8",
    )

    result = _run(checkout)

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"SYNCHRONIZED RELEASE VERSION: {__version__}\n"
    assert current.exists()
    assert not stale.exists()
    assert "9.9.9" not in current.read_text(encoding="utf-8")
    assert __version__ in compatibility.read_text(encoding="utf-8")
    checked = _run(checkout, "--check")
    assert checked.returncode == 0, checked.stderr


def test_release_version_sync_propagates_a_new_canonical_version(
    tmp_path: Path,
) -> None:
    checkout = _copy_checkout(tmp_path)
    canonical = checkout / "release-gate" / "src" / "release_gate" / "__init__.py"
    next_version = "9.9.9"
    canonical.write_text(
        canonical.read_text(encoding="utf-8").replace(__version__, next_version),
        encoding="utf-8",
    )
    historical = (
        "\n## Historical migration example\n\n"
        "Keep release-gate-v0.1.7, release_gate-0.1.7-py3-none-any.whl, and "
        "release-gate 0.1.7 unchanged.\n"
    )
    historical_files = (
        checkout / "release-gate" / "README.md",
        checkout / "release-gate" / "docs" / "adoption.md",
    )
    for historical_file in historical_files:
        historical_file.write_text(
            historical_file.read_text(encoding="utf-8") + historical,
            encoding="utf-8",
        )

    result = _run(checkout)

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"SYNCHRONIZED RELEASE VERSION: {next_version}\n"
    for relative in (
        ".github/workflows/release-gate-ci.yml",
        ".github/workflows/release-gate-release.yml",
        "release-gate/README.md",
        "release-gate/demo/python-slugify/README.md",
        "release-gate/docs/adoption.md",
        "release-gate/docs/cli.md",
        "release-gate/docs/qualification.md",
        "release-gate/demo/python-slugify/demo.py",
        "release-gate/scripts/build_release_assets.py",
        "release-gate/scripts/smoke_installed.py",
        "release-gate/scripts/validate_qualification.py",
        "release-gate/skills/release-gate/SKILL.md",
        "release-gate/skills/release-gate/references/compatibility.json",
    ):
        text = (checkout / relative).read_text(encoding="utf-8")
        assert next_version in text, relative
        if "<!-- release-version-sync:start -->" in text:
            current = text.split("<!-- release-version-sync:start -->", 1)[1]
            current = current.split("<!-- release-version-sync:end -->", 1)[0]
            assert __version__ not in current, relative
        else:
            assert __version__ not in text, relative
    for historical_file in historical_files:
        assert historical_file.read_text(encoding="utf-8").endswith(historical)
    qualification = checkout / "release-gate" / "qualification"
    assert (qualification / f"release-gate-v{next_version}-rc.1.pending.json").exists()


def test_release_version_sync_adds_heading_without_rewriting_release_history(
    tmp_path: Path,
) -> None:
    checkout = _copy_checkout(tmp_path)
    canonical = checkout / "release-gate" / "src" / "release_gate" / "__init__.py"
    changelog = checkout / "release-gate" / "CHANGELOG.md"
    original = changelog.read_text(encoding="utf-8")
    current_heading = f"## {__version__}\n"
    preamble, prior_releases = original.split(current_heading, 1)
    prior_releases = current_heading + prior_releases
    next_version = "9.9.9"
    canonical.write_text(
        canonical.read_text(encoding="utf-8").replace(__version__, next_version),
        encoding="utf-8",
    )

    checked = _run(checkout, "--check")

    assert checked.returncode != 0
    assert "release-gate/CHANGELOG.md" in checked.stderr
    assert changelog.read_text(encoding="utf-8") == original

    result = _run(checkout)

    assert result.returncode == 0, result.stderr
    repaired = changelog.read_text(encoding="utf-8")
    assert repaired == preamble + f"## {next_version}\n\n" + prior_releases
    assert prior_releases in repaired


def test_readme_documents_the_single_source_release_bump_workflow() -> None:
    readme = (PRODUCT / "README.md").read_text(encoding="utf-8")
    normalized = " ".join(readme.split())

    for phrase in (
        "edit only `src/release_gate/__init__.py::__version__`",
        "`uv run python scripts/sync_release_version.py`",
        "review the generated changes and release notes",
        "`uv run python scripts/sync_release_version.py --check`",
        "CI",
    ):
        assert phrase.casefold() in normalized.casefold()


def test_release_version_check_rejects_missing_or_extra_sync_markers(
    tmp_path: Path,
) -> None:
    mutations = ("marker-missing", "marker-extra", "target-missing", "target-extra")
    for mutation in mutations:
        checkout = _copy_checkout(tmp_path / mutation)
        readme = checkout / "release-gate" / "README.md"
        text = readme.read_text(encoding="utf-8")
        start = "<!-- release-version-sync:start -->"
        end = "<!-- release-version-sync:end -->"
        assert text.count(start) == 1
        if mutation == "marker-missing":
            text = text.replace(start, "", 1)
        elif mutation == "marker-extra":
            text += f"\n{start}\n{end}\n"
        elif mutation == "target-missing":
            text = text.replace(
                f"release-gate-v{__version__}", "release-gate-current", 1
            )
        else:
            text = text.replace(end, f"release-gate-v{__version__}\n{end}", 1)
        readme.write_text(text, encoding="utf-8")

        result = _run(checkout, "--check")

        assert result.returncode == 2
        if mutation.startswith("marker"):
            assert "expected exactly one release version sync block" in result.stderr
        else:
            assert "release version targets" in result.stderr
        assert "release-gate/README.md" in result.stderr


def test_release_version_check_rejects_missing_or_extra_anchored_targets(
    tmp_path: Path,
) -> None:
    for mutation in ("missing", "extra"):
        checkout = _copy_checkout(tmp_path / mutation)
        workflow = checkout / ".github" / "workflows" / "release-gate-ci.yml"
        text = workflow.read_text(encoding="utf-8")
        target = f"release-gate-v{__version__}"
        if mutation == "missing":
            text = text.replace(target, "release-gate-current", 1)
        else:
            text += f"\n# unexpected current target: {target}\n"
        workflow.write_text(text, encoding="utf-8")

        result = _run(checkout, "--check")

        assert result.returncode == 2
        assert "expected 2 release version targets" in result.stderr
        assert ".github/workflows/release-gate-ci.yml" in result.stderr


def test_ci_checks_generated_release_version_surfaces() -> None:
    text = CI.read_text(encoding="utf-8")
    assert "python scripts/sync_release_version.py --check" in text
