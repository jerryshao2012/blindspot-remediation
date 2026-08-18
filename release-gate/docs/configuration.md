# Configuration Reference

The repository policy is `.release-gate.yaml`. `release-gate run` always reads
that path from the resolved base commit, never from the candidate working tree.
`release-gate validate` may validate a worktree file before it is committed.
The document is YAML whose data model MUST validate against
`schemas/config-v1.schema.json`.

## Complete shape

```yaml
version: 1
scope:
  allowed_paths: ["src/**", "tests/**"]
  forbidden_paths: [".github/**"]
  review_required_paths: [".release-gate.yaml", "SECURITY.md", "LICENSE*"]
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

## Scope

Changed paths are Git repository-relative paths with `/` separators. V1 uses
`pathspec==1.1.1` and
`pathspec.PathSpec.from_lines("gitwildmatch", patterns)`. Matching is
case-sensitive on every host and uses the following closed subset of Git
wildmatch:

- `*`, `?`, and bracket classes do not cross `/`; dotfiles are not special.
- A pattern with no `/`, such as `*.md`, matches a basename at any depth.
- A pattern containing a non-terminal `/`, such as `src/*.py`, is anchored to
  repository root.
- A trailing `/` is directory-only and covers that directory's descendants,
  not a same-named regular file. Its terminal slash does not itself anchor the
  pattern, so `docs/` matches directories named `docs` at any depth.
- `**/name` matches `name` at any depth including root; `a/**/b` matches zero
  or more complete directory segments; `dir/**` matches descendants below
  `dir` but not the directory entry itself.
- Pattern lists are an unordered OR. Negation is not supported.

Patterns beginning `/`, `!`, or `#`, ending in whitespace,
absolute/drive/UNC/device paths, backslashes, `.` or `..` components, and empty
path components are invalid. The single terminal separator that gives a
directory pattern its trailing `/` semantics is the only permitted empty
component. These restrictions remove Git-ignore comments, negation, escaping,
trailing-space normalization, and host-dependent path interpretation while
retaining the matching rules above.

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
case-colliding entries in one list or map are invalid. POSIX reserves `HOME`
and `TMPDIR`; Windows reserves `USERPROFILE`, `HOMEDRIVE`, `HOMEPATH`, `TEMP`,
and `TMP`; every platform also reserves the `RELEASE_GATE_` prefix. Reserved
names are invalid in both environment fields. The engine sets them to
clone-specific locations. In particular, `PATH` is inherited only when it is
listed; the engine never adds the repository or `.` to `PATH`.

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
missing report is recorded but is an error if an assertion references it.

V1 parsers expose these JSON-shaped metrics:

- `junit-xml`: `/tests`, `/failures`, `/errors`, `/skipped`, and
  `/duration_seconds`, aggregated across suites without resolving external
  entities.
- `coverage-json`: `/percent_covered`, `/covered_lines`, `/missing_lines`,
  `/excluded_lines`, and `/statements` from coverage.py totals.
- `json-metrics`: the parsed JSON value itself; it must contain only JSON data.

`metric` is an RFC 6901 JSON Pointer. `comparison` selects `candidate`,
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
50 MiB; individual reports may set a lower `max_bytes`. Reports are never
silently truncated before parsing. `total_bytes` defaults to and cannot exceed
200 MiB per run. Exhausting the total budget stops scheduling new checks,
marks required work `SKIPPED`, and yields `NEEDS_HUMAN`.
