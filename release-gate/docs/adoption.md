# Adoption and Coexistence

## Install the reusable product

Use Python 3.11–3.13 and install the package from this repository:

```bash
python -m pip install ./release-gate
```

The optional agent wrapper is `release-gate/skills/release-gate/`. Copy that
directory into the host's skill search path only after the CLI is installed.
The skill is portable and does not require a plugin.

## Add a repository

1. Install the independent Python 3.11+ CLI in a dedicated environment.
2. Run `release-gate init --repo /path/to/repository`.
3. Replace example `allowed_paths`, `forbidden_paths`,
   `review_required_paths`, commands, inherited-environment names, exit
   classes, reports, and assertions with repository-owned policy.
4. Run `release-gate validate` and review the effective platform command.
5. Commit `.release-gate.yaml` and every script it invokes. The first run must
   select a base commit containing that policy.
6. Run `release-gate run --base <trusted-commit>` and consume
   `<effective-evidence-root>/<run-id>/result.json` (by default,
   `.release-gate/runs/<run-id>/result.json`).

Do not copy thresholds blindly. Calibrate blocking policy against known-good,
known-bad, broken-tool, timeout, scope-tamper, and pre-existing-debt cases.
Candidate mode is appropriate for a green baseline and absolute requirements;
differential mode is appropriate when policy deliberately allows existing
debt but forbids regression.

Add `.release-gate/runs/` to the repository's ignore policy after reviewing
that change. After no-follow verification, the engine excludes descendants of
only that exact default subtree from candidate capture even before it is
ignored. A custom evidence root must resolve outside the repository and is
never an additional capture exclusion; evidence should not normally be
committed. Keep `.release-gate` and its `runs` child as real directories: a
symbolic link, Windows junction, or other reparse point at either location
makes the default unsafe and the run exits 3 without following or replacing
it.

## CI use

Check out the candidate tree with enough history to resolve the trusted target
commit, install a pinned gate version, and pass the target commit ID explicitly
as `--base`. Do not accept a candidate-controlled base ref or install a gate
from candidate code. Store the whole evidence directory as one CI artifact and
branch on exit 0/1/2; treat 3/4 as pipeline failures rather than candidate
verdicts.

Consumers MUST validate the schema and contract version before interpreting
the closed v1 reason-code registry. An unknown or wrong-context code is a
version/validation error, not a warning to ignore. Root reason arrays are
stable machine data and are ASCII-sorted atomic causes; log prose is not.
Size `total_bytes` with the exact patch/config feasibility rule and fixed
7 MiB finalization reserve in mind; a preflight-infeasible change is exit 3,
not a candidate failure.

Linux, macOS, and Windows jobs SHOULD each run `validate`. Repositories
claiming platform support MUST execute at least one real gate run on each
claimed OS, because argv, executable names, path casing, signals, and process
termination differ.

## Portable skill

The v1 skill is a thin distribution companion, not an evaluation engine. It:

1. locates the independently installed `release-gate` executable;
2. invokes `run` with an explicit repository and base;
3. reads `result.json` after exits 0, 1, or 2; and
4. reports the verdict, reason codes, and result path without softening or
   reinterpreting them.

It never edits candidate files or policy, retries until a pass, maps
`NEEDS_HUMAN` to `FAIL`, or claims that local execution is isolated. V1 ships
no plugin. Plugin packaging is deferred until managed distribution, hooks, or
external integrations justify the additional lifecycle.

The skill treats `PASS` only as recorded policy eligibility. It never performs
or authorizes a merge or deployment.

## Existing blindspot demo

`demo/gate/gate.sh` and `demo/gate/SKILL.md` stay unchanged. They remain the
legacy Python/X1 demonstration and all commands documented under `demo/`
remain intact. The standalone gate does not import, wrap, or silently replace
them.

Migration is a later, separately reviewed activity:

1. express the demo's scope, tests, coverage, typing, lint, and secret checks
   in a base-owned v1 policy;
2. reproduce the untouched, lazy-change, missing-tool, and evidence-tamper
   control outcomes with new run IDs;
3. compare both verdicts and reason-coded evidence; and
4. update demo documentation only after parity is accepted.

The historical A3 service and A/B architecture remain design donors, not
runtime dependencies or compatibility APIs. Canonical reusable-product
contracts live under `release-gate/`.

## Version evolution

Additive clarifications that remain schema-valid may update the v1 docs.
Renamed fields, changed verdict meaning, new precedence, new parser semantics,
or incompatible evidence layout require v2 schemas and an explicit migration.
Never reinterpret stored v1 evidence under later policy.
