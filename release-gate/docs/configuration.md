# Configuration Reference

The repository policy is `.release-gate.yaml`. `release-gate run` always reads
that path from the resolved base commit, never from the candidate working tree.
`release-gate validate` may validate a worktree file before it is committed.
The document is YAML whose data model MUST validate against
`schemas/config-v1.schema.json`.

`release-gate init --from-config PATH` validates an approved source with this
same contract before mutating the target repository, caps the source at 1 MiB,
and copies its exact bytes rather than parsing and reserializing it. The source
must be an ordinary non-reparse file; symbolic links, FIFOs, devices,
directories, and other special files are rejected before a nonblocking,
no-follow open. Descriptor/path identity, size/change metadata, and two reads
are compared before validation. These checks detect ordinary concurrent edits
but are not an atomic snapshot against a hostile same-user writer. Plain
`release-gate init` continues to create the generic draft.

## Complete shape

```yaml
version: 1
scope:
  allowed_paths: ["src/**", "tests/**", "/README.md"]
  forbidden_paths: [".github/**"]
  review_required_paths: ["/.release-gate.yaml", "/SECURITY.md", "/LICENSE*"]
prepare:
  - id: dependencies
    argv: ["python3", "-m", "pip", "install", "-e", ".[test]"]
    cwd: "."
    timeout: 600
    inherit_environment: ["PATH"]
    environment: {PIP_DISABLE_PIP_VERSION_CHECK: "1"}
    exit_classes: {pass: [0], fail: [1], error: []}
    platform:
      windows:
        argv: ["py", "-3", "-m", "pip", "install", "-e", ".[test]"]
        inherit_environment: ["PATH", "PATHEXT", "SYSTEMROOT"]
limits:
  stream_bytes: 1048576
  report_bytes: 5242880
  total_bytes: 209715200
checks:
  - id: tests
    mode: differential
    severity: blocking
    argv: ["python3", "-m", "pytest", "--junitxml=junit.xml"]
    cwd: "."
    timeout: 600
    inherit_environment: ["PATH"]
    environment: {CI: "true"}
    exit_classes: {pass: [0], fail: [1], error: [2, 3, 4, 5]}
    platform:
      windows:
        argv: ["py", "-3", "-m", "pytest", "--junitxml=junit.xml"]
        inherit_environment: ["PATH", "PATHEXT", "SYSTEMROOT"]
    reports:
      - id: junit
        parser: junit-xml
        path: junit.xml
        required: true
        max_bytes: 5242880
    assertions:
      - report: junit
        metric: /failures
        comparison: candidate-minus-baseline
        operator: lte
        value: 0
```

Unknown keys are invalid. Defaults are applied only after schema and semantic
validation; `effective-config.json` records the fully defaulted,
platform-resolved policy used by the run.

## Portable identifiers

Preparation, check, and report `id` values are filesystem components in the
evidence tree. They contain 1-64 ASCII characters, begin with `a`-`z`, use only
lowercase letters, digits, `.`, `_`, and `-`, and cannot end in `.`. They MUST
NOT have a case-insensitive DOS device basename: `CON`, `PRN`, `AUX`, `NUL`,
`COM1` through `COM9`, or `LPT1` through `LPT9`, including before an extension
(`con.json` is invalid). This stricter ASCII grammar also excludes control
characters and every Windows-illegal component character.

Preparation and check IDs share one global namespace. Report IDs are unique
within their check. The implementation applies these rules before creating an
evidence path.

## Scope

Changed paths are Git repository-relative paths with `/` separators. V1 uses
`pathspec==1.1.1` and
`pathspec.PathSpec.from_lines("gitwildmatch", patterns)`. Matching is
case-sensitive on every host and uses the following closed subset of Git
wildmatch:

- `*`, `?`, and bracket classes do not cross `/`; dotfiles are not special.
- A pattern with no `/`, such as `*.md`, matches a basename at any depth.
- One leading `/` anchors the pattern to repository root and is not a
  filesystem absolute path: `/README.md` selects the root entry named
  `README.md` (and its descendants if that entry is a directory), `/*.md`
  excludes `docs/x.md`, and `/docs/` matches only the root directory and its
  descendants.
- A pattern containing a non-terminal `/`, such as `src/*.py`, is anchored to
  repository root.
- A trailing `/` is directory-only and covers that directory's descendants,
  not a same-named regular file. Its terminal slash does not itself anchor the
  pattern, so `docs/` matches directories named `docs` at any depth.
- `**/name` matches `name` at any depth including root; `a/**/b` matches zero
  or more complete directory segments; `dir/**` matches descendants below
  `dir` but not the directory entry itself.
- Pattern lists are an unordered OR. Negation is not supported.

Exactly one optional leading `/` is permitted as the repository-root anchor.
A bare `/`, `//`, a leading `!` or `#`, trailing whitespace, drive/UNC/device
syntax (including after the optional anchor), backslashes, `.` or `..`
components, and empty path components are invalid. The one terminal separator
that gives a directory pattern its trailing `/` semantics is the only
permitted empty component. These restrictions remove Git-ignore comments,
negation, escaping, trailing-space normalization, and host-dependent
filesystem interpretation while retaining the matching rules above.

- `allowed_paths` is a required allowlist. A changed path outside it is
  blocking.
- `forbidden_paths` is a blocking denylist, even if the path is also allowed.
- `review_required_paths` requires human review, even when the path is allowed.

All applicable matches are retained. Because `NEEDS_HUMAN` outranks `FAIL`, a
review match dominates a simultaneous forbidden/out-of-scope failure in the
final verdict. Renames evaluate both old and new paths; deletions evaluate the
old path. Symlinks are matched as paths and are not traversed.

Any candidate change to `.release-gate.yaml` is an invariant preflight
`NEEDS_HUMAN`, even if a policy omits it from `review_required_paths`. All
examples include it to make the invariant visible. No configured command runs
after this condition is found.

## Preparation and commands

`prepare` is an optional ordered array. Every item requires a unique `id` and
an ordinary command specification. IDs are unique across preparation items
and checks and are stable evidence directory names. The engine needs the base
workspace if any check is differential and always needs the candidate
workspace. For each item in declaration order, it runs base first when
required and candidate second before advancing to the next item. A preparation
result other than `pass` stops later preparation and checks and yields
`NEEDS_HUMAN` regardless of exit classification.

Every check requires a unique `id`, `mode`, `severity`, and non-empty `argv`.
`argv` is passed directly to a process without a shell; shell operators,
expansion, and quoting have no special meaning. `cwd` is relative to the clone
root and cannot escape it.

## Environment

No host variable is inherited implicitly. `inherit_environment` is the closed,
explicit allowlist of host environment names for that command. A requested
name absent on the execution host is an evidence error, not an empty value.
`environment` is a literal string map; values have no interpolation and SHOULD
NOT contain secrets because the effective configuration is retained.

The effective environment is built in this order:

1. copy only present, explicitly named `inherit_environment` variables;
2. overlay literal `environment` values, which win on the same name; and
3. inject engine-owned home and temporary-directory values, which always win.

On Linux and macOS names and duplicates are case-sensitive. On Windows they
are compared case-insensitively and canonicalized to uppercase in evidence;
case-colliding entries in one list or map are invalid. Every platform reserves
`HOME` and the `RELEASE_GATE_` prefix. POSIX additionally reserves `TMPDIR`;
Windows additionally reserves `USERPROFILE`, `HOMEDRIVE`, `HOMEPATH`, `TEMP`,
and `TMP`. Reserved-name comparison follows those platform identity rules, so
every case variant of a reserved name or prefix is reserved on Windows.

Reserved names are invalid in both environment fields. The engine injects a
clone-specific `HOME` on every platform after configured values. It also
injects clone-specific `TMPDIR` on POSIX and consistent clone-specific
`USERPROFILE`, `HOMEDRIVE`, `HOMEPATH`, `TEMP`, and `TMP` values on Windows.
In particular, `PATH` is inherited only when it is listed; the engine never
adds the repository or `.` to `PATH`.

## Platform overrides

`platform` may contain `linux`, `macos`, and `windows`. For the current host,
provided `argv`, `cwd`, `timeout`, `exit_classes`, and `inherit_environment`
replace their common values; literal `environment` keys overlay the common
map. Unspecified fields retain the common value. The resulting command must
still validate.

A directly invoked repository-local launcher is an effective `argv[0]` that
resolves inside the clone rather than through the host `PATH`. Every such
common or platform-specific launcher MUST match
`scope.review_required_paths`. Scope is evaluated before command execution. If
a candidate changes a launcher, no configured command runs and the result is
`NEEDS_HUMAN`; the changed bytes are not executed. This rule does not make
candidate source or test inputs trusted.

Timeout defaults to 600 seconds and cannot exceed 86,400 seconds. Exit-class
integers use the inclusive range -2,147,483,648 through 4,294,967,295 so the
evidence can preserve negative POSIX signal return codes and unsigned Windows
32-bit statuses. Signal termination is always `error`; a negative code may
only appear in the `error` class. Spawn failure, timeout, and any unlisted exit
are also evidence errors. The `pass`, `fail`, and `error` arrays must be
pairwise disjoint. Defaults are `pass: [0]`, `fail: [1]`, and `error: []`;
unlisted exits remain errors.

Manifest execution records use one normalized lifecycle on every platform.
A `pass` or `fail` has a nonnegative integer exit code and `timed_out: false`.
An explicitly configured `error` exit or an unclassified exit also has its
nonnegative integer status. A negative subprocess return is always
`COMMAND_SIGNALLED`; a timeout is always `COMMAND_TIMED_OUT` with a null exit
code and `timed_out: true`. Failure before a child starts—including a missing
executable, which is `COMMAND_SPAWN_FAILED`—a missing inherited variable, and
a safely finalized operator interruption all use a null exit code and
`timed_out: false`. A skipped control likewise has a null exit code,
`timed_out: false`, and no metrics. Platform-specific termination statuses are
normalized to these records before policy aggregation.

## Modes and severities

`candidate` runs only against the reconstructed candidate. `differential`
runs independently against base and candidate. In differential mode, an error
on either side is `ERROR`; otherwise the exit-class dimension fails only when
the candidate regresses from `pass` to `fail`. Assertions may independently
fail it.

An ordinary classified failure never short-circuits the other differential
side or later checks. When the host and evidence budget remain usable, a
check-level error also does not suppress later independent checks.

| Severity | ordinary `FAIL` | `ERROR` or required `SKIPPED` |
|---|---|---|
| `blocking` | `FAIL` | `NEEDS_HUMAN` |
| `advisory` | `NEEDS_HUMAN` | `NEEDS_HUMAN` |
| `informational` | recorded only | `NEEDS_HUMAN` |

Timeout, missing tool or inherited variable, signal, unclassified exit,
preparation failure, required-report problem, invalid assertion operand, and
required skip always produce `NEEDS_HUMAN` regardless of severity.

## Reports and assertions

Report paths are POSIX-style, clone-root-relative single files without globs
or traversal. A required report that is missing, escapes through a symlink,
exceeds its limit, or cannot be parsed makes the check `ERROR`. An optional
missing report is recorded but is an error if an assertion references it. If
an optional report exists but is unsafe, oversized, or unparsable, it is
`ERROR`; `required: false` permits absence, not invalid content. A report that
cannot be retained whole under the total evidence allowance produces
`EVIDENCE_BUDGET_EXHAUSTED` and `NEEDS_HUMAN` regardless of `required`.

V1 parsers expose these JSON-shaped metrics:

- `junit-xml`: `/tests`, `/failures`, `/errors`, `/skipped`, and
  `/duration_seconds`, aggregated across suites without resolving external
  entities.
- `coverage-json`: `/percent_covered`, `/covered_lines`, `/missing_lines`,
  `/excluded_lines`, and `/statements` from coverage.py totals.
- `json-metrics`: the parsed JSON value itself; it must contain only JSON data.

`metric` is an RFC 6901 JSON Pointer. The empty pointer `""` selects the entire
parsed JSON value, which permits scalar-root `json-metrics` assertions while
the ordinary assertion type rules still apply; `/` instead selects an object
member whose key is the empty string. `comparison` selects `candidate`,
`baseline`, or numeric `candidate-minus-baseline`. The last two are valid only
for differential checks, and subtraction requires finite numbers. `operator`
is `eq`, `ne`, `gt`, `gte`, `lt`, or `lte`. Ordered comparisons require
compatible finite numbers; invalid or unavailable operands are `ERROR`.

Report IDs are unique within a check, and every assertion must reference a
declared report. Preparation/check IDs are globally unique. Those rules,
pairwise-disjoint exit codes, mode/comparison compatibility, negative codes
outside the error class, platform-resolved environment-name collisions or
reserved names, and uncovered local launchers are semantic validation errors
(exit 3), even where JSON Schema cannot express them.

## Evidence budgets

`stream_bytes` applies separately to stdout and stderr for each execution. It
defaults to 1 MiB and may be raised to at most 10 MiB. The engine keeps
draining and hashing a larger stream but retains only the configured prefix
and records truncation.

`report_bytes` defaults to 5 MiB per report and may be raised to at most
50 MiB. An individual `max_bytes` must not exceed the effective
`limits.report_bytes`; reports are never silently truncated before parsing.

`total_bytes` is 16-200 MiB and defaults to 200 MiB. Every retained regular
file in the run directory counts by exact byte length, including the patch,
effective configuration, result, trace, manifest, logs, and copied reports.
The engine reserves exactly 7 MiB before candidate evaluation: 2 MiB for
`result.json`, 4 MiB for `manifest.json`, and 1 MiB for `trace.json`. The raw
UTF-8 YAML and canonical UTF-8 effective JSON are each limited to 1 MiB.
Preflight stages and measures the exact patch and effective JSON and requires
`patch + effective-config + 7 MiB <= total_bytes`; failure is invalid input
(exit 3) before a verdict or `result.json`. An accepted patch and effective
configuration are retained byte-for-byte and never truncated.

Once evaluation starts, the remaining non-finalization bytes are allocated in
declaration order. Prefix-bounded streams are drained fully; reports are kept
whole or rejected, never partially retained. Budget exhaustion stops new
controls, leaves every unrun check in `result.json` as `SKIPPED`, and yields
`NEEDS_HUMAN`. The accounting and deterministic allocation algorithm are
normative in [Evidence Contract](evidence.md#deterministic-byte-accounting).

## Structural bounds

V1 bounds policy shape before execution: at most 32 preparation items, 128
checks, 16 reports and 64 assertions per check, 256 entries in each scope
list, 64 argv entries, 64 names in each literal/inherited environment
collection, and 256 exit codes per class. A platform literal map may add 64
disjoint keys to the common map, while its inherited list replaces the common
list; after overlap and up to six engine-owned Windows keys, a manifest
execution can therefore record at most 198 environment names. Paths, scope
patterns, and metric pointers are at most 1,024 Unicode code points; argv
elements, literal environment values, and string assertion values are at most
4,096; environment names are at most 128. JSON numeric inputs and parsed
numeric metrics must be finite IEEE 754 binary64 values within
`±1.7976931348623157e308`. The canonical encoder uses the shortest
round-tripping JSON representation, normalizes negative zero to `0`, and emits
at most 24 ASCII bytes per number.

These are schema limits, not evidence entitlements. Semantic preflight also
builds the maximum-size result/manifest skeleton implied by the actual
effective policy and rejects it with exit 3 unless `result.json` can remain at
most 2 MiB, `manifest.json` at most 4 MiB, and `trace.json` at most 1 MiB.
This accounts for every configured check in order, the captured changed-path
inventory, both required sides, bounded scalar slots, and every possible
retained artifact entry. It prevents a schema-valid but structurally extreme
policy from consuming the finalization reserve.
