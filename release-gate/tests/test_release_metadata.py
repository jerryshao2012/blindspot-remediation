from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from release_gate import __version__

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/jerryshao2012/blindspot-remediation"
RELEASE_TAG = "release-gate-v0.2.2"
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
