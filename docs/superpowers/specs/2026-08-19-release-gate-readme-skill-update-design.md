# Release Gate README Skill-Update Design

## Goal

Add a concise, copy-pasteable update procedure to `release-gate/README.md` for
every supported assistant host. Keep the detailed checksum and rollback
procedure authoritative in `release-gate/docs/adoption.md`.

## Scope

The README addition covers GitHub Copilot CLI, Codex CLI/IDE, Claude Code,
Antigravity IDE, and Antigravity CLI. It documents updating the copied skill
and the paired Release Gate CLI. It does not change installation behavior,
release assets, schemas, or runtime policy.

## README Structure

Add an **Updating an existing installation** section inside the existing
`release-version-sync` block, after initial skill installation and before
invocation guidance.

The section will:

1. Require a published final release and checksum verification using the
   linked adoption guide.
2. Tell the operator to retain the previous wheel, host archive, and checksum
   manifest for rollback.
3. Warn against self-update and unpinned `skills update`.
4. Provide one `remove`, `add`, and `list` command block for each supported
   host target. Antigravity IDE and CLI use the shared Antigravity archive but
   retain their distinct agent targets.
5. Replace the CLI from the verified local wheel and require both the assistant
   version report and executable version output to match before use.
6. Link to the adoption guide for complete checksum verification and rollback.

## Version Synchronization

All current-release URLs, archive names, wheel names, and expected outputs stay
inside the existing README synchronization markers. Update the synchronizer's
count-checked README target total so a future canonical version bump updates the
new commands and fails loudly if a required target is missing or duplicated.
Historical examples outside the markers remain untouched.

## Verification

Tests will derive the current version from `release_gate.__version__` and
verify:

- all five host targets have ordered `remove`, `add`, and `list` commands;
- each target uses the correct archive and pinned `skills` version;
- the CLI is replaced from the verified local wheel;
- both skill-facing and executable version checks are documented;
- the detailed checksum/rollback guide remains linked; and
- version synchronization and its future-version propagation test remain
  green.

The full Release Gate tests, Ruff, mypy, synchronization check, and Markdown
diff check must pass after the documentation change.
