# Standalone Release Gate Design

## Product boundary

The release gate judges an already-created repository change. It does not
generate or repair code, deploy software, call hidden oracles, or reinterpret
its own verdict. V1 consists of:

1. an independently installable Python 3.11+ `release-gate` CLI;
2. versioned configuration, result, and evidence contracts; and
3. a portable skill that invokes the CLI and reports `result.json` verbatim.

The package MUST NOT import A-series or B-series packages. V1 has no plugin,
adapter, remote runner, or project-specific service dependency.

## Trust and isolation model

The engine, its installed schemas, and policy read from the selected base
revision are trusted. The source working tree, candidate patch, commands,
reports, and command output are untrusted data. Execution occurs on a trusted
host without a security sandbox. Base and candidate commands can execute
arbitrary repository code, so operators MUST use only repositories and
changes they are willing to run with their own account privileges.

The gate creates an evidence directory outside both execution clones and two
separate disposable, clean clones:

- **base clone:** checked out at the resolved base commit;
- **candidate clone:** checked out at the same commit, then given the captured
  patch.

No check runs in the developer's source working tree, and the engine provides
no shared build directory between clones. Repository policy MUST keep generated
virtual environments, dependency directories, and reports inside the relevant
clone; a trusted policy can otherwise defeat this separation by naming a
shared or absolute location.

## Evidence destination preflight

Before candidate capture, the engine canonicalizes the source worktree, its
`.git` entry, the absolute per-worktree `--git-dir`, and the absolute shared
`--git-common-dir`. A relative custom root is anchored to the invocation
working directory. The selected evidence spelling is lexically normalized
without following it, then classified as the literal default candidate or a
custom root. The default branch performs the no-follow walk below before any
evidence-root or run-directory canonicalization. Only the custom branch
canonically resolves those paths through existing ancestors. Containment uses
path components and native case rules rather than string prefixes, and the
engine checks both normalized spellings and every existing-prefix identity
encountered during custom resolution.

The sole in-repository exception is the nonredirected directory chain formed
by joining the literal `.release-gate` and `runs` components to the canonical
repository root. Under native filesystem case rules, the selected spelling
must normalize to that exact path. Each existing component is inspected
without following it and must be a real directory, not a symbolic link,
junction, or any other Windows reparse point. A symlink spelling or redirected
component does not qualify merely because it canonically reaches the same
target. Missing components remain absent until candidate capture is complete.

The engine performs this no-follow inspection before capture, checks the
default node itself before applying the descendant exclusion, and repeats the
inspection immediately after capture. It therefore rejects tracked and
untracked candidate redirects instead of masking them. These checks are
read-only and an unsafe-destination exit 3 leaves the source, index, and status
unchanged. After capture, missing components are created one at a time using
no-follow/no-reparse operations rooted at a verified directory. The engine
pins and revalidates their filesystem identities after creation, after clone
placement, before configured preparation/check commands, and before and after
finalization; all evidence operations are relative to those pinned identities.
Empty scaffolding created by this invocation is rolled back on a pre-execution
rejection.

The default exception permits containment only in that verified source
subtree, never in Git metadata or a clone. A custom root may not equal or be
below the source, either Git metadata directory, or a clone. It may be an
ancestor of a protected path only when its final `<run-id>` directory is
disjoint from every protected path. The engine chooses clone locations that
are also disjoint from the effective evidence root. Candidate evaluation
begins immediately before invariant policy/launcher and configured-scope
evaluation, after capture, destination creation, clone placement, and a final
identity check. A destination failure before that exact transition is invalid
input (exit 3). Identity loss after the transition makes safe finalization
impossible (exit 4), never a candidate verdict.

## Candidate reconstruction

`run` resolves `--base` to a commit before executing anything. It reads
`.release-gate.yaml` from that commit, not from candidate-modified bytes.
Missing or invalid base policy is an input/configuration error (exit 3).

To capture the complete non-ignored working-tree state without changing the
developer's real index, the engine:

1. creates a temporary Git index;
2. populates it with the base tree using `git read-tree`;
3. stages the current working tree into that temporary index with
   `git add -A`, including non-ignored untracked files and deletions but
   excluding descendants of only the literal, no-follow-verified-or-absent
   default `.release-gate/runs/` subtree; and
4. emits a binary-safe staged diff against the base commit.

Ignored files and `.git/` are excluded by Git. The engine hashes the patch,
applies it to the clean candidate clone, writes the reconstructed candidate
tree object, and records that tree ID. A patch that cannot be reconstructed
unambiguously is invalid candidate input (exit 3). The real index, working
tree candidate bytes, and base repository are never mutated. Default evidence
directories may be created only after capture and only through the verified
nonredirected chain described above.

Any candidate addition, modification, rename, or deletion of
`.release-gate.yaml` is a non-configurable preflight review condition. The
engine still uses policy from the base, executes no configured preparation or
check command, marks every configured control `SKIPPED` with
`POLICY_FILE_CHANGED`, and finalizes `NEEDS_HUMAN`. Scope configuration cannot
weaken this invariant.

Every directly invoked repository-local prepare/check launcher, including a
launcher selected by a platform override, MUST be covered by
`scope.review_required_paths`. This is a semantic configuration requirement.
Scope is evaluated before any repository process starts. If the candidate
changes one of those launchers, the engine runs no preparation or check
command, marks every configured control `SKIPPED` with
`CONTROL_LAUNCHER_REVIEW`, and returns `NEEDS_HUMAN`. Candidate-modified
launcher bytes are never executed. Candidate source, tests, and other command
inputs remain the code under evaluation and may execute on the trusted host.

## Execution flow

```text
source repository
  -> resolve base + load/validate base policy
  -> read-only canonical/no-follow validation of evidence destination
  -> capture working-tree patch through temporary index
  -> revalidate and safely create/pin evidence destination
  -> create independent base and candidate clones
  -> revalidate and begin candidate evaluation
  -> evaluate invariant policy/launcher tamper and configured scope
  -> run ordered preparation steps in each required clone
  -> run configured checks
  -> parse bounded reports and evaluate assertions
  -> aggregate verdict (NEEDS_HUMAN > FAIL > PASS)
  -> revalidate, atomically finalize result.json then manifest.json, revalidate
```

Commands are argv arrays and run without a shell. Relative `cwd` values are
resolved inside the relevant clone. A platform override (`linux`, `macos`, or
`windows`) overlays the common command definition. Checks run in declaration
order. A differential check runs base first and candidate second; a candidate
check runs only in the candidate clone. V1 deliberately provides no plugin or
adapter hook that can alter this flow.

`prepare` is an optional ordered array of explicitly identified command
specifications. The base workspace is required when at least one differential
check exists; the candidate workspace is always required. For each preparation
item in declaration order, the engine runs base first when required and
candidate second before advancing to the next item. Its `id` is the stable
evidence ID under `controls/<id>/<side>/`, and all preparation and check IDs
are unique together.

Any preparation `fail` or `error`, spawn failure, timeout, missing inherited
environment variable, or interruption yields `NEEDS_HUMAN`, stops remaining
preparation and all checks, and records the unrun required controls as
`SKIPPED`. Preparation is infrastructure setup and never produces `FAIL`.

## Check evaluation

Each process exit is classified by `exit_classes` as `pass`, `fail`, or
`error`. An unlisted exit, spawn failure, signal termination, timeout, missing
required report, oversized required report, or parse failure is `ERROR`.

For `candidate` mode, the candidate exit class is the initial check status.
For `differential` mode, `error` on either side is `ERROR`; otherwise a
candidate `fail` is a check failure only when the base was `pass`. A candidate
that stays at `fail` or improves to `pass` has not regressed on the exit-class
dimension. Assertions can still fail the check.

An ordinary classified `fail` never short-circuits the other differential
side or any later check. Both sides and subsequent checks still run so a later
evidence error can correctly outrank a failure. A check-level `ERROR` also does
not stop later checks when the host and evidence budget remain usable. The
only scheduling stops are preflight policy/launcher review, preparation
failure, global evidence-budget exhaustion, operator interruption, or an
unrecoverable engine/host failure.

Report assertions use an RFC 6901 pointer to select a normalized metric from
the candidate, baseline, or numeric candidate-minus-baseline value and compare
it with a literal using `eq`, `ne`, `gt`, `gte`, `lt`, or `lte`. The empty
pointer selects the entire parsed report value; `/` selects an empty-key member.
Invalid metric types or unavailable required operands are evidence errors, not
candidate failures.

## Severity and verdict aggregation

| Severity | `PASS` | ordinary classified `FAIL` | `ERROR` or required `SKIPPED` |
|---|---|---|---|
| `blocking` | no effect | contributes `FAIL` | contributes `NEEDS_HUMAN` |
| `advisory` | no effect | contributes `NEEDS_HUMAN` | contributes `NEEDS_HUMAN` |
| `informational` | no effect | recorded only | contributes `NEEDS_HUMAN` |

Timeout, missing tool, signal termination, unclassified exit, preparation
failure, missing/invalid/oversized required report, assertion operand error,
and required skip always contribute `NEEDS_HUMAN`, regardless of severity.
Severity can soften an ordinary informational failure; it cannot turn missing
required assurance into a pass.

Scope is an engine invariant and always contributes to the verdict. A changed
path outside `scope.allowed_paths` or matching `scope.forbidden_paths`
contributes `FAIL`. A path matching `scope.review_required_paths` contributes
`NEEDS_HUMAN`. All matches are retained, so a review requirement outranks a
simultaneous failure.

Aggregation is deterministic:

1. policy-file/launcher preflight review, any required-evidence error or skip,
   preparation failure, advisory failure, or review-required path ->
   `NEEDS_HUMAN`;
2. otherwise any blocking check failure or forbidden/out-of-scope path ->
   `FAIL`;
3. otherwise -> `PASS`.

This precedence is not configurable.

## Failure boundaries

Once candidate evaluation begins, expected operational failures are captured
as evidence and yield `NEEDS_HUMAN`, not exit 4. Exit 4 is reserved for an
engine defect or host failure that prevents complete evidence and
`result.json` finalization. A partial directory has a `.incomplete` marker only
when the engine retains a verified safe handle through which to write it; no
marker is guaranteed after destination identity loss. No partial directory is
a valid evidence package.

The engine writes run artifacts to temporary names, fsyncs where supported,
renames `result.json` only after it is complete, and writes `manifest.json`
last. An existing or portable-casefold-equivalent run ID is never overwritten.

## Portability

Paths in policy and evidence use repository-relative POSIX separators. Every
engine-created filesystem component follows the bounded portable grammar in
the configuration, CLI, and evidence contracts; artifact components are NFC
and are checked for Unicode-casefold collisions. Commands use native argv
without shell syntax. Platform overrides are explicit and limited to the three
v1 operating-system families. Required verification covers Linux, macOS, and
Windows, filenames with spaces and Unicode, binary patches, symlinks where Git
supports them, timeouts, signals, and interrupted runs.
