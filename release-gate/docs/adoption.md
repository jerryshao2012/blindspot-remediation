# Adoption, Installation, and Lifecycle

Release and cross-assistant qualification status is tracked in
[Release qualification](qualification.md). The checked-in template is pending;
it is not evidence that the external hosts or `skills@1.5.23` have passed.

Release Gate is distributed as two independent, version-matched artifacts:

1. the Python CLI wheel, which is the only policy validator and verdict engine;
2. one assistant-specific skill archive, which provides the explicit command
   workflow and delegates every operation to that CLI.

Pin and verify both. The skill does not install or upgrade the CLI, and the CLI
does not install a skill.

## Prerequisites and package-name warning

- Python 3.11 through 3.13 and Git are required for the CLI.
- [`uv`](https://docs.astral.sh/uv/guides/tools/) installs the isolated CLI.
- Node.js 22.20 or newer is required for the pinned
  [`skills`](https://github.com/vercel-labs/skills) installer.

The release procedure requires exactly `skills@1.5.23`. Qualification and
publication are blocked until that exact version is available from the
configured npm registry and has passed the release-host matrix. This document
pins the prerequisite; it does not assert that the package version is
currently available.

> **Do not install by package name.** An unrelated existing PyPI project is
> named `release-gate`. Do not `uv tool install release-gate`, do not use
> `pip install release-gate`, and do not resolve the name through a package
> index. This project is not published to PyPI. Use only the exact GitHub
> release wheel URL and its published SHA-256.

The commands below are release-ready examples for use only after the final
GitHub release is published with its checksum manifest. They use the immutable
`release-gate-v0.2.0` tag, but do not claim that those assets are currently
available. Candidate assets and URLs belong only in the separate qualification
procedure and are not substitutes for these end-user commands.

## Download and verify the CLI

Download the release checksum manifest and exact wheel:

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/SHA256SUMS
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release_gate-0.2.0-py3-none-any.whl
grep '  release_gate-0.2.0-py3-none-any.whl$' SHA256SUMS | shasum -a 256 --check -
```

Review that the checksum line came from the same GitHub release, names exactly
one wheel, and reports `OK`. On systems that provide `sha256sum` instead of
`shasum`, use the equivalent check against that single manifest line. Stop if
the file is absent, duplicated, or mismatched.

Install only the verified local wheel and confirm its exact version:

```bash
uv tool install ./release_gate-0.2.0-py3-none-any.whl
release-gate --version
```

The required output is `release-gate 0.2.0`.

The checksum covers the Release Gate wheel itself and proves nothing about
transitive package bytes. `uv tool install` resolves the declared dependency
ranges from the configured package index at install time, and those dependency
bytes are outside the release asset checksum. The development `uv.lock` is not
consumed by `uv tool install`. If the entire installed environment must be
reproducible, separately control the package index and retain the resolved
dependency names, versions, and hashes used by the installation.

## Download, verify, and install one host archive

Each assistant has a distinct archive. Download the one matching the host,
verify its exact line in `SHA256SUMS`, then pass that reviewed immutable asset
URL to `skills@1.5.23`. `--global` installs for the current user, `--copy`
avoids cross-host symlink behavior, and `--agent` selects one explicit host
target. Do not replace the pinned installer version with `latest`.

### GitHub Copilot CLI

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-copilot-0.2.0.tar.gz
grep '  release-gate-skill-copilot-0.2.0.tar.gz$' SHA256SUMS | shasum -a 256 --check -
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-copilot-0.2.0.tar.gz --global --copy --agent github-copilot
```

### Codex CLI and IDE

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-codex-0.2.0.tar.gz
grep '  release-gate-skill-codex-0.2.0.tar.gz$' SHA256SUMS | shasum -a 256 --check -
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-codex-0.2.0.tar.gz --global --copy --agent codex
```

### Claude Code

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-claude-code-0.2.0.tar.gz
grep '  release-gate-skill-claude-code-0.2.0.tar.gz$' SHA256SUMS | shasum -a 256 --check -
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-claude-code-0.2.0.tar.gz --global --copy --agent claude-code
```

### Antigravity IDE or CLI

The same verified archive is used for both Antigravity surfaces, but the
installer target is surface-specific:

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-antigravity-0.2.0.tar.gz
grep '  release-gate-skill-antigravity-0.2.0.tar.gz$' SHA256SUMS | shasum -a 256 --check -
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-antigravity-0.2.0.tar.gz --global --copy --agent antigravity
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-antigravity-0.2.0.tar.gz --global --copy --agent antigravity-cli
```

Install only the line for the surface being used. After installation, use the
pinned installer's `list --global --agent <target>` command and the host's skill
discovery UI or command to confirm that `release-gate` is visible. Installation
does not replace qualification of the exact host and archive combination.
The checksum step verifies the separately downloaded review copy. The Skills
CLI may download the URL again during installation, so the final release asset
must be immutable and byte-identical to the hash-qualified asset. Stop if the
release asset was replaced, the manifest changed, or the installed archive
cannot be tied to the qualified SHA-256.

## Invocation contract

The standalone skill supports only `init`, `validate`, and `run`. A missing or
unknown subcommand displays help and performs no operational tool call.

| Host | Initialize | Validate | Run |
|---|---|---|---|
| GitHub Copilot CLI | `/release-gate init` | `/release-gate validate` | `/release-gate run --base <trusted-ref>` |
| Codex CLI/IDE | `$release-gate init` | `$release-gate validate` | `$release-gate run --base <trusted-ref>` |
| Claude Code | `/release-gate init` | `/release-gate validate` | `/release-gate run --base <trusted-ref>` |
| Antigravity IDE/CLI | `/release-gate init` | `/release-gate validate` | `/release-gate run --base <trusted-ref>` |

Codex uses `$release-gate`; it does not provide arbitrary custom slash
commands. `/skills` can be used to find and select the installed skill.
Copilot and Claude enforce explicit user invocation through host metadata.
Codex disables implicit invocation in its bundled agent policy. Antigravity
may load skill instructions implicitly in some host versions, so the portable
body independently blocks every effect unless the user explicitly invoked a
Release Gate operation.

Before each operation, the skill compares `release-gate --version` with its
bundled `references/compatibility.json`. Any missing executable or version
mismatch stops without initialization, validation, or gate execution.

## Add a repository

Guided `init` may inspect manifests, lockfiles, CI configuration, and declared
scripts. It does not execute repository code or read environment values. It
cites the source of every proposed argv and asks for explicit decisions about
command inclusion, candidate or differential mode, severity, preparation and
network behavior, path scope, and inherited environment variable names. It
shows one combined diff for `.release-gate.yaml` and `.gitignore` and writes
only after approval through `release-gate init --from-config`.

After initialization:

1. Review and commit `.release-gate.yaml` and every script it invokes.
2. Run `release-gate validate --repo /path/to/repository`.
3. Run `release-gate run --repo /path/to/repository --base <trusted-commit>`.
4. Consume `<evidence-root>/<run-id>/result.json` for exits 0 through 2.
   Treat exits 3 and 4 as operational errors with no verdict.

Do not copy thresholds blindly. Calibrate blocking policy against known-good,
known-bad, broken-tool, timeout, scope-tamper, and pre-existing-debt cases.
Candidate mode suits absolute requirements on a green baseline. Differential
mode suits policy that deliberately permits existing debt but blocks
regression.

The default evidence root is `.release-gate/runs/`; guided initialization adds
that path to `.gitignore` only after approval. Keep `.release-gate` and its
`runs` child as real directories. A symbolic link, Windows junction, or other
reparse point at either location is unsafe and causes exit 3. A custom evidence
root must resolve outside the repository and is not an additional candidate
capture exclusion. Evidence should not normally be committed.

## Permissions, data, and trust boundaries

Installing a global copied skill writes under the selected assistant's user
skill location. Guided `init` reads limited repository metadata and, only after
approval, creates `.release-gate.yaml` and updates `.gitignore`. `validate` is
read-only. `run` reads Git history and candidate files, creates isolated work
trees, executes the base-owned configured argv, and writes evidence to the
selected evidence root.

Release Gate is trusted-host execution, not a sandbox. Configured commands run
with the operator's local identity and may read host-accessible files, consume
resources, or access the network when the operator permits it. The CLI passes
only explicitly inherited environment names and records names, not inherited
values, but executed repository code can discover other host-readable data.
Use a low-privilege account and an isolated, secret-free runner when
consequences matter. Repository content and assistant output are untrusted;
the installed CLI, matching skill archive, checksum manifest, chosen base
commit, and base-owned policy are trusted inputs.

The skill never retries a gate to obtain a pass, edits evidence, merges, or
deploys. For exits 0 through 2, it reports the recorded verdict, reason codes,
and result path without softening them; in particular, it never maps
`NEEDS_HUMAN` to `FAIL` or claims that local execution is isolated. A `PASS` is
only recorded policy eligibility. See the detailed [security and trust
model](security.md) and the
[vulnerability reporting policy](../SECURITY.md).

## Upgrade, uninstall, and rollback

Never use an unpinned `skills update`. To upgrade, retain the prior wheel,
host archive, and `SHA256SUMS`; download and verify the next immutable release;
remove the old copied skill; install the new host archive with its exact
`skills@1.5.23` command; then replace the CLI with the matching verified wheel.
Confirm `release-gate --version` and run host discovery before use. Do not mix
CLI and skill versions.

For example, after the final 0.2.0 release is published, upgrade the CLI from a
prior release only after the new wheel passes its checksum check:

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/SHA256SUMS
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release_gate-0.2.0-py3-none-any.whl
grep '  release_gate-0.2.0-py3-none-any.whl$' SHA256SUMS | shasum -a 256 --check -
uv tool uninstall release-gate
uv tool install ./release_gate-0.2.0-py3-none-any.whl
release-gate --version
```

Likewise, first download and checksum the new host archive using the relevant
command above. Then remove the prior copied skill and install from the new
immutable URL. Use only the pair matching the selected host:

```bash
npx --yes skills@1.5.23 remove release-gate --global --agent github-copilot --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-copilot-0.2.0.tar.gz --global --copy --agent github-copilot
```

```bash
npx --yes skills@1.5.23 remove release-gate --global --agent codex --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-codex-0.2.0.tar.gz --global --copy --agent codex
```

```bash
npx --yes skills@1.5.23 remove release-gate --global --agent claude-code --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-claude-code-0.2.0.tar.gz --global --copy --agent claude-code
```

```bash
npx --yes skills@1.5.23 remove release-gate --global --agent antigravity --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-antigravity-0.2.0.tar.gz --global --copy --agent antigravity
```

```bash
npx --yes skills@1.5.23 remove release-gate --global --agent antigravity-cli --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.0/release-gate-skill-antigravity-0.2.0.tar.gz --global --copy --agent antigravity-cli
```

To uninstall without upgrading, run only the matching `skills remove` line
above, then uninstall the CLI separately:

```bash
uv tool uninstall release-gate
```

For rollback, perform those same removals, reinstall the retained prior skill
archive for the exact host target, uninstall the current CLI, and reinstall the
retained prior verified wheel. Verify both versions before resuming. A release
process must preserve the prior GitHub release and its checksums so rollback
does not depend on mutable or newly built bytes.

Uninstall does not remove repository policy or evidence. Remove those only as
a separate, reviewed repository change.

## Distribution limits

Release Gate has no first-use self-install behavior. This release includes no
plugins, cloud agents, hooks, MCP servers, managed service, or PyPI publication.
The assistant archive is a standalone skill; the local Python executable
remains the only verdict authority.

## CI use

Check out enough history to resolve the trusted base commit, install the exact
verified release wheel, and pass the commit ID explicitly as `--base`. Do not
accept a candidate-controlled base ref or install the gate from candidate
code. Store the complete evidence directory as one CI artifact and branch on
exit 0, 1, or 2; treat 3 and 4 as pipeline failures rather than verdicts.

Consumers must validate the schema and contract version before interpreting
the closed v1 reason-code registry. Unknown or context-invalid codes are
version or validation errors, not warnings to ignore. Root reason arrays are
stable machine data containing ASCII-sorted atomic causes; log prose is not.
Size `limits.total_bytes` using the exact patch/config feasibility rule and the
fixed 7 MiB finalization reserve. A preflight-infeasible change is exit 3, not
a candidate verdict.

Linux, macOS, and Windows jobs should each run `validate`. Repositories
claiming platform support must execute at least one real gate run on every
claimed operating system because argv, executable names, path casing, signals,
and process termination differ.

## Existing blindspot demo

`demo/gate/gate.sh` and `demo/gate/SKILL.md` remain the legacy Python/X1
demonstration. The standalone product does not import, wrap, or silently
replace them. Existing A/B components remain design donors, not runtime
dependencies or compatibility APIs.

Migration is a separate review: express the demo controls in base-owned policy,
reproduce its control outcomes with new run IDs, compare verdicts and evidence,
and update demo documentation only after parity is accepted.

## Version evolution

Additive clarifications that remain schema-valid may update v1 documentation.
Renamed fields, changed verdict meaning or precedence, new parser semantics, or
an incompatible evidence layout require a new schema and explicit migration.
Never reinterpret stored v1 evidence under later policy.
