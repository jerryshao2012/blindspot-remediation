from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "release-gate-ci.yml"
RELEASE = ROOT / ".github" / "workflows" / "release-gate-release.yml"
QUALIFICATION_DOCS = ROOT / "release-gate" / "docs" / "qualification.md"


def _workflow(path: Path) -> dict[str, object]:
    loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return loaded


def test_pr_ci_is_read_only_secret_free_and_keeps_full_matrix() -> None:
    workflow = _workflow(CI)
    assert workflow["permissions"] == {"contents": "read"}
    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-latest", "macos-latest", "windows-latest"]
    assert matrix["python"] == ["3.11", "3.12", "3.13"]
    text = CI.read_text(encoding="utf-8")
    assert "secrets." not in text
    assert "contents: write" not in text
    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" in text
    assert "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b" in text
    assert 'version: "0.12.5"' in text
    assert "uv sync --all-groups --locked" in text
    assert "actions/checkout@v" not in text
    assert "astral-sh/setup-uv@v" not in text


def test_release_workflow_separates_build_from_protected_writes() -> None:
    workflow = _workflow(RELEASE)
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    for name in ("build-rc", "validate-promotion"):
        assert jobs[name].get("permissions", {"contents": "read"}) == {
            "contents": "read"
        }
        assert "environment" not in jobs[name]
    for name in ("publish-rc", "publish-final"):
        assert jobs[name]["permissions"] == {"contents": "write"}
        assert jobs[name]["environment"] == "release-gate-production"
    assert workflow["concurrency"] == {
        "group": "release-gate-v0.2.0",
        "cancel-in-progress": "false",
    }


def test_write_token_jobs_never_execute_or_checkout_candidate_code() -> None:
    workflow = _workflow(RELEASE)
    for name in ("publish-rc", "publish-final"):
        job = workflow["jobs"][name]
        uses = [step.get("uses", "") for step in job["steps"]]
        assert all(
            "checkout" not in action and "setup-uv" not in action for action in uses
        )
        scripts = "\n".join(step.get("run", "") for step in job["steps"])
        for forbidden in ("uv run", "python ", "release-gate/scripts", "git checkout"):
            assert forbidden not in scripts
        assert "sha256sum" in scripts
        assert "gh api" in scripts
        assert "releases/tags/" not in scripts
        assert "gh release download" not in scripts
        assert "--paginate" in scripts
        assert "release_id" in scripts
        assert "releases/$release_id/assets" in scripts
        assert "uploads.github.com" in scripts
        assert "curl --fail-with-body --silent --show-error" in scripts
        assert "--hostname uploads.github.com" not in scripts
        assert "api.uploads.github.com" not in scripts
        assert "Authorization: Bearer $GH_TOKEN" in scripts
        assert '--data-binary @"$asset"' in scripts
        assert "--method PATCH" in scripts
    for name in ("build-rc", "validate-promotion"):
        checkout = next(
            step
            for step in workflow["jobs"][name]["steps"]
            if "checkout" in step.get("uses", "")
        )
        assert checkout["with"]["persist-credentials"] == "false"


def test_all_actions_are_pinned_to_reviewed_immutable_commits() -> None:
    allowed = {
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
        "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b",
    }
    for path in (CI, RELEASE):
        workflow = _workflow(path)
        for job in workflow["jobs"].values():
            for step in job["steps"]:
                if "uses" in step:
                    assert step["uses"] in allowed


def test_run_scripts_never_interpolate_untrusted_workflow_inputs() -> None:
    workflow = _workflow(RELEASE)
    for job_name, job in workflow["jobs"].items():
        for step in job["steps"]:
            if "run" in step:
                assert "${{ inputs." not in step["run"], (
                    f"{job_name} interpolates workflow input directly in a run script"
                )
    build = workflow["jobs"]["build-rc"]
    assert "rc_commit" in build["outputs"]
    publish = workflow["jobs"]["publish-rc"]
    assert "needs.build-rc.outputs.rc_commit" in str(publish)


def test_every_workflow_shell_script_passes_bash_syntax_check() -> None:
    for path in (CI, RELEASE):
        workflow = _workflow(path)
        for job_name, job in workflow["jobs"].items():
            for step in job["steps"]:
                if "run" not in step:
                    continue
                script = re.sub(r"\$\{\{.*?\}\}", "github-expression", step["run"])
                result = subprocess.run(
                    ["bash", "-n"],
                    input=script,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                assert result.returncode == 0, f"{job_name}: {result.stderr}"


def test_docs_require_real_github_environment_protection() -> None:
    docs = " ".join(QUALIFICATION_DOCS.read_text(encoding="utf-8").split()).casefold()
    for phrase in (
        "required reviewers",
        "prevent self-review",
        "deployment branch",
        "trusted default branch",
        "exact commit",
        "exact artifact",
    ):
        assert phrase in docs


def test_promotion_reuses_rc_assets_and_never_deletes_or_rebuilds() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    promotion = text.split("validate-promotion:", 1)[1]
    assert "gh release download release-gate-v0.2.0-rc.1" in promotion
    assert "validate_qualification.py" in promotion
    assert "verify_release_assets.py" in promotion
    assert "build_release_assets.py" not in promotion
    assert "gh release delete" not in text
    assert "git tag -d" not in text
    assert "release-gate-v0.2.0" in promotion
    assert "release-gate-v0.2.0-rc.1" in promotion
    assert "-F draft=true" in text
    assert "--clobber" not in text
    assert "concurrency:" in text
    assert "compare/" in text
    assert "manifest_sha256" in text
    assert "-F prerelease=true" in text
    assert "-F prerelease=false" in text
    assert (
        'test "$(gh api "repos/$GITHUB_REPOSITORY/'
        'releases/tags/$RC_TAG" --jq .prerelease)" = true' in promotion
    )
