# Release Gate README Skill Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document the safe remove-and-reinstall update commands for every supported Release Gate assistant host directly in the product README.

**Architecture:** Keep `docs/adoption.md` authoritative for checksum verification and rollback, while adding a concise multi-host command section inside the README's existing release-version synchronization markers. Extend metadata tests to enforce command ordering and host/archive mapping, and increase the synchronizer's count-checked README target total for the added current-version references.

**Tech Stack:** Markdown, Python 3.11+, pytest, Ruff, mypy, Graphify

---

## File Structure

- Modify `release-gate/README.md`: add the concise update procedure and all five host command blocks.
- Modify `release-gate/tests/test_release_metadata.py`: enforce safety language, command order, host targets, archive mapping, CLI replacement, and version checks.
- Modify `release-gate/scripts/sync_release_version.py`: update only the README's expected count of synchronized release-version targets.

### Task 1: Specify the README update contract

**Files:**
- Test: `release-gate/tests/test_release_metadata.py`

- [ ] **Step 1: Write the failing test**

Add this test after `test_upgrade_commands_remove_then_install_verified_pinned_artifacts`:

```python
def test_readme_documents_safe_updates_for_every_host() -> None:
    readme = _read("README.md")
    update = readme.split("## Updating an existing installation", 1)[1]
    update = update.split("Invoke the skill explicitly", 1)[0]
    normalized = " ".join(update.split())
    wheel = f"release_gate-{__version__}-py3-none-any.whl"
    targets = {
        "github-copilot": "copilot",
        "codex": "codex",
        "claude-code": "claude-code",
        "antigravity": "antigravity",
        "antigravity-cli": "antigravity",
    }

    for phrase in (
        "only after the final GitHub release is published",
        "Retain the previous wheel, host archive, and `SHA256SUMS`",
        "Never use self-update or an unpinned `skills update`",
        "complete checksum-first upgrade and rollback procedure",
        "Do not invoke Release Gate while the skill and CLI versions differ",
    ):
        assert phrase.casefold() in normalized.casefold()

    for agent, host in targets.items():
        archive = f"release-gate-skill-{host}-{__version__}.tar.gz"
        archive_url = f"{REPOSITORY}/releases/download/{RELEASE_TAG}/{archive}"
        commands = (
            f"npx --yes skills@{SKILLS_VERSION} remove release-gate "
            f"--global --agent {agent} --yes\n"
            f"npx --yes skills@{SKILLS_VERSION} add {archive_url} "
            f"--global --copy --agent {agent}\n"
            f"npx --yes skills@{SKILLS_VERSION} list --global --agent {agent}"
        )
        assert commands in update

    assert (
        "uv tool uninstall release-gate\n"
        f"uv tool install ./{wheel}\n"
        "release-gate --version\n"
        f"# required output: release-gate {__version__}"
    ) in update
    assert "/release-gate --version" in update
    assert "$release-gate --version" in update
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
cd release-gate
uv run pytest tests/test_release_metadata.py::test_readme_documents_safe_updates_for_every_host -q
```

Expected: FAIL because `README.md` has no `## Updating an existing installation` section.

### Task 2: Add the synchronized multi-host update guide

**Files:**
- Modify: `release-gate/README.md:59-75`
- Modify: `release-gate/scripts/sync_release_version.py:35`
- Test: `release-gate/tests/test_release_metadata.py`
- Test: `release-gate/tests/test_sync_release_version.py`

- [ ] **Step 1: Add the README section**

Inside `<!-- release-version-sync:start -->`, after the initial Codex archive example and before `Invoke the skill explicitly`, add:

````markdown
## Updating an existing installation

Update only after the final GitHub release is published. Use the complete
[checksum-first upgrade and rollback procedure](docs/adoption.md#upgrade-uninstall-and-rollback)
before replacing anything. Retain the previous wheel, host archive, and
`SHA256SUMS` for rollback. Never use self-update or an unpinned `skills update`.

After verifying the new wheel and exactly one matching host archive, run only
the block for the installed host:

```bash
# GitHub Copilot CLI
npx --yes skills@1.5.23 remove release-gate --global --agent github-copilot --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.3/release-gate-skill-copilot-0.2.3.tar.gz --global --copy --agent github-copilot
npx --yes skills@1.5.23 list --global --agent github-copilot
```

```bash
# Codex CLI and IDE
npx --yes skills@1.5.23 remove release-gate --global --agent codex --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.3/release-gate-skill-codex-0.2.3.tar.gz --global --copy --agent codex
npx --yes skills@1.5.23 list --global --agent codex
```

```bash
# Claude Code
npx --yes skills@1.5.23 remove release-gate --global --agent claude-code --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.3/release-gate-skill-claude-code-0.2.3.tar.gz --global --copy --agent claude-code
npx --yes skills@1.5.23 list --global --agent claude-code
```

```bash
# Antigravity IDE
npx --yes skills@1.5.23 remove release-gate --global --agent antigravity --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.3/release-gate-skill-antigravity-0.2.3.tar.gz --global --copy --agent antigravity
npx --yes skills@1.5.23 list --global --agent antigravity
```

```bash
# Antigravity CLI
npx --yes skills@1.5.23 remove release-gate --global --agent antigravity-cli --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.3/release-gate-skill-antigravity-0.2.3.tar.gz --global --copy --agent antigravity-cli
npx --yes skills@1.5.23 list --global --agent antigravity-cli
```

The skill and CLI versions differ until both are replaced. Do not invoke
Release Gate while the skill and CLI versions differ. Replace the CLI from the
verified local wheel, then confirm the executable version:

```bash
uv tool uninstall release-gate
uv tool install ./release_gate-0.2.3-py3-none-any.whl
release-gate --version
# required output: release-gate 0.2.3
```

Finally, run `/release-gate --version` in Copilot, Claude Code, or Antigravity,
or `$release-gate --version` in Codex. Resume operations only when the bundled
skill version and executable version match.
````

- [ ] **Step 2: Update the count-checked synchronization target**

In `MARKED_RELEASE_FILES`, change the README expected target count from `10` to
`22`. The five new archive URLs contribute ten targets, and the wheel filename
plus required executable output contribute two.

- [ ] **Step 3: Run focused metadata and synchronization tests**

Run:

```bash
cd release-gate
uv run pytest tests/test_release_metadata.py tests/test_sync_release_version.py -q
```

Expected: all tests PASS.

- [ ] **Step 4: Verify synchronization is clean**

Run:

```bash
cd release-gate
uv run python scripts/sync_release_version.py --check
```

Expected: `RELEASE VERSION IN SYNC: 0.2.3`.

- [ ] **Step 5: Commit the implementation**

```bash
git add release-gate/README.md \
  release-gate/scripts/sync_release_version.py \
  release-gate/tests/test_release_metadata.py
git commit -m "docs(release-gate): add multi-host skill update guide"
```

### Task 3: Verify the completed documentation change

**Files:**
- Verify: `release-gate/README.md`
- Verify: `release-gate/scripts/sync_release_version.py`
- Verify: `release-gate/tests/test_release_metadata.py`

- [ ] **Step 1: Run the full Release Gate test suite**

Run: `cd release-gate && uv run pytest -q`

Expected: 330 tests pass with zero failures.

- [ ] **Step 2: Run static verification**

Run:

```bash
cd release-gate
uv run ruff check src tests scripts
uv run mypy src/release_gate
uv run python scripts/sync_release_version.py --check
git diff --check
```

Expected: Ruff and mypy pass, synchronization reports `0.2.3` in sync, and
`git diff --check` has no output.

- [ ] **Step 3: Refresh the repository graph**

Run from the repository root: `graphify update .`

Expected: Graphify rebuilds successfully and reports the updated node, edge,
and community totals. Generated `graphify-out/` files remain ignored.

- [ ] **Step 4: Confirm branch state**

Run:

```bash
git status --short
git log -2 --oneline
```

Expected: no tracked changes remain, and the implementation commit follows the
approved design/plan history.
