from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from release_gate import __version__

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/jerryshao2012/blindspot-remediation"
RELEASE_TAG = f"release-gate-v{__version__}"
SKILLS_VERSION = "1.5.23"
HOST_AGENTS = {
    "copilot": "github-copilot",
    "codex": "codex",
    "claude-code": "claude-code",
    "antigravity": "antigravity",
}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_package_metadata_uses_the_license_file_and_authoritative_urls() -> None:
    pyproject = tomllib.loads(_read("pyproject.toml"))
    metadata = pyproject["project"]

    assert metadata["dynamic"] == ["version"]
    assert metadata["requires-python"] == ">=3.11,<3.14"
    assert pyproject["tool"]["hatch"]["version"] == {
        "path": "src/release_gate/__init__.py"
    }
    assert metadata["license"] == {"file": "LICENSE"}
    assert metadata["urls"] == {
        "Homepage": f"{REPOSITORY}/tree/main/release-gate",
        "Repository": REPOSITORY,
        "Documentation": f"{REPOSITORY}/tree/main/release-gate/docs",
        "Issues": f"{REPOSITORY}/issues",
        "Support": f"{REPOSITORY}/issues",
        "Security": f"{REPOSITORY}/security/advisories/new",
    }


def test_version_agrees_across_release_metadata() -> None:
    assert __version__ == "0.3.0"
    compatibility = json.loads(
        _read("skills/release-gate/references/compatibility.json")
    )

    assert compatibility == {"cli": {"name": "release-gate", "version": __version__}}
    changelog = _read("CHANGELOG.md")
    assert f"## {__version__}\n" in changelog
    assert "qualifies `release-gate-v0.2.0-rc.1`" in changelog
    assert "byte-identical final promotion" in changelog
    assert "GitHub release page is authoritative" in changelog
    assert "pending release" not in changelog


def test_observability_behavior_is_documented_across_public_surfaces() -> None:
    text = " ".join(
        "\n".join(
            _read(path)
            for path in (
                "README.md",
                "docs/adoption.md",
                "docs/cli.md",
                "docs/design.md",
                "docs/evidence.md",
            )
        ).split()
    )
    for phrase in (
        "exit 0, 1, or 2",
        "partial warm-up windows",
        "latest 100",
        "199",
        "custom `--output`",
        "shared scope",
        "_observability/index.html",
        "_observability/gate-decisions-v1.json",
        "observability/gate-decisions.html",
        "mutable",
        "tamper-evident",
        "SNAPSHOT:",
        "DASHBOARD:",
        "OBSERVABILITY_DATA:",
        "stdout",
        "stderr",
        "non-gating",
    ):
        assert phrase.casefold() in text.casefold()


def test_installed_smoke_checks_the_observability_schema() -> None:
    smoke = _read("scripts/smoke_installed.py")
    assert "gate-decisions-v1.schema.json" in smoke
    assert "Draft202012Validator.check_schema" in smoke


def test_current_release_workflows_and_qualification_use_package_version() -> None:
    rc_tag = f"release-gate-v{__version__}-rc.1"
    final_tag = f"release-gate-v{__version__}"
    template_name = f"{rc_tag}.pending.json"
    current_surfaces = {
        "release workflow": _read("../.github/workflows/release-gate-release.yml"),
        "CI workflow": _read("../.github/workflows/release-gate-ci.yml"),
        "qualification docs": _read("docs/qualification.md"),
        "asset builder": _read("scripts/build_release_assets.py"),
        "qualification validator": _read("scripts/validate_qualification.py"),
    }

    for name, text in current_surfaces.items():
        assert "release-gate-v0.2.0" not in text, name
        assert "v0.2.0" not in text, name

    assert rc_tag in current_surfaces["release workflow"]
    assert final_tag in current_surfaces["release workflow"]
    assert template_name in current_surfaces["CI workflow"]
    assert rc_tag in current_surfaces["qualification docs"]
    assert final_tag in current_surfaces["qualification docs"]
    assert f"v{__version__}" in current_surfaces["asset builder"]
    assert f"v{__version__}" in current_surfaces["qualification validator"]

    template_path = ROOT / "qualification" / template_name
    assert template_path.exists()
    assert not (
        ROOT / "qualification" / "release-gate-v0.2.0-rc.1.pending.json"
    ).exists()
    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert template["release"]["tag"] == rc_tag
    for asset in template["assets"]:
        if asset["name"] != "SHA256SUMS":
            assert __version__ in asset["name"]


def test_build_backend_and_uv_are_exactly_locked() -> None:
    pyproject = tomllib.loads(_read("pyproject.toml"))
    assert pyproject["build-system"]["requires"] == ["hatchling==1.32.0"]
    assert "hatchling==1.32.0" in pyproject["dependency-groups"]["dev"]
    lock = _read("uv.lock")
    assert 'name = "hatchling"\nversion = "1.32.0"' in lock
    assert "--no-isolation" in _read("scripts/build_release_assets.py")
    root_ignore = (ROOT.parent / ".gitignore").read_text(encoding="utf-8")
    assert "!release-gate/uv.lock" in root_ignore


def test_install_docs_bound_checksums_to_release_assets_not_dependencies() -> None:
    release_docs = " ".join(
        "\n".join((_read("README.md"), _read("docs/adoption.md"))).split()
    )

    assert "checksum covers the Release Gate wheel itself" in release_docs
    assert "resolves the declared dependency ranges" in release_docs
    assert "outside the release asset checksum" in release_docs
    assert "development `uv.lock` is not consumed" in release_docs


def test_release_documents_pin_both_installations_and_every_host_archive() -> None:
    release_docs = "\n".join((_read("README.md"), _read("docs/adoption.md")))

    wheel = f"release_gate-{__version__.replace('.', '_')}-py3-none-any.whl"
    # The wheel filename uses dots in its version; keep the assertion separate
    # from the archive loop so a package/archive mismatch is easy to diagnose.
    assert f"release_gate-{__version__}-py3-none-any.whl" in release_docs
    assert wheel not in release_docs
    assert f"releases/download/{RELEASE_TAG}" in release_docs
    assert f"skills@{SKILLS_VERSION}" in release_docs
    assert "--global" in release_docs
    assert "--copy" in release_docs
    assert "Node.js 22.20" in release_docs
    assert "sha256" in release_docs.lower()

    for host, agent in HOST_AGENTS.items():
        archive = f"release-gate-skill-{host}-{__version__}.tar.gz"
        archive_url = f"{REPOSITORY}/releases/download/{RELEASE_TAG}/{archive}"
        assert archive_url in release_docs
        assert (
            f"skills@{SKILLS_VERSION} add {archive_url} --global --copy --agent {agent}"
        ) in release_docs
    assert "--agent antigravity-cli" in release_docs


def test_install_examples_are_gated_on_publication_and_explain_redownload() -> None:
    release_docs = "\n".join((_read("README.md"), _read("docs/adoption.md")))
    normalized = " ".join(release_docs.split())

    assert "only after the final GitHub release is published" in release_docs
    assert "do not claim that those assets are currently available" in normalized
    assert "may download the URL again" in release_docs
    assert "qualification and publication are blocked" in normalized.casefold()


def test_upgrade_commands_remove_then_install_verified_pinned_artifacts() -> None:
    adoption = _read("docs/adoption.md")
    wheel = f"release_gate-{__version__}-py3-none-any.whl"
    wheel_url = f"{REPOSITORY}/releases/download/{RELEASE_TAG}/{wheel}"

    assert f"curl --fail --location --remote-name {wheel_url}" in adoption
    assert "uv tool uninstall release-gate\nuv tool install ./" + wheel in adoption
    for host, agent in HOST_AGENTS.items():
        archive = f"release-gate-skill-{host}-{__version__}.tar.gz"
        archive_url = f"{REPOSITORY}/releases/download/{RELEASE_TAG}/{archive}"
        assert (
            f"remove release-gate --global --agent {agent} --yes\n"
            f"npx --yes skills@{SKILLS_VERSION} add {archive_url} "
            f"--global --copy --agent {agent}"
        ) in adoption


def test_readme_documents_safe_updates_for_every_host() -> None:
    readme = _read("README.md")
    heading = "## Updating an existing installation"

    assert heading in readme
    upgrade = readme.split(heading, 1)[1].split("Invoke the skill explicitly", 1)[0]
    normalized = " ".join(upgrade.split())
    wheel = f"release_gate-{__version__}-py3-none-any.whl"

    for phrase in (
        "only after the final GitHub release is published",
        "Retain the previous wheel, host archive, and `SHA256SUMS`",
        "Never self-update or use an unpinned `skills update`",
        "Do not invoke Release Gate while the skill and CLI versions differ",
        "After verifying the new wheel and exactly one host archive, run exactly one "
        "matching host block",
        "Resume only when the bundled skill version and executable version match",
    ):
        assert phrase.casefold() in normalized.casefold()

    procedure = (
        "[checksum-first upgrade and rollback procedure]"
        "(docs/adoption.md#upgrade-uninstall-and-rollback)"
    )
    assert procedure in upgrade
    assert "## Upgrade, uninstall, and rollback" in _read("docs/adoption.md")

    host_targets = (
        ("GitHub Copilot CLI", "github-copilot", "copilot"),
        ("Codex CLI and IDE", "codex", "codex"),
        ("Claude Code", "claude-code", "claude-code"),
        ("Antigravity IDE", "antigravity", "antigravity"),
        ("Antigravity CLI", "antigravity-cli", "antigravity"),
    )
    block_positions: list[int] = []
    for label, agent, archive_host in host_targets:
        archive = f"release-gate-skill-{archive_host}-{__version__}.tar.gz"
        archive_url = f"{REPOSITORY}/releases/download/{RELEASE_TAG}/{archive}"
        block = (
            "```bash\n"
            f"# {label}\n"
            f"npx --yes skills@{SKILLS_VERSION} remove release-gate "
            f"--global --agent {agent} --yes\n"
            f"npx --yes skills@{SKILLS_VERSION} add {archive_url} "
            f"--global --copy --agent {agent}\n"
            f"npx --yes skills@{SKILLS_VERSION} list --global --agent {agent}\n"
            "```"
        )
        assert block in upgrade
        block_positions.append(upgrade.index(block))
    assert block_positions == sorted(block_positions)

    cli_block = (
        "```bash\n"
        "uv tool uninstall release-gate\n"
        f"uv tool install ./{wheel}\n"
        "release-gate --version\n"
        f"# required output: release-gate {__version__}\n"
        "```"
    )
    assert cli_block in upgrade
    assert "/release-gate --version" in upgrade
    assert "$release-gate --version" in upgrade

    uninstall_position = upgrade.index("uv tool uninstall release-gate")
    assert all(position < uninstall_position for position in block_positions)

    cli_end = upgrade.index(cli_block) + len(cli_block)
    slash_check_position = upgrade.index("`/release-gate --version`")
    dollar_check_position = upgrade.index("`$release-gate --version`")
    assert cli_end < slash_check_position
    assert cli_end < dollar_check_position

    resume_position = upgrade.index("Resume only when the bundled skill version")
    assert slash_check_position < resume_position
    assert dollar_check_position < resume_position


def test_assistant_version_syntax_is_documented_as_informational() -> None:
    readme = _read("README.md")
    adoption = _read("docs/adoption.md")

    for text in (readme, adoption):
        assert "/release-gate --version" in text
        assert "$release-gate --version" in text
        assert f"release-gate {__version__}" in text
        assert "does not call the CLI" in text
    assert "underlying CLI output" in adoption


def test_upgrade_retains_and_verifies_both_pairs_before_removal() -> None:
    adoption = _read("docs/adoption.md")
    upgrade = adoption.split("## Upgrade, uninstall, and rollback", 1)[1]
    normalized = " ".join(upgrade.split())
    wheel = f"release_gate-{__version__}-py3-none-any.whl"

    for phrase in (
        "Retain the prior wheel, host archive, and `SHA256SUMS`",
        "exactly one archive for the host target",
        "before removing or replacing anything",
        "verified local wheel",
        "never from a package index",
        f"release-gate {__version__}",
        "Do not invoke Release Gate while the skill and CLI versions differ",
        "rollback to the retained prior pair",
        "Never use self-update",
        "never use an unpinned `skills update`",
    ):
        assert phrase.casefold() in normalized.casefold()

    manifest_url = f"{REPOSITORY}/releases/download/{RELEASE_TAG}/SHA256SUMS"
    wheel_url = f"{REPOSITORY}/releases/download/{RELEASE_TAG}/{wheel}"
    assert f"curl --fail --location --remote-name {manifest_url}" in upgrade
    assert f"curl --fail --location --remote-name {wheel_url}" in upgrade
    assert upgrade.index(manifest_url) < upgrade.index("remove release-gate")
    assert upgrade.index(wheel_url) < upgrade.index("remove release-gate")

    for host, agent in HOST_AGENTS.items():
        archive = f"release-gate-skill-{host}-{__version__}.tar.gz"
        archive_url = f"{REPOSITORY}/releases/download/{RELEASE_TAG}/{archive}"
        assert upgrade.index(archive_url) < upgrade.index(
            f"remove release-gate --global --agent {agent} --yes"
        )
    assert "--agent antigravity-cli --yes" in upgrade
    assert "skills list" in upgrade


def test_upgrade_checksum_commands_are_cross_platform_and_require_one_entry() -> None:
    adoption = _read("docs/adoption.md")
    upgrade = adoption.split("## Upgrade, uninstall, and rollback", 1)[1]
    verification = "uv run --no-project python -c"

    assert "grep " not in upgrade
    assert upgrade.count(verification) == 4
    for guard in (
        "all(valid_entries)",
        "all(len(matches[name]) == 1 for name in names)",
        "expected exactly one SHA256SUMS entry per asset",
        "hashlib.sha256",
        "SHA-256 mismatch",
    ):
        assert upgrade.count(guard) == 4
    wheel = f"release_gate-{__version__}-py3-none-any.whl"
    for host in HOST_AGENTS:
        archive = f"release-gate-skill-{host}-{__version__}.tar.gz"
        assert f'" {wheel} {archive}' in upgrade
    assert "PowerShell" in upgrade
    assert "macOS" in upgrade
    for document in (adoption, _read("README.md")):
        assert "On Windows" in document
        assert "Git Bash" in document
        assert "do not paste the `curl` lines into PowerShell" in document


def _documented_checksum_verifier() -> str:
    adoption = _read("docs/adoption.md")
    lines = [
        line
        for line in adoption.splitlines()
        if line.startswith("uv run --no-project python -c")
    ]
    codes: list[str] = []
    for line in lines:
        arguments = shlex.split(line)
        code_index = arguments.index("-c") + 1
        codes.append(arguments[code_index])
    assert len(codes) == 4
    assert len(set(codes)) == 1
    return codes[0]


@pytest.mark.parametrize(
    ("case", "expected_error"),
    [
        ("valid", None),
        ("duplicate", "expected exactly one SHA256SUMS entry per asset"),
        ("malformed", "invalid SHA256SUMS"),
        ("missing", "expected exactly one SHA256SUMS entry per asset"),
        ("mismatched", "SHA-256 mismatch"),
    ],
)
def test_documented_checksum_verifier_behavior(
    tmp_path: Path,
    case: str,
    expected_error: str | None,
) -> None:
    names = ("release_gate-test.whl", "release-gate-skill-test.tar.gz")
    entries: list[str] = []
    for index, name in enumerate(names):
        content = f"asset {index}\n".encode()
        (tmp_path / name).write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        entries.append(f"{digest}  {name}")

    if case == "duplicate":
        entries.append(entries[0])
    elif case == "malformed":
        entries.append("not a checksum entry")
    elif case == "missing":
        entries.pop()
    elif case == "mismatched":
        entries[0] = f"{'0' * 64}  {names[0]}"
    (tmp_path / "SHA256SUMS").write_text("\n".join(entries) + "\n", encoding="ascii")

    result = subprocess.run(
        [sys.executable, "-c", _documented_checksum_verifier(), *names],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    if expected_error is None:
        assert result.returncode == 0, result.stderr
        assert result.stdout == "".join(f"{name}: OK\n" for name in names)
        assert result.stderr == ""
    else:
        assert result.returncode != 0
        assert expected_error in result.stderr
        assert result.stdout == ""


def test_upgrade_checksum_verifiers_report_each_verified_asset_once() -> None:
    adoption = _read("docs/adoption.md")
    upgrade = adoption.split("## Upgrade, uninstall, and rollback", 1)[1]
    verifiers = [
        line
        for line in upgrade.splitlines()
        if line.startswith("uv run --no-project python -c")
    ]

    assert len(verifiers) == 4
    success = "print('\\n'.join(f'{name}: OK' for name in names))"
    for command in verifiers:
        assert command.count(success) == 1
        assert command.index("SHA-256 mismatch") < command.index(success)


def test_documented_invocations_and_lifecycle_guards_are_explicit() -> None:
    release_docs = "\n".join((_read("README.md"), _read("docs/adoption.md")))

    for invocation in (
        "/release-gate init",
        "$release-gate init",
        "/skills",
        "/release-gate validate",
        "/release-gate run",
    ):
        assert invocation in release_docs

    for required_phrase in (
        "existing PyPI project",
        "do not `uv tool install release-gate`",
        "remove",
        "rollback",
        "self-install",
        "cloud agents",
        "plugins",
    ):
        assert required_phrase.casefold() in release_docs.casefold()


def test_security_policy_points_to_private_reporting_and_avoids_false_sla() -> None:
    security = _read("SECURITY.md")
    normalized = " ".join(security.split())

    assert f"{REPOSITORY}/security/advisories/new" in security
    assert "Do not open a public issue" in normalized
    assert "response-time SLA" in security
    assert "0.2.x" in security
    assert "only supported private reporting channel" in normalized
    assert "retain the report details and retry" in normalized
    assert "contact a repository maintainer" not in security


def test_apache_license_is_complete_enough_to_identify_the_standard_text() -> None:
    license_text = _read("LICENSE")

    assert license_text.lstrip().startswith(
        "Apache License\n                           Version 2.0"
    )
    assert "http://www.apache.org/licenses/LICENSE-2.0" in license_text
    assert "END OF TERMS AND CONDITIONS" in license_text


def test_local_markdown_links_resolve() -> None:
    markdown_files = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    link_pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")

    for document in markdown_files:
        content = document.read_text(encoding="utf-8")
        prose = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        prose = re.sub(r"`[^`]*`", "", prose)
        for target in link_pattern.findall(prose):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_text = target.split("#", 1)[0]
            assert (document.parent / path_text).exists(), (
                f"broken local link in {document.relative_to(ROOT)}: {target}"
            )
