# Release qualification

Release Gate 0.2.0 is not qualified or published yet. In particular, this
repository does **not** claim that `skills@1.5.23` has been obtained and tested,
or that any of the six advertised assistant surfaces has passed. Promotion is
designed to stop until the exact installer is available and complete evidence
passes both the JSON Schema and semantic validator.

## Immutable candidate

The protected release workflow builds the wheel, source distribution, and four
host archives once for `release-gate-v0.2.0-rc.1`. It emits a sorted
`SHA256SUMS`, verifies source/wheel/CLI/compatibility/archive version agreement,
and publishes only after approval through the `release-gate-production`
environment. An existing tag or release is never replaced.

That environment name alone does not protect a release. Before enabling this
workflow, repository administrators must configure the GitHub
`release-gate-production` environment with required reviewers, enable prevent
self-review, and add deployment branch/ref restrictions that permit only the
trusted default branch. The reviewers must inspect the exact commit and exact
artifact hashes presented by the workflow before approving either publication
job. Until those environment rules exist, maintainers must treat the workflow
as unprotected and must not dispatch a release.

Final promotion downloads those existing RC assets. It does not rebuild them.
The final `release-gate-v0.2.0` tag must target the same commit and receives the
same bytes only after qualification passes. The previous release is retained
for rollback.

## Fresh-agent protocol

Qualify each of Copilot CLI, Codex CLI, Codex IDE, Claude Code, Antigravity IDE,
and Antigravity CLI separately:

1. Record the exact host and model versions, OS, Node version, and available
   permissions/tools. Use a fresh agent without the skill and record the
   baseline routing failure before installing anything.
2. Verify `SHA256SUMS`. Install the exact RC wheel and matching RC host archive.
   Use Node.js 22.20 or newer and exactly `skills@1.5.23`; do not substitute
   `latest`. Record the installed CLI-wheel and archive hashes.
3. Repeat the exact prompt through explicit selection/invocation. Preserve the
   prompt, observable tool calls, files read/written, command output, timestamp,
   and an evidence reference. A model summary without observable effects is not
   evidence.
4. Exercise generic, Python, Node, and ambiguous-monorepo initialization. Cover
   cancellation, an existing policy, invalid configuration, missing and
   mismatched CLI versions, permission failures, adversarial repository
   instructions, `PASS`, `FAIL`, `NEEDS_HUMAN`, and pre-verdict exits 3 and 4.
   Confirm no repository code is executed during guided inspection, no write
   occurs before approval, and no retry, evidence edit, merge, or deploy occurs.
5. Mark a surface `pass` only when the entire routing and safety corpus has the
   expected observable result. Record failures honestly and rerun with a new
   RC rather than editing evidence into a pass.

The checked-in
[`release-gate-v0.2.0-rc.1.pending.json`](../qualification/release-gate-v0.2.0-rc.1.pending.json)
is an explicitly non-promotable example. Its zero hashes, placeholder commit,
and pending results are not qualification evidence. After external testing,
create `qualification/release-gate-v0.2.0-rc.1.json` with actual values and run:

```bash
uv run python scripts/validate_qualification.py \
  qualification/release-gate-v0.2.0-rc.1.json \
  --expected-tag release-gate-v0.2.0-rc.1 \
  --expected-commit FULL_RC_COMMIT \
  --assets-dir /path/to/downloaded-rc-assets
```

The schema permits a pending document so CI can check the template shape. The
semantic validator deliberately rejects pending, duplicate, missing, failing,
wrong-version, wrong-tag, wrong-commit, and hash-mismatched evidence.

Every surface records its exact operating system and its own Node.js version;
the latter must be 22.20.0 or newer. Every session and corpus-case evidence
reference is a globally unique `{uri, sha256}` pair. The digest binds the
referenced transcript or observation record rather than trusting a mutable
path or prose assertion.

## Recovery and pinned release tooling

Release publication is resumable. Each write-authorized job first creates a
draft release targeted at the validated commit and never overwrites an asset.
On retry it accepts only a still-draft release whose target and any existing
tag match that commit, downloads and verifies existing assets, uploads only
missing names, verifies the complete remote seven-file set, and only then
publishes the draft. A published or mismatched release stops the workflow. Do
not delete a partial draft: inspect the failure and rerun the same action and
commit so the job can safely resume it.

Draft discovery deliberately uses the authenticated, paginated releases API,
because the published-release-by-tag endpoint does not reliably discover
drafts. Creation returns a numeric release ID. Every asset list, download,
upload, and final draft patch is then addressed through that numeric ID; the RC
requires `prerelease=true`, while the final release requires
`prerelease=false`.

Both workflows pin every action to a reviewed immutable commit. `setup-uv`
v8.1.0 is pinned by commit and installs exactly uv 0.12.5. The committed
`uv.lock` includes Hatchling 1.32.0, matching the exact build-system pin, and
release builds use `python -m build --no-isolation`. Upgrade an action, uv, or
Hatchling only in a reviewed change that updates its pin, lockfile,
deterministic-build evidence, and this documentation together.
