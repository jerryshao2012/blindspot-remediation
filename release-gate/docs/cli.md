# CLI Contract

The installed console command is `release-gate`. It supports exactly three v1
subcommands: `init`, `validate`, and `run`.

## `init`

```text
release-gate init [--repo PATH] [--profile generic|python|node]
```

`--repo` defaults to the current directory and `--profile` to `generic`. The
command writes `.release-gate.yaml` from the matching built-in v1 example and
then validates it. It never overwrites an existing file; an existing target,
non-repository path, or write failure is exit 3. The operator must tailor and
commit the policy before `run`, because runs trust only base-revision policy.

## `validate`

```text
release-gate validate [--repo PATH] [--config PATH]
```

The default input is `<repo>/.release-gate.yaml`. This command performs YAML
parsing, JSON Schema 2020-12 validation, semantic validation, defaults, and
host-platform resolution without running repository commands. Success prints
the config version and check count. Validation diagnostics go to stderr, use
document paths, contain no traceback for expected errors, and exit 3.

`--config` is a convenience for validating an uncommitted file. It is not
accepted by `run` and cannot override trusted base policy.

## `run`

```text
release-gate run --base REF [--repo PATH] [--run-id ID]
                 [--evidence-root PATH]
```

`--repo` defaults to the current directory. `--base` is required and must
resolve to a local commit. `--run-id` defaults to a separator-free UTC
timestamp plus random suffix. It is a 1-128-character ASCII component that
begins with a letter or digit, then uses only letters, digits, `.`, `_`, and
`-`, cannot end in `.`, and cannot have a case-insensitive DOS device basename
`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, or `LPT1`-`LPT9`, even with an
extension. This allowed set excludes ASCII controls, empty/dot/dotdot names,
spaces, and Windows-illegal `<>:"/\|?*`. An existing or
NFC-plus-casefold-equivalent sibling run directory is never overwritten.

The default evidence root is `<repo>/.release-gate/runs`. A relative custom
`--evidence-root` is anchored to the invocation working directory, not to
`--repo`. Before candidate capture, the engine resolves the repository root,
its `.git` entry, per-worktree Git directory from `git rev-parse --git-dir`,
shared metadata directory from `git rev-parse --git-common-dir`, the evidence
root, and the proposed `<root>/<run-id>` through every existing ancestor and
symlink. Git-reported paths are first made absolute. Nonexistent suffixes are
appended to the canonical nearest existing ancestor. The engine performs
component-aware containment using native case rules, never string-prefix
comparison, and repeats canonicalization after creating the directory; any
identity change is exit 3.

Only a root whose canonical identity equals the canonical default is the
engine-owned in-repository exception, whether selected implicitly or by an
equivalent spelling. Only the exact repository-relative
`.release-gate/runs/` subtree is excluded from candidate capture. Every other
custom root is rejected if either its normalized spelling or canonical target
or any existing-prefix identity encountered while resolving it is equal to or
below the source repository, its `.git` entry, its per-worktree Git directory,
or its shared Git common directory. This catches an in-repository symlink that
later resolves outward as well as an outside alias that resolves inward. The
default exception permits only source-worktree containment: it is still
rejected if its canonical root or run directory enters either Git metadata
directory or an execution clone. A custom root that is an ancestor of a
protected path is accepted only when the final run directory is disjoint from
every protected path. The engine creates clones elsewhere and rechecks before
executing commands. Symlink aliases do not bypass any containment check. A user
therefore cannot hide candidate files by choosing another in-repository
evidence path.

Preflight resolves the base, reads `.release-gate.yaml` from it, validates the
policy, checks the source repository and evidence destination, and only then
captures the working tree through a temporary index. Invalid refs,
invalid/missing policy, ambiguous input, patch reconstruction failure, or an
unsafe evidence path exit 3 before a candidate verdict.

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
printed.

## Exit codes

| Exit | Meaning | `result.json` guaranteed? |
|---:|---|---|
| 0 | Candidate verdict `PASS`. | Yes |
| 1 | Candidate verdict `FAIL`. | Yes |
| 2 | Candidate verdict `NEEDS_HUMAN`. | Yes |
| 3 | Invalid CLI usage, repository/input, or configuration before a candidate verdict. | No |
| 4 | Unrecoverable internal gate failure before complete evidence/result finalization. | No |

`NEEDS_HUMAN` outranks `FAIL`: if both conditions occur, the command exits 2.
Exit 4 is not a fourth verdict. If a partial run directory exists, it contains
a `.incomplete` marker and MUST NOT be consumed as an evidence package.

SIGINT, host shutdown, disk exhaustion, or an engine defect yields exit 4 when
the engine cannot finalize a complete result. If a check process is interrupted
but the engine remains able to record and finalize the event, it is an evidence
error and yields `NEEDS_HUMAN` instead.

## Compatibility

The new CLI does not replace or proxy `demo/gate/gate.sh`. Existing demo
commands and their 0/1/2 behavior remain intact. There is no A3 request-file,
execution-result, plugin, or adapter mode in v1.
