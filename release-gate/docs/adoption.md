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

<!-- release-version-sync:start -->
The commands below are release-ready examples for use only after the final
GitHub release is published with its checksum manifest. They use the immutable
`release-gate-v0.6.0` tag, but do not claim that those assets are currently
available. Candidate assets and URLs belong only in the separate qualification
procedure and are not substitutes for these end-user commands.

All fenced `bash` download commands require a POSIX shell. On Windows, run
them in Git Bash; do not paste the `curl` lines into PowerShell. The later
Python checksum command itself is also safe to run from PowerShell.

## Download and verify the CLI

Download the release checksum manifest and exact wheel:

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/SHA256SUMS
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release_gate-0.6.0-py3-none-any.whl
grep '  release_gate-0.6.0-py3-none-any.whl$' SHA256SUMS | shasum -a 256 --check -
```

Review that the checksum line came from the same GitHub release, names exactly
one wheel, and reports `OK`. On systems that provide `sha256sum` instead of
`shasum`, use the equivalent check against that single manifest line. Stop if
the file is absent, duplicated, or mismatched.

Install only the verified local wheel and confirm its exact version:

```bash
uv tool install ./release_gate-0.6.0-py3-none-any.whl
release-gate --version
```

The required output is `release-gate 0.6.0`.

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
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-copilot-0.6.0.tar.gz
grep '  release-gate-skill-copilot-0.6.0.tar.gz$' SHA256SUMS | shasum -a 256 --check -
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-copilot-0.6.0.tar.gz --global --copy --agent github-copilot
```

### Codex CLI and IDE

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-codex-0.6.0.tar.gz
grep '  release-gate-skill-codex-0.6.0.tar.gz$' SHA256SUMS | shasum -a 256 --check -
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-codex-0.6.0.tar.gz --global --copy --agent codex
```

### Claude Code

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-claude-code-0.6.0.tar.gz
grep '  release-gate-skill-claude-code-0.6.0.tar.gz$' SHA256SUMS | shasum -a 256 --check -
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-claude-code-0.6.0.tar.gz --global --copy --agent claude-code
```

### Antigravity IDE or CLI

The same verified archive is used for both Antigravity surfaces, but the
installer target is surface-specific:

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-antigravity-0.6.0.tar.gz
grep '  release-gate-skill-antigravity-0.6.0.tar.gz$' SHA256SUMS | shasum -a 256 --check -
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-antigravity-0.6.0.tar.gz --global --copy --agent antigravity
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-antigravity-0.6.0.tar.gz --global --copy --agent antigravity-cli
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

## Troubleshooting current installer availability
### When the CLI reports an older version

The Copilot skill installation and the `release-gate` CLI executable are separate. Updating the skill with `skills add --global --copy` does not replace a CLI launcher already on `PATH`. Check the executable PowerShell resolves before troubleshooting the package version:

```powershell
Get-Command release-gate -All
release-gate --version
```

If the command resolves to `$HOME\.local\bin\release-gate.exe`, it is typically a `uv` tool launcher. Reinstall the tool from the checkout that contains the desired version:

```powershell
$root = 'C:\path\to\release-gate'
uv tool install --force --editable $root
```

If `uv` cannot resolve dependencies because the package index is unavailable or returns an authorization error, first verify the checkout's isolated launcher:

```powershell
& "$root\.venv\Scripts\release-gate.exe" --version
```

As a temporary local recovery, when that launcher reports the desired version, copy it over the stale launcher and verify from a fresh PowerShell process:

```powershell
$source = Join-Path $root '.venv\Scripts\release-gate.exe'
$target = Join-Path $HOME '.local\bin\release-gate.exe'
Copy-Item $source $target -Force
powershell.exe -NoProfile -Command 'Get-Command release-gate -All; release-gate --version'
```

This recovery depends on the checkout's `.venv` remaining available. Use a successful `uv tool install` or a host archive installation for a durable installation.


If `npx --yes skills@1.5.23 ...` fails with `npm ERR! code ETARGET`, the
required installer version is not yet available from your configured npm
registry. If a release asset URL fails with `HTTP 404`, the immutable final
GitHub release asset is not published yet.

For local development in this repository only (not final release installation),
install the checked-in skill directory directly:

```bash
npx --yes skills@1.5.22 remove release-gate --global --agent github-copilot --yes
npx --yes skills@1.5.22 add ./release-gate/skills/release-gate --global --copy --agent github-copilot
npx --yes skills@1.5.22 list --global --agent github-copilot
```

This workaround bypasses unavailable release assets and should be replaced with
the pinned checksum-verified release workflow in this document as soon as the
final release artifacts and required installer version are available.

## Invocation contract

The standalone skill accepts informational `--version` and the three
operational subcommands `init`, `validate`, and `run`. A missing or unknown
input displays help and performs no operational tool call. The informational
command reads the bundled compatibility reference and prints exactly
`release-gate 0.6.0`; it does not call the CLI, inspect the repository, consider
Graphify, or perform an operation.

| Host | Version | Initialize | Validate | Run |
|---|---|---|---|---|
| GitHub Copilot CLI | `/release-gate --version` | `/release-gate init` | `/release-gate validate` | `/release-gate run --base <trusted-ref>` |
| Codex CLI/IDE | `$release-gate --version` | `$release-gate init` | `$release-gate validate` | `$release-gate run --base <trusted-ref>` |
| Claude Code | `/release-gate --version` | `/release-gate init` | `/release-gate validate` | `/release-gate run --base <trusted-ref>` |
| Antigravity IDE/CLI | `/release-gate --version` | `/release-gate init` | `/release-gate validate` | `/release-gate run --base <trusted-ref>` |

Codex uses `$release-gate`; it does not provide arbitrary custom slash
commands. `/skills` can be used to find and select the installed skill.
Copilot and Claude enforce explicit user invocation through host metadata.
Codex disables implicit invocation in its bundled agent policy. Antigravity
may load skill instructions implicitly in some host versions, so the portable
body independently blocks every effect unless the user explicitly invoked a
Release Gate operation.

Before each operation, the skill compares the underlying CLI output from
`release-gate --version` with its
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

The proposal also includes a user-approved assurance map. Each failure mode or
assurance claim is tied to a cited repository command or report, candidate or
differential mode, severity, and known limitation. Applicable work that is not
run is disclosed as `N-A`, `UNAVAILABLE`, or `SUBSTITUTED`, never as passed.
Custom checkers must fail closed, and aggregate checks require a reviewed fixed
expected-layer manifest and omission/failure negative controls.

### Repositories without Oracles

Release Gate does not require or invoke external hidden oracles (perfect graders typically used in evaluation campaigns). If a repository normally does not have an oracle, you map the failure modes to the repository's existing imperfect checks (e.g., standard unit tests, static analysis, linters). 

For absolute correctness checks that you cannot perfectly verify without an oracle, explicitly disclose them in the assurance map as `N-A`, `UNAVAILABLE`, or `SUBSTITUTED`. They must never be falsely recorded as passing. A `PASS` verdict from the gate therefore means the candidate met all requirements of the *recorded policy* using the repository's available checks; it is not a mathematical proof of correctness.

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

For every finalized exit 0, 1, or 2 run, the skill reports `result.json` and
its exact verdict before the non-gating observability report. It validates
`gate-decisions-v1.json` with the schema bundled in the host archive,
summarizes the latest rolling 10 and rolling 100 sample sizes, counts, and
rates, and labels partial warm-up windows. It links emitted snapshot,
dashboard, and data locations, reports refresh warnings without retrying, and
runs any eligible Graphify advisory last.

The run report lists every configured check's exact status. `ERROR` and
`SKIPPED` are unverified, and Release Gate cannot independently attest
unreported layers inside an aggregate command. The configured-policy-only
`PASS` caveat still applies.

The default evidence root forms one repository-local dashboard scope. A
custom `--output` is the shared scope: repositories that select the same root
intentionally combine their finalized decisions. Stable files under
`_observability/` are mutable operational views. The per-run
`observability/gate-decisions.html` snapshot is manifest-inventoried and
tamper-evident when budget and artifact slots permit it.

## Upgrade, uninstall, and rollback

Never use self-update, and never use an unpinned `skills update`. Retain the
prior wheel, host archive, and `SHA256SUMS` in a separate rollback directory.
Then download the 0.6.0 `SHA256SUMS`, wheel, and exactly one archive for the
host target into a fresh directory:

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/SHA256SUMS
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release_gate-0.6.0-py3-none-any.whl
```

Choose exactly one matching host download-and-check pair below. Do not download
several host archives into the upgrade directory. The `uv run --no-project`
verification command is identical in macOS shells and Windows PowerShell. It
validates every `SHA256SUMS` line, requires exactly one entry for both selected
assets, and compares both bytestring digests before any removal.

```bash
# GitHub Copilot CLI
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-copilot-0.6.0.tar.gz
uv run --no-project python -c "import hashlib,pathlib,re,sys; names=sys.argv[1:]; lines=pathlib.Path('SHA256SUMS').read_text(encoding='ascii').splitlines(); valid_entries=[re.fullmatch(r'[0-9a-f]{64}  [A-Za-z0-9][A-Za-z0-9._-]*', line) is not None for line in lines]; (lines and all(valid_entries)) or sys.exit('invalid SHA256SUMS'); matches={name:[line for line in lines if line.endswith('  '+name)] for name in names}; all(len(matches[name]) == 1 for name in names) or sys.exit('expected exactly one SHA256SUMS entry per asset'); all(hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest() == matches[name][0][:64] for name in names) or sys.exit('SHA-256 mismatch'); print('\n'.join(f'{name}: OK' for name in names))" release_gate-0.6.0-py3-none-any.whl release-gate-skill-copilot-0.6.0.tar.gz

# Codex CLI and IDE
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-codex-0.6.0.tar.gz
uv run --no-project python -c "import hashlib,pathlib,re,sys; names=sys.argv[1:]; lines=pathlib.Path('SHA256SUMS').read_text(encoding='ascii').splitlines(); valid_entries=[re.fullmatch(r'[0-9a-f]{64}  [A-Za-z0-9][A-Za-z0-9._-]*', line) is not None for line in lines]; (lines and all(valid_entries)) or sys.exit('invalid SHA256SUMS'); matches={name:[line for line in lines if line.endswith('  '+name)] for name in names}; all(len(matches[name]) == 1 for name in names) or sys.exit('expected exactly one SHA256SUMS entry per asset'); all(hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest() == matches[name][0][:64] for name in names) or sys.exit('SHA-256 mismatch'); print('\n'.join(f'{name}: OK' for name in names))" release_gate-0.6.0-py3-none-any.whl release-gate-skill-codex-0.6.0.tar.gz

# Claude Code
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-claude-code-0.6.0.tar.gz
uv run --no-project python -c "import hashlib,pathlib,re,sys; names=sys.argv[1:]; lines=pathlib.Path('SHA256SUMS').read_text(encoding='ascii').splitlines(); valid_entries=[re.fullmatch(r'[0-9a-f]{64}  [A-Za-z0-9][A-Za-z0-9._-]*', line) is not None for line in lines]; (lines and all(valid_entries)) or sys.exit('invalid SHA256SUMS'); matches={name:[line for line in lines if line.endswith('  '+name)] for name in names}; all(len(matches[name]) == 1 for name in names) or sys.exit('expected exactly one SHA256SUMS entry per asset'); all(hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest() == matches[name][0][:64] for name in names) or sys.exit('SHA-256 mismatch'); print('\n'.join(f'{name}: OK' for name in names))" release_gate-0.6.0-py3-none-any.whl release-gate-skill-claude-code-0.6.0.tar.gz

# Antigravity IDE or CLI (one shared archive)
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-antigravity-0.6.0.tar.gz
uv run --no-project python -c "import hashlib,pathlib,re,sys; names=sys.argv[1:]; lines=pathlib.Path('SHA256SUMS').read_text(encoding='ascii').splitlines(); valid_entries=[re.fullmatch(r'[0-9a-f]{64}  [A-Za-z0-9][A-Za-z0-9._-]*', line) is not None for line in lines]; (lines and all(valid_entries)) or sys.exit('invalid SHA256SUMS'); matches={name:[line for line in lines if line.endswith('  '+name)] for name in names}; all(len(matches[name]) == 1 for name in names) or sys.exit('expected exactly one SHA256SUMS entry per asset'); all(hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest() == matches[name][0][:64] for name in names) or sys.exit('SHA-256 mismatch'); print('\n'.join(f'{name}: OK' for name in names))" release_gate-0.6.0-py3-none-any.whl release-gate-skill-antigravity-0.6.0.tar.gz
```

Stop unless the manifest came from the same immutable 0.6.0 release and both
selected asset checks report `OK` exactly once. Complete these checks before
removing or replacing anything. Then run exactly one host block. Each block
removes the old copied skill with the exact pinned installer, installs the
immutable 0.6.0 URL with `--global --copy` for the same target, and uses
`skills list` to discover the installed skill without invoking it:

```bash
npx --yes skills@1.5.23 remove release-gate --global --agent github-copilot --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-copilot-0.6.0.tar.gz --global --copy --agent github-copilot
npx --yes skills@1.5.23 list --global --agent github-copilot
```

```bash
npx --yes skills@1.5.23 remove release-gate --global --agent codex --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-codex-0.6.0.tar.gz --global --copy --agent codex
npx --yes skills@1.5.23 list --global --agent codex
```

```bash
npx --yes skills@1.5.23 remove release-gate --global --agent claude-code --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-claude-code-0.6.0.tar.gz --global --copy --agent claude-code
npx --yes skills@1.5.23 list --global --agent claude-code
```

```bash
npx --yes skills@1.5.23 remove release-gate --global --agent antigravity --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-antigravity-0.6.0.tar.gz --global --copy --agent antigravity
npx --yes skills@1.5.23 list --global --agent antigravity
```

```bash
npx --yes skills@1.5.23 remove release-gate --global --agent antigravity-cli --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-antigravity-0.6.0.tar.gz --global --copy --agent antigravity-cli
npx --yes skills@1.5.23 list --global --agent antigravity-cli
```

The skill and CLI now differ temporarily. Do not invoke Release Gate while the
skill and CLI versions differ. Replace the CLI from the verified local wheel,
never from a package index, and confirm the exact version:

```bash
uv tool uninstall release-gate
python -m build --wheel --no-isolation
uv tool install --offline .\dist\release_gate-0.6.0-py3-none-any.whl
release-gate --version
# required output: release-gate 0.6.0
```

To uninstall without upgrading, run only the matching `skills remove` line
above, then uninstall the CLI separately:

```bash
uv tool uninstall release-gate
```

For rollback to the retained prior pair, stop invoking the skill, remove the
0.6.0 copied skill with the same pinned removal command, and reinstall the
retained checksum-verified prior archive with `skills@1.5.23 --global --copy`
for the same agent target. Then uninstall the current CLI and install the
retained verified local prior wheel. Confirm the prior `release-gate --version`
output, list the skill, and resume only when the pair matches. Preserve the
prior GitHub release and its checksums so rollback never depends on mutable or
newly built bytes.
<!-- release-version-sync:end -->

Uninstall does not remove repository policy or evidence. Remove those only as
a separate, reviewed repository change.

## Distribution limits

Release Gate has no first-use self-install behavior. This release includes no
plugins, cloud agents, hooks, MCP servers, managed service, or PyPI publication.
The assistant archive is a standalone skill; the local Python executable
remains the only verdict authority.

## SDLC CI/CD Integration

Release Gate is designed to run in standard SDLC CI/CD pipelines (like GitHub Actions, GitLab CI, or Jenkins) to enforce the repository's `.release-gate.yaml` policy on candidate changes. It is particularly useful in pull request validation.

### Best Practices for CI/CD

1. **Use the Trusted Base:** Always pass the explicitly trusted target branch (e.g., `origin/main` or `HEAD^`) as `--base`. Never allow the candidate code to specify the base revision or alter the installation of Release Gate itself.
2. **Immutable Install:** Install the exact, checksum-verified release wheel URL (never a floating `latest` tag).
3. **Handle Pipeline Exits:** `release-gate run` exits 0 (PASS), 1 (FAIL), or 2 (NEEDS_HUMAN). Treat these as your business-logic verdicts. Exits 3 or 4 indicate operational pipeline failures (e.g., malformed configuration, missing dependencies) and should fail the pipeline directly.
4. **Preserve Evidence:** Store the `.release-gate/runs/` evidence directory as a pipeline artifact. This provides a detailed, tamper-evident `result.json` explaining the verdict.
5. **Matrix Testing:** Repositories claiming cross-platform support should run the gate on all claimed operating systems (Linux, macOS, Windows) because argv handling, executable names, and path casing differ natively.

### Example: GitHub Actions Pull Request Check

Below is a complete example of applying Release Gate on a pull request using GitHub Actions. It downloads the verified CLI wheel and evaluates the PR candidate against the target branch (`github.base_ref`).

```yaml
name: Release Gate Enforcement

on:
  pull_request:
    branches: [ "main" ]

jobs:
  gate:
    name: Evaluate Candidate
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          # Fetch enough history for the gate to reconstruct the base commit
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "0.12.5"

      - name: Install and verify Release Gate
        run: |
          # Download immutable manifest and wheel
          curl -fLO https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/SHA256SUMS
          curl -fLO https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release_gate-0.6.0-py3-none-any.whl
          
          # Verify checksum
          grep '  release_gate-0.6.0-py3-none-any.whl$' SHA256SUMS | shasum -a 256 --check -
          
          # Install CLI
          uv tool install ./release_gate-0.6.0-py3-none-any.whl

      - name: Run Release Gate Validate
        run: release-gate validate --repo .

      - name: Run Release Gate Evaluation
        run: |
          # Evaluate against the pull request's target branch
          release-gate run --repo . --base "origin/${{ github.base_ref }}"
        
      - name: Archive Gate Evidence
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: release-gate-evidence
          path: .release-gate/runs/
          retention-days: 14
```

Consumers must validate the schema and contract version before interpreting the closed v1 reason-code registry in evidence files. Unknown or context-invalid codes are version or validation errors, not warnings to ignore. Size `limits.total_bytes` using the exact patch/config feasibility rule and the fixed 7 MiB finalization reserve. A preflight-infeasible change is exit 3, not a candidate verdict.

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
