# Release Gate

This directory contains the canonical specification and implementation of the
standalone release gate. The gate independently reconstructs a repository change, runs
repository-owned checks, preserves evidence, and returns exactly one verdict:
`PASS`, `FAIL`, or `NEEDS_HUMAN`.

The v1 product is an independent Python 3.11+ CLI and a thin portable skill.
It does not import any A-series or B-series package. It runs configured
commands directly on a trusted host; it is not a sandbox and must not be used
for hostile repositories or patches.

The Python package in `src/release_gate/` implements the versioned contracts in
`schemas/`. The portable wrapper in `skills/release-gate/` invokes the installed
CLI; it contains no second policy implementation.

## Install and quick start

Python 3.11 through 3.13 and Git are required. Install the CLI and assistant
skill as two separately pinned artifacts. Node.js 22.20 or newer is required
only for the pinned skill installer. See [Adoption](docs/adoption.md) for every
host command, checksum verification, upgrades, uninstall, and rollback.

> **Package-name collision:** an unrelated existing PyPI project is named
> `release-gate`. Do not `uv tool install release-gate` and do not install it
> by an unqualified pip package name. This project is not published to PyPI.
> Install only the exact, checksum-verified wheel URL from the immutable GitHub
> release.

The following are release-ready commands, not an availability announcement.
Run them only after the final GitHub release is published and its checksums are
available. These documents do not claim that those assets are currently
available.

For example, download `SHA256SUMS` and
`release_gate-0.2.2-py3-none-any.whl` from the immutable
`release-gate-v0.2.2` release, verify the wheel entry, and then install it:

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.2/SHA256SUMS
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.2/release_gate-0.2.2-py3-none-any.whl
grep '  release_gate-0.2.2-py3-none-any.whl$' SHA256SUMS | shasum -a 256 --check -
uv tool install ./release_gate-0.2.2-py3-none-any.whl
release-gate --version
```

The published SHA-256 checksum covers the Release Gate wheel itself, not its
transitive dependencies. `uv tool install` resolves the declared dependency
ranges from the configured package index at install time; those dependency
bytes are outside the release asset checksum. The development `uv.lock` is not
consumed by this tool installation. Operators that require a reproducible
complete environment must separately control and record the index and resolved
dependency artifacts.

Then install the matching assistant archive with `skills@1.5.23`, always using
`--global`, `--copy`, and the explicit host target. This Codex example passes
the immutable release asset URL directly, after the separate download and
checksum review described in [Adoption](docs/adoption.md):

```bash
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.2.2/release-gate-skill-codex-0.2.2.tar.gz --global --copy --agent codex
```

Invoke the skill explicitly: `/release-gate init` in Copilot and Claude Code,
`$release-gate init` in Codex, and `/release-gate init` in Antigravity. Codex
does not support arbitrary custom slash commands; `/skills` can select the
installed skill. The skill supports only `init`, `validate`, and `run`.

After guided initialization, review and commit `.release-gate.yaml`. From the
target repository directory, validate and run it against an explicit trusted
base revision:

```bash
release-gate validate --repo .
release-gate run --repo . --base HEAD
```

`--repo .` means the current directory. To run against another repository,
replace `.` with its actual path, such as `C:\work\target-repository` in
PowerShell. `run` prints the stable verdict and the absolute path to
`result.json`. By default evidence is written under the target repository's
`.release-gate/runs/`; `--output` selects a safe disjoint evidence root.

## Command summary

| Command | Purpose |
|---|---|
| `release-gate init [--repo PATH] [--from-config PATH]` | Create a generic draft or copy an already validated policy byte-for-byte. |
| `release-gate validate [--repo PATH]` | Validate the working-copy policy draft. |
| `release-gate run [--repo PATH] --base REF [--output PATH] [--run-id ID]` | Evaluate the captured candidate using policy from the required base revision. |

Published users install the matching verified host archive. The canonical
`skills/release-gate/` tree is for development and packaging. No plugin is
required.

## Contract map

- [Design](docs/design.md): architecture, reconstruction, execution, and
  verdict rules.
- [Configuration](docs/configuration.md): `.release-gate.yaml` fields and
  evaluation semantics.
- [CLI](docs/cli.md): `init`, `validate`, `run`, output, and exit codes.
- [Evidence](docs/evidence.md): artifact layout, stable result, manifest, and
  size budgets.
- [Security](docs/security.md): trust boundary and operational safeguards.
- [Security policy](SECURITY.md): supported releases and private vulnerability
  reporting.
- [Adoption](docs/adoption.md): repository onboarding and legacy coexistence.
- [Changelog](CHANGELOG.md): version history and release status.
- [License](LICENSE): Apache License 2.0 terms.
- [Implementation plan](docs/implementation-plan.md): TDD-first delivery and
  cross-platform verification checklist.
- [Release qualification](docs/qualification.md): immutable RC construction,
  six-surface fresh-agent evidence, and protected byte-identical promotion.
- [Schemas](schemas): JSON Schema 2020-12 contracts for configuration, result,
  and manifest documents.
- [Examples](examples): generic, Python, and Node configurations.

Source and releases live in the
[blindspot-remediation repository](https://github.com/jerryshao2012/blindspot-remediation).
Use [GitHub issues](https://github.com/jerryshao2012/blindspot-remediation/issues)
for non-sensitive support and defects. Report vulnerabilities only through
[private vulnerability reporting](https://github.com/jerryshao2012/blindspot-remediation/security/advisories/new),
following the [security policy](SECURITY.md).

## Normative terms

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative. When prose and a schema
disagree, the schema controls document shape and the prose controls runtime
semantics. A future incompatible change requires a new schema version; v1
files are not silently reinterpreted.

## Verdicts

| Verdict | Exit | Meaning |
|---|---:|---|
| `PASS` | 0 | Every verdict-contributing check completed and policy accepted the candidate. |
| `FAIL` | 1 | Complete evidence proves at least one blocking policy violation. |
| `NEEDS_HUMAN` | 2 | Required evidence is unavailable or policy explicitly requires review. |

`NEEDS_HUMAN` outranks `FAIL`. Invalid usage, input, or configuration before a
candidate verdict exits 3. An unrecoverable internal failure before complete
result/evidence finalization exits 4.

`PASS` means eligible under the recorded gate policy. The gate neither performs
nor authorizes a merge or deployment. It is not a security attestation or
proof that the software is defect free.

## Demos

[`demo/python-slugify/`](demo/python-slugify/README.md) is the standalone
product walkthrough for native Windows and macOS. It uses GitHub Copilot CLI's
explicit `/release-gate` skill, a generated pinned workbench, all three
verdicts, evidence inspection, and hidden-oracle grading.

### Legacy demo

`demo/gate/gate.sh` and `demo/gate/SKILL.md` are the unchanged legacy X1 demo.
Their documented commands remain valid. They are neither the implementation
nor the configuration of this standalone product. Canonical reusable-gate
documentation lives only under `release-gate/`.
