# Release Gate

Release Gate is an independent, policy-driven verification and bounded repair gate designed to sit between AI coding assistants (GitHub Copilot, OpenAI Codex, Claude Code, Google Antigravity) and production repositories.

The gate independently reconstructs candidate changes in isolated evaluation workspaces, executes repository-owned verification checks against base-trusted policy, detects AI blindspots, blocks scope and policy tampering, preserves tamper-evident evidence packages, and returns exactly one stable verdict: `PASS`, `FAIL`, or `NEEDS_HUMAN`.

The v1 product is an independent Python 3.11+ CLI and a thin portable assistant skill. It does not import any A-series or B-series package. It runs configured commands directly on a trusted host; it is not a sandbox and must not be used for hostile repositories or patches.

The Python package in `src/release_gate/` implements the versioned contracts in `schemas/`. The portable wrapper in `skills/release-gate/` invokes the installed CLI; it contains no secondary policy engine.

---

## Core Capabilities

1. **Independent Candidate Reconstruction & Isolation:** Captures uncommitted or committed changes using a private Git object database and temporary index, evaluating the candidate in clean, disjoint workspaces without polluting the working tree.
2. **Base-Trusted Policy Enforcement:** Evaluates candidate changes against `.release-gate.yaml` defined at an explicit base revision (`--base <ref>`). Any candidate modification, renaming, or deletion of policy files or protected launchers halts with `NEEDS_HUMAN` to prevent policy tampering.
3. **AI Blindspot Detection:** Catches ambient environment confusion, uninstalled declared dependencies, selective or incomplete file updates across peripheral configs, and subtle edge-case boundary logic errors.
4. **Bounded Repair Workflow:** An automated, human-in-the-loop repair state machine ($C0 \to C1 \to C2$) with an explicit 2-attempt budget, candidate lineage tracking, isolated disposable repair clones, and transactional patch application bound to SHA-256 digest verification.
5. **Assurance-Aware Mapping & Integrity:** Maps failure modes to repository checks with explicit classifications (`N-A`, `UNAVAILABLE`, `SUBSTITUTED`) and reports unverified layers inside aggregate test suites without falsely claiming coverage.
6. **Decision Observability Dashboards:** Automatically updates non-gating rolling 10 and rolling 100 decision dashboards (`_observability/index.html`, `_observability/gate-decisions-v1.json`) and generates tamper-evident per-run HTML snapshots.

---

## Bounded Repair Workflow

Release Gate provides an explicit, bounded repair workflow for resolving eligible check failures. When invoked via `/release-gate repair --base <ref>` (or `$release-gate repair --base <ref>`):

```text
[ C0: Initial Failure ]
        │
        ▼
[ User Approval: Edit scope & 2-attempt budget ]
        │
        ▼
[ Isolated Workspace ] ── Attempt 1 (C1) ──► Gate Evaluate ── (Fail) ─┐
        ▲                                                               │
        │                                                               ▼
        └──────────────── Revise Workspace ◄── Attempt 2 (C2) ◄─────────┘
                                                       │
                                                       ▼
                                                 Gate Evaluate
                                                       │
                                                 (PASS / Exit 0)
                                                       │
                                                       ▼
                                            [ Final Human Approval ]
                                                       │
                                                       ▼
                                          [ Transactional Apply to Worktree ]
```

1. **Assessment ($C0$):** The gate evaluates the initial candidate $C0$ without modifying source files. If eligible, it optionally provides a read-only Graphify diagnosis bounded to failed checks.
2. **Session Approval:** The user reviews failed checks, approved edit paths, and the strict 2-attempt budget before repair begins.
3. **Isolated Disposable Workspace:** All candidate edits occur strictly inside a temporary clone outside the source repository and evidence roots.
4. **Multi-Attempt Loop:** If Attempt 1 ($C1$) fails gate evaluation, the assistant is directed back to the isolated workspace for Attempt 2 ($C2$). The controller's 2-attempt budget is authoritative.
5. **Transactional Apply:** Upon achieving a passing candidate ($C2$), the final diff and evidence package are presented for human review. Once approved, the patch is verified against its SHA-256 digest and applied to the source worktree cleanly.
6. **Non-Modifying Default:** Standard evaluation via `release-gate run` never modifies repository files.

---

## Install and Quick Start

Python 3.11 through 3.13 and Git are required. Install the CLI and assistant skill as two separately pinned artifacts. Node.js 22.20 or newer is required only for the pinned skill installer. See [Adoption](docs/adoption.md) for detailed host commands, checksum verification, upgrades, uninstall, and rollback.

> **Package-name collision:** An unrelated existing PyPI project is named `release-gate`. Do not `uv tool install release-gate` and do not install it by an unqualified pip package name. This project is not published to PyPI. Install only the exact, checksum-verified wheel URL from the immutable GitHub release.

The following are release-ready commands, not an availability announcement. Run them only after the final GitHub release is published and its checksums are available.

<!-- release-version-sync:start -->
All fenced `bash` download commands require a POSIX shell. On Windows, run them in Git Bash; do not paste the `curl` lines into PowerShell.

For example, download `SHA256SUMS` and `release_gate-0.6.0-py3-none-any.whl` from the immutable `release-gate-v0.6.0` release, verify the wheel entry, and then install it:

```bash
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/SHA256SUMS
curl --fail --location --remote-name https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release_gate-0.6.0-py3-none-any.whl
grep '  release_gate-0.6.0-py3-none-any.whl$' SHA256SUMS | shasum -a 256 --check -
uv tool install ./release_gate-0.6.0-py3-none-any.whl
release-gate --version
```

The published SHA-256 checksum covers the Release Gate wheel itself, not its transitive dependencies. `uv tool install` resolves the declared dependency ranges from the configured package index at install time; those dependency bytes are outside the release asset checksum. The development `uv.lock` is not consumed by this tool installation. Operators that require a reproducible complete environment must separately control and record the index and resolved dependency artifacts.

Then install the matching assistant archive with `skills@1.5.23`, always using `--global`, `--copy`, and the explicit host target. This Codex example passes the immutable release asset URL directly, after the separate download and checksum review described in [Adoption](docs/adoption.md):

```bash
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-codex-0.6.0.tar.gz --global --copy --agent codex
```

## Updating an Existing Installation

Update only after the final GitHub release is published. Before replacing anything, complete the [checksum-first upgrade and rollback procedure](docs/adoption.md#upgrade-uninstall-and-rollback). Retain the previous wheel, host archive, and `SHA256SUMS` in a separate rollback directory. Never self-update or use an unpinned `skills update`.

After verifying the new wheel and exactly one host archive, run exactly one matching host block:

```bash
# GitHub Copilot CLI
npx --yes skills@1.5.23 remove release-gate --global --agent github-copilot --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-copilot-0.6.0.tar.gz --global --copy --agent github-copilot
npx --yes skills@1.5.23 list --global --agent github-copilot
```

```bash
# Codex CLI and IDE
npx --yes skills@1.5.23 remove release-gate --global --agent codex --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-codex-0.6.0.tar.gz --global --copy --agent codex
npx --yes skills@1.5.23 list --global --agent codex
```

```bash
# Claude Code
npx --yes skills@1.5.23 remove release-gate --global --agent claude-code --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-claude-code-0.6.0.tar.gz --global --copy --agent claude-code
npx --yes skills@1.5.23 list --global --agent claude-code
```

```bash
# Antigravity IDE
npx --yes skills@1.5.23 remove release-gate --global --agent antigravity --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-antigravity-0.6.0.tar.gz --global --copy --agent antigravity
npx --yes skills@1.5.23 list --global --agent antigravity
```

```bash
# Antigravity CLI
npx --yes skills@1.5.23 remove release-gate --global --agent antigravity-cli --yes
npx --yes skills@1.5.23 add https://github.com/jerryshao2012/blindspot-remediation/releases/download/release-gate-v0.6.0/release-gate-skill-antigravity-0.6.0.tar.gz --global --copy --agent antigravity-cli
npx --yes skills@1.5.23 list --global --agent antigravity-cli
```

The skill and CLI versions now differ temporarily. Do not invoke Release Gate while the skill and CLI versions differ. Replace the CLI from the verified local wheel and confirm the exact executable version:

```bash
uv tool uninstall release-gate
uv tool install ./release_gate-0.6.0-py3-none-any.whl
release-gate --version
# required output: release-gate 0.6.0
```

For Copilot, Claude Code, and Antigravity, run `/release-gate --version`; for Codex, run `$release-gate --version`. Resume only when the bundled skill version and executable version match.

Invoke the skill explicitly: `/release-gate init` in Copilot and Claude Code, `$release-gate init` in Codex, and `/release-gate init` in Antigravity. Codex does not support arbitrary custom slash commands; `/skills` can select the installed skill. `/release-gate --version` (or `$release-gate --version` in Codex) reports exactly `release-gate 0.6.0` from the bundled skill version; it does not call the CLI or inspect the repository. The only operational subcommands are `init`, `validate`, and `run`.
<!-- release-version-sync:end -->

After guided initialization, review and commit `.release-gate.yaml`. From the target repository directory, validate and run it against an explicit trusted base revision:

```bash
release-gate validate --repo .
release-gate run --repo . --base HEAD
```

`--repo .` means the current directory. To run against another repository, replace `.` with its actual path. `run` prints the stable verdict and the absolute path to `result.json`. By default evidence is written under the target repository's `.release-gate/runs/`; `--output` selects a safe disjoint evidence root.

---

## Assurance-Aware Skill Behavior

Guided initialization requires a user-approved assurance map from each failure mode or assurance claim to a repository-declared check or report, execution mode, severity, and limitation. Omitted layers are identified as `N-A`, `UNAVAILABLE`, or `SUBSTITUTED`. Aggregate checks require a reviewed expected-layer manifest and negative controls before the skill recommends them.

After a run, the skill reports each exact check status and labels `ERROR` and `SKIPPED` work unverified. Release Gate cannot independently attest unreported layers inside an aggregate command. A `PASS` still covers only the configured policy.

---

## Command Summary

### Public CLI & Skill Commands

| Command | Invocation Layer | Purpose |
|---|---|---|
| `release-gate --version` | CLI / Skill | Report the exact installed CLI version or bundled skill compatibility version (`release-gate 0.6.0`). |
| `release-gate init [--repo PATH] [--from-config PATH]` | CLI / Skill (`/release-gate init`) | Create a generic draft or copy an already validated policy byte-for-byte. |
| `release-gate validate [--repo PATH]` | CLI / Skill (`/release-gate validate`) | Validate working-copy policy draft without running repository commands. |
| `release-gate run [--repo PATH] --base REF [--output PATH] [--run-id ID]` | CLI / Skill (`/release-gate run --base REF`) | Reconstruct candidate, run policy checks, finalize evidence, and emit stable verdict (`PASS`, `FAIL`, `NEEDS_HUMAN`). |
| `/release-gate repair --base REF` | Assistant Skill | Orchestrate full human-in-the-loop bounded repair loop ($C0 \to C1 \to C2$) in isolated workspaces. |

### Private Repair Protocol Commands

The repair workflow uses deterministic controller protocol commands to coordinate the bounded repair state machine:

| Protocol Command | State Transition | Description |
|---|---|---|
| `release-gate repair-start --repo PATH --base REF [--session-id ID]` | `uninitialized` $\to$ `awaiting_approval` / `stopped` | Initializes session, evaluates $C0$, creates isolated workspace, and prepares approval request. |
| `release-gate repair-approve --session PATH --approval PATH` | `awaiting_approval` $\to$ `repairing` | Validates human approval of edit scope and budget. |
| `release-gate repair-request --session PATH` | Query | Returns workspace path, active path constraints, and playbook guidance. |
| `release-gate repair-evaluate --session PATH` | `repairing` $\to$ `awaiting_final_approval` / `repairing` / `stopped` | Exports candidate from isolated workspace, executes Release Gate, and records attempt lineage. |
| `release-gate repair-finalize --session PATH` | Maintenance | Refreshes session summary and evidence manifests. |
| `release-gate repair-apply --session PATH --approval PATH` | `awaiting_final_approval` $\to$ `applied` | Verifies source worktree matches $C0$, checks patch digest, and transactionally applies patch. |
| `release-gate repair-cancel --session PATH` | Any $\to$ `canceled` | Cancels the repair session cleanly without touching source files. |

---

## Verdicts & Decision Handling

| Verdict | Exit Code | Meaning |
|---|---:|---|
| `PASS` | `0` | Every verdict-contributing check completed successfully and policy accepted candidate. |
| `FAIL` | `1` | Complete evidence proves at least one blocking policy violation. |
| `NEEDS_HUMAN` | `2` | Required evidence is unavailable, policy was modified, or policy explicitly requires review. |

* `NEEDS_HUMAN` outranks `FAIL` if both conditions occur.
* Exit `3`: Invalid CLI usage, repository/input validation error, or policy schema violation prior to evaluation.
* Exit `4`: Unrecoverable internal engine failure before complete result and evidence finalization.

### Decision Observability Dashboard

Every finalized run with exit 0, 1, or 2 automatically updates the non-gating decision dashboard:
* **Dashboard View:** `_observability/index.html` (interactive HTML report charting `PASS`, `FAIL`, and `NEEDS_HUMAN` over rolling 10 and rolling 100 windows).
* **Data Feed:** `_observability/gate-decisions-v1.json` (versioned JSON decision series).
* **Tamper-Evident Run Snapshot:** `observability/gate-decisions.html` preserved within each run's evidence package.

---

## End-to-End Demos & Benchmarks

The [`demo/`](demo/README.md) directory contains complete, reproducible end-to-end demonstrations of Release Gate in action:

| Dimension / Feature | `python-slugify` Demo (Task X1) | `rate-limiter` Demo |
|---|---|---|
| **Primary Focus** | **Packaging Migration & AI Agent Blindspots** | **Algorithmic Correctness & Bounded Repair** |
| **Domain / Scenario** | Open-source library migrating transliteration backend (`text-unidecode` $\to$ `Unidecode`). | In-process sliding-window rate limiter with injected clock. |
| **Workflow Tested** | Automated 3-verdict controls and **Interactive Copilot CLI / Chat walkthrough**. | Automated 3-verdict controls and **0.6.0 Bounded Repair Loop** ($C0 \to C1 \to C2$). |
| **Defect Profile** | Ambient environment confusion, uninstalled declared dependencies, silent omission of `tox.ini`. | Exact-boundary off-by-one expiry ($t = \text{window}$), inverted pruning, non-finite window validation. |
| **Assurance Layers** | Package build validation, unit test suites, linting, scope enforcement against test tampering. | 100% branch coverage, 8-mutant mutation gauntlet, cache-collision negative controls, strict types, must-not scans. |
| **Independent Oracle** | Hidden transliteration oracle (15 checks) verifying symbol/currency divergence (`₹500`, `♥ love`). | Differential brute-force model (11 tests) verifying boundary, interleaving, and clock rollback. |
| **Launchers & Docs** | [python-slugify/README.md](demo/python-slugify/README.md) | [rate-limiter/README.md](demo/rate-limiter/README.md) (`run.sh` / `run.ps1`) |

### Demo Highlights

1. **[`demo/python-slugify/`](demo/python-slugify/README.md):**
   * Exposes AI coding assistant blindspots during real-world packaging maintenance:
     - **Ambient Environment Confusion:** Assistant modifies `setup.py` and assumes tests pass because dependencies exist in the host environment, but forgets to install them in the clean project venv (`NEEDS_HUMAN`).
     - **Selective / Incomplete Updates:** Assistant updates `setup.py` but omits updating `tox.ini`.
     - **Tampering Defenses:** Intercepts unauthorized modifications to `test.py` (`FAIL`) or `.release-gate.yaml` (`NEEDS_HUMAN`).

2. **[`demo/rate-limiter/`](demo/rate-limiter/README.md):**
   * Rigorous verification of complex sliding-window rate limiter invariants with full bounded repair:
     - **$C0$ (FAIL):** Seeds off-by-one window expiry defect (`>=` instead of `>`).
     - **$C1$ (FAIL):** Assistant attempts fix in isolated disposable workspace but inverts check (`<=`), failing gate evaluation while preserving source worktree integrity.
     - **$C2$ (PASS $\to$ Applied):** Assistant restores strict boundary (`>`). Release Gate evaluates $C2$ as `PASS`, obtains final approval, and transactionally applies the fix.
   * Run automated tests with `./run.sh verify` and `./run.sh verify-repair` (or `.\run.ps1` on Windows).

3. **[`demo/release-gate-demo.html`](demo/release-gate-demo.html):**
   * Standalone interactive visual slide presentation and architectural overview of Release Gate, failure modes, bounded repair loops, and decision observability.

4. **Enterprise Proxy Configuration ([`demo/env.example.ps1`](demo/env.example.ps1) / [`demo/env.example.sh`](demo/env.example.sh)):**
   * Checked-in, credential-free environment templates for enterprise networks with custom TLS certificate stores (`UV_SYSTEM_CERTS`) and authenticated HTTP/HTTPS proxies.

### Legacy Demo

`demo/gate/gate.sh` and `demo/gate/SKILL.md` are the unchanged legacy X1 demo scripts retained for historical comparison. Canonical reusable gate documentation and implementation live exclusively under `release-gate/`.

---

## Contract Map

- [Design](docs/design.md): Architecture, reconstruction, execution, and verdict rules.
- [Configuration](docs/configuration.md): `.release-gate.yaml` fields, schemas, and semantics.
- [CLI](docs/cli.md): `init`, `validate`, `run`, protocol `repair-*` commands, exit codes, and output streams.
- [Evidence](docs/evidence.md): Artifact layout, stable result package, manifest, and size budgets.
- [Security](docs/security.md): Trust boundaries, isolation principles, and operational safeguards.
- [Security Policy](SECURITY.md): Supported releases and private vulnerability reporting.
- [Adoption](docs/adoption.md): Repository onboarding, upgrade procedures, uninstall, and rollback.
- [Changelog](CHANGELOG.md): Detailed version history and release status.
- [License](LICENSE): Apache License 2.0 terms.
- [Implementation Plan](docs/implementation-plan.md): TDD-first delivery and cross-platform verification checklist.
- [Release Qualification](docs/qualification.md): Immutable RC construction, six-surface fresh-agent evidence, and promotion criteria.
- [Schemas](schemas/): JSON Schema 2020-12 contracts for configuration, result, manifest, qualification, and decision observability.
- [Examples](examples/): Generic, Python, and Node configuration templates.
- [Demos](demo/README.md): Comprehensive guide to `python-slugify`, `rate-limiter`, and interactive demo artifacts.

---

Source and releases live in the [blindspot-remediation repository](https://github.com/jerryshao2012/blindspot-remediation).
Use [GitHub issues](https://github.com/jerryshao2012/blindspot-remediation/issues) for non-sensitive inquiries. Report vulnerabilities through [private vulnerability reporting](https://github.com/jerryshao2012/blindspot-remediation/security/advisories/new) per the [security policy](SECURITY.md).

