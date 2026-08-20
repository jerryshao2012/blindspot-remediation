# CLI Contract

The installed console command is `release-gate`. It supports exactly three v1
subcommands: `init`, `validate`, and `run`. The global `release-gate --version`
command prints the installed distribution version and exits 0.

## `init`

```text
release-gate init [--repo PATH] [--from-config PATH]
```

`--repo` defaults to the current directory. The command writes a generic
`.release-gate.yaml` draft containing an intentionally unavailable placeholder
command, then validates it. It does not infer an ecosystem or project command.
With `--from-config`, it instead reads at most 1 MiB from the selected file,
performs the same YAML, schema, and semantic validation before changing the
target repository, and preserves the exact approved source bytes in the new
policy. It never overwrites an existing policy.

Initialization snapshots `.gitignore` by filesystem identity, length, and
SHA-256 before writing either target and rejects symbolic links, Windows
reparse points, and non-regular ignore targets. It stages and flushes the
policy privately, then opens or exclusively creates `.gitignore`, takes a
nonblocking cross-platform advisory lock, and performs the final snapshot
check through that pinned handle. The lock remains held through an append or
no-op, policy publication, and any rollback. Immediately before publication,
it revalidates both the final path identity and the exact expected bytes through
the locked descriptor, including the existing-entry no-op case. Detected path
or content changes stop publication and are preserved. The policy is published
last by an atomic exclusive hard link; the command has no policy rollback and
does not deliberately remove or truncate a published policy. On failure it
attempts to roll back ignore bytes only through the locked handle after repeated
identity and exact-content checks. When initialization created a missing
`.gitignore` but later fails, it leaves the empty file instead of using a
check-then-unlink cleanup. Advisory-lock contention, an existing target,
non-directory repository path, unsafe ignore target, race, or write failure is
exit 3. The operator must tailor and commit the policy before `run`, because
runs trust only base-revision policy.

The lock serializes cooperating Release Gate initializers, not arbitrary
writers. Portable filesystems cannot atomically combine the final ignore check
with policy linking, or the rollback content check with truncation. A hostile
or non-cooperating same-user process can therefore race those syscall gaps.
Run initialization without other repository writers; same-user processes are
inside this local-filesystem trust boundary.

## `validate`

```text
release-gate validate [--repo PATH]
```

The default input is `<repo>/.release-gate.yaml`. This command performs YAML
parsing, JSON Schema 2020-12 validation, semantic validation, defaults, and
host-platform resolution without running repository commands. Success prints
`VALID:` and the policy path. Validation diagnostics go to stderr, use document
paths, contain no traceback for expected errors, and exit 3.

## `run`

```text
release-gate run [--repo PATH] --base REF [--output PATH] [--run-id ID]
```

`--repo` defaults to the current directory. `--base` is mandatory at the
argument-parser boundary and the selected ref must resolve to a local commit.
`--run-id` defaults to a separator-free UTC timestamp plus random suffix. It is
a 1-128-character ASCII component that
begins with a letter or digit, then uses only letters, digits, `.`, `_`, and
`-`, cannot end in `.`, and cannot have a case-insensitive DOS device basename
`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, or `LPT1`-`LPT9`, even with an
extension. This allowed set excludes ASCII controls, empty/dot/dotdot names,
spaces, and Windows-illegal `<>:"/\|?*`. An existing or
NFC-plus-casefold-equivalent sibling run directory is never overwritten.

The default evidence root is the literal path
`<canonical-repo>/.release-gate/runs`. A relative custom `--output` is
anchored to the invocation working directory, not to `--repo`. Before candidate
capture, the engine first canonicalizes only the repository root, its `.git`
entry, the per-worktree directory from `git rev-parse --git-dir`, and the
shared metadata directory from `git rev-parse --git-common-dir`; Git-reported
paths are first made absolute. It lexically normalizes the selected evidence
spelling without resolving it and branches on whether it names the literal
default under native filesystem case rules. A default candidate uses the
no-follow procedure below before any evidence-root or run-directory
canonicalization. Only a custom root and its proposed `<root>/<run-id>` are
then canonically resolved through every existing ancestor. Their nonexistent
suffixes are appended to the canonical nearest existing ancestor. Containment
is component-aware and never uses string-prefix comparison.

The in-repository exception is stricter than ordinary canonical resolution.
Starting from the already canonical repository directory, the engine inspects
the existing `.release-gate` and `runs` entries without following them. Each
MUST be a real directory, never a POSIX symbolic link or a Windows reparse
point, including a junction; a non-directory is also invalid. Missing entries
are allowed but are not created before capture. Relative or redundant-segment
spellings qualify when they normalize to the literal default: every existing
component must have the identity obtained by the no-follow walk, and an absent
suffix is represented only by the remaining literal component names. The full
identity is pinned after any missing components are created. A symlink alias
is not an equivalent spelling, even if its target is the default directory.

The no-follow inspection occurs immediately before capture and checks the
`.release-gate/runs` node itself before enabling the exclusion. Consequently,
a tracked or untracked candidate symlink, reparse point, or junction at either
default component is rejected as unsafe input rather than hidden. Pre-capture
validation is read-only: it does not create, delete, replace, or traverse a
default component and an exit-3 rejection leaves source bytes, index, and
status unchanged. Candidate capture then excludes descendants of only the
verified-or-absent literal `.release-gate/runs/` path. The engine repeats the
no-follow inspection immediately after capture and before creating anything.

Only after the patch is complete may the engine create missing default
components, one at a time with no-follow/no-reparse operations rooted at the
verified repository directory. It verifies directory type and stable
filesystem identity after each creation and after creating the run directory.
If a pre-execution check fails, it removes only still-empty scaffolding that
this invocation created; it never writes through, deletes, or replaces the
unexpected entry. Evidence I/O remains relative to pinned directory handles,
or an equivalent facility that cannot be redirected by a later path swap.
Identities are rechecked after capture, after creation, after clone placement,
before any configured preparation/check command, immediately before
finalization, and after finalization before printing `RESULT`. Candidate
evaluation begins only after capture, destination creation, clone placement,
and a final identity check, immediately before invariant policy/launcher and
scope evaluation. A mismatch before that transition is exit 3. A mismatch
after it prevents a valid package, yields exit 4, and leaves `.incomplete`
only when it can be written through a still verified handle.

Every other custom root is rejected if either its normalized spelling,
canonical target, or any existing-prefix identity encountered while resolving
it is equal to or below the source repository, its `.git` entry, its
per-worktree Git directory, or its shared Git common directory. This catches
an in-repository symlink that later resolves outward as well as an outside
alias that resolves inward. The default exception permits only the verified
source-worktree directory chain and never Git metadata or an execution clone.
A custom root that is an ancestor of a protected path is accepted only when
the final run directory is disjoint from every protected path. The engine
creates clones elsewhere and rechecks before executing commands. No custom
root creates a capture exclusion or hides candidate files.

Preflight resolves the base, reads at most 1 MiB of `.release-gate.yaml` from
it, validates the policy, performs the read-only source/evidence checks above,
and only then captures the working tree through an invocation-owned temporary
index and Git object directory. Source objects are read-only alternates; newly
staged blobs do not enter the source/common object database.

Before candidate evaluation, preflight stages and measures the exact
`candidate.patch` and canonical `effective-config.json`. It rejects a patch
over 200 MiB, either raw/effective configuration over 1 MiB, or any input for
which `patch bytes + effective-config bytes + 7,340,032` exceeds
`limits.total_bytes`. It also rejects an effective policy and captured
changed-path inventory whose maximum bounded result/manifest/trace structures
cannot fit the respective 2/4/1 MiB parts of that reserve. These are exit-3
input/configuration errors: no verdict or `result.json` is promised, staged
files are discarded, and accepted patch/config bytes are never truncated.
Invalid refs, ambiguous input, patch reconstruction failure, or an unsafe
evidence path have the same boundary.

After capture, preflight compares `.release-gate.yaml` and every directly
invoked repository-local launcher with the base. Any candidate add, modify,
rename, or delete of the policy, or change to a covered launcher, is valid
candidate input but requires review: no configured preparation/check command
runs, all controls are recorded `SKIPPED`, a complete `NEEDS_HUMAN` result is
finalized, and the command exits 2. Policy scope and severity cannot weaken
this rule.

After preflight, expected check/tool/report failures are finalized in
`result.json` and map to a candidate verdict. Normal stdout ends with these
stable lines:

```text
VERDICT: PASS|FAIL|NEEDS_HUMAN
RESULT: <absolute-path-to-result.json>
```

Human-readable progress goes to stderr. Automation MUST consume `result.json`,
not parse progress text. The result is complete before the verdict lines are
printed. Even when later work stops, its `checks` array contains one item per
effective check in declaration order; unrun checks are reason-coded `SKIPPED`.
Before those lines, the engine validates result and manifest with the bundled
Draft 2020-12 schemas using an explicit `FormatChecker`, then applies the
cross-document semantic checks, including the strict timestamp profile and
execution lifecycle/order contract. Annotation-only `format` handling is not
accepted.

After a finalized decision, observability paths and bounded warnings use
stderr without changing stdout:

```text
SNAPSHOT: <absolute-path-to-run/observability/gate-decisions.html>
DASHBOARD: <absolute-path-to-root/_observability/index.html>
OBSERVABILITY_DATA: <absolute-path-to-root/_observability/gate-decisions-v1.json>
```

A path is emitted only when that artifact was successfully refreshed. Warning
codes cover conditions such as lock contention, unsafe paths, exhausted
budgets, invalid history, and publication failure. Snapshot and stable-report
failures are non-gating: they do not change verdict, exit code, `result.json`,
or the exact `VERDICT:` and `RESULT:` stdout lines.

Each exit 0, 1, or 2 run counts as one task. The report maps `PASS` to
Releasing, `FAIL` to Failing, and `NEEDS_HUMAN` to Human review. Rolling 10 and
rolling 100 use partial warm-up windows. The series exposes the latest 100
points from up to 199 retained source summaries. A custom `--output` defines a
shared scope; using one root across repositories intentionally combines them.

## Exit codes

| Exit | Meaning | `result.json` guaranteed? |
|---:|---|---|
| 0 | Candidate verdict `PASS`. | Yes |
| 1 | Candidate verdict `FAIL`. | Yes |
| 2 | Candidate verdict `NEEDS_HUMAN`. | Yes |
| 3 | Invalid CLI usage, repository/input, or configuration before a candidate verdict. | No |
| 4 | Unrecoverable internal gate failure before complete evidence/result finalization. | No |

`NEEDS_HUMAN` outranks `FAIL`: if both conditions occur, the command exits 2.
Exit 4 is not a fourth verdict. A partial run directory contains a
`.incomplete` marker only when the engine can write it through a still verified
safe handle; the marker is not guaranteed after destination identity loss. A
partial directory with or without that marker MUST NOT be consumed as an
evidence package.

SIGINT, host shutdown, disk exhaustion, or an engine defect yields exit 4 when
the engine cannot finalize a complete result. If a check process is interrupted
but the engine remains able to record and finalize the event, it is an evidence
error and yields `NEEDS_HUMAN` instead.

## Compatibility

The new CLI does not replace or proxy `demo/gate/gate.sh`. Existing demo
commands and their 0/1/2 behavior remain intact. There is no A3 request-file,
execution-result, plugin, or adapter mode in v1.

<!-- release-version-sync:start -->
The 0.3.0 assistant archives bundle `references/compatibility.json` and require
the exact output `release-gate 0.3.0` before `init`, `validate`, or `run`.
A missing executable or different version is a safe stop. Install the CLI wheel
and host archive as a separately verified, version-matched pair using the
[adoption procedure](adoption.md).
<!-- release-version-sync:end -->
