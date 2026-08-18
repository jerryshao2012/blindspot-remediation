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

## Candidate reconstruction

`run` resolves `--base` to a commit before executing anything. It reads
`.release-gate.yaml` from that commit, not from candidate-modified bytes.
Missing or invalid base policy is an input/configuration error (exit 3).

To capture the complete non-ignored working-tree state without changing the
developer's real index, the engine:

1. creates a temporary Git index;
2. populates it with the base tree using `git read-tree`;
3. stages the current working tree into that temporary index with
   `git add -A`, including non-ignored untracked files and deletions; and
4. emits a binary-safe staged diff against the base commit.

Ignored files and `.git/` are excluded by Git. The engine hashes the patch,
applies it to the clean candidate clone, writes the reconstructed candidate
tree object, and records that tree ID. A patch that cannot be reconstructed
unambiguously is invalid candidate input (exit 3). The real index, working
tree, and base repository are never mutated.

Candidate edits to `.release-gate.yaml` never change the policy used for the
current run. Other repository scripts are judged by their configured scope;
directly invoked launchers have the stronger rule below.

Every directly invoked repository-local prepare/check launcher, including a
launcher selected by a platform override, MUST be covered by `scope.review`.
This is a semantic configuration requirement. Scope is evaluated before any
repository process starts. If the candidate changes one of those launchers,
the engine runs no prepare or check command, marks them `SKIPPED` with
`CONTROL_LAUNCHER_REVIEW`, and returns `NEEDS_HUMAN`. Candidate-modified
launcher bytes are never executed. Candidate source, tests, and other command
inputs remain the code under evaluation and may execute on the trusted host.

## Execution flow

```text
source repository
  -> resolve base + load/validate base policy
  -> capture working-tree patch through temporary index
  -> create independent base and candidate clones
  -> evaluate scope and stop on a changed repository-local launcher
  -> run optional prepare command in each required clone
  -> run configured checks
  -> parse bounded reports and evaluate assertions
  -> aggregate verdict (NEEDS_HUMAN > FAIL > PASS)
  -> atomically finalize result.json, then manifest.json
```

Commands are argv arrays and run without a shell. Relative `cwd` values are
resolved inside the relevant clone. A platform override (`linux`, `macos`, or
`windows`) overlays the common command definition. Checks run in declaration
order. A differential check runs base first and candidate second; a candidate
check runs only in the candidate clone. V1 deliberately provides no plugin or
adapter hook that can alter this flow.

The optional `prepare` command runs independently in both clones before any
check. Any prepare spawn failure, timeout, non-pass exit, or interrupted run
means required evidence is unavailable and produces `NEEDS_HUMAN` with a
finalized result. Checks that could not run are marked `SKIPPED`.

## Check evaluation

Each process exit is classified by `exit_classes` as `pass`, `fail`, or
`error`. An unlisted exit, spawn failure, signal termination, timeout, missing
required report, oversized required report, or parse failure is `ERROR`.

For `candidate` mode, the candidate exit class is the initial check status.
For `differential` mode, `error` on either side is `ERROR`; otherwise a
candidate `fail` is a check failure only when the base was `pass`. A candidate
that stays at `fail` or improves to `pass` has not regressed on the exit-class
dimension. Assertions can still fail the check.

Report assertions select a normalized metric from the candidate, baseline,
or numeric candidate-minus-baseline value and compare it with a literal using
`eq`, `ne`, `gt`, `gte`, `lt`, or `lte`. Invalid metric types or unavailable
required operands are evidence errors, not candidate failures.

## Severity and verdict aggregation

- `blocking`: `FAIL` contributes `FAIL`; `ERROR` or `SKIPPED` contributes
  `NEEDS_HUMAN`.
- `advisory`: status and reasons are prominently recorded but do not affect
  the verdict.
- `informational`: observations are recorded but do not affect the verdict.

Scope is an engine invariant and always contributes to the verdict. A changed
path outside `scope.allowed` or matching `scope.forbidden` contributes
`FAIL`. A path matching `scope.review` contributes `NEEDS_HUMAN`. All matches
are retained, so a review requirement outranks a simultaneous failure.

Aggregation is deterministic:

1. any blocking evidence error, skipped blocking check, prepare error, or
   review-scoped path -> `NEEDS_HUMAN`;
2. otherwise any blocking check failure or scope violation -> `FAIL`;
3. otherwise -> `PASS`.

This precedence is not configurable.

## Failure boundaries

Once candidate evaluation begins, expected operational failures are captured
as evidence and yield `NEEDS_HUMAN`, not exit 4. Exit 4 is reserved for an
engine defect or host failure that prevents complete evidence and
`result.json` finalization. Partial directories are retained with a
`.incomplete` marker and are not valid evidence packages.

The engine writes run artifacts to temporary names, fsyncs where supported,
renames `result.json` only after it is complete, and writes `manifest.json`
last. An existing run ID is never overwritten.

## Portability

Paths in policy and evidence use repository-relative POSIX separators.
Commands use native argv without shell syntax. Platform overrides are explicit
and limited to the three v1 operating-system families. Required verification
covers Linux, macOS, and Windows, filenames with spaces and Unicode, binary
patches, symlinks where Git supports them, timeouts, signals, and interrupted
runs.
