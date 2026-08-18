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
  allowed: ["src/**", "tests/**"]
  forbidden: [".release-gate.yaml", ".github/**"]
  review: ["SECURITY.md", "LICENSE*"]
prepare:
  argv: ["python3", "-m", "pip", "install", "-e", ".[test]"]
  cwd: "."
  timeout: 600
  environment: {CI: "true"}
  exit_classes: {pass: [0], fail: [1], error: []}
  platform:
    windows:
      argv: ["py", "-3", "-m", "pip", "install", "-e", ".[test]"]
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
    environment: {CI: "true"}
    exit_classes: {pass: [0], fail: [1], error: [2, 3, 4, 5]}
    platform:
      windows:
        argv: ["py", "-3", "-m", "pytest", "--junitxml=junit.xml"]
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

Changed paths are Git repository-relative paths with `/` separators. Patterns
support `*` and `?` within a segment, character classes, and `**` across
segments. Patterns MUST NOT be absolute, contain `..` segments or backslashes,
begin with `!`, or have a Windows drive prefix such as `C:`. Leading `/`, UNC
and device paths, drive-absolute and drive-relative paths, and traversal are
invalid. A path matches a list when it matches any pattern.

- `allowed` is a required allowlist. A changed path outside it is blocking.
- `forbidden` is a blocking denylist, even if the path is also allowed.
- `review` requires human review, even if the path is allowed.

All applicable matches are retained. Because `NEEDS_HUMAN` outranks `FAIL`, a
review match dominates a simultaneous forbidden/out-of-scope failure in the
final verdict. Renames evaluate both old and new paths; deletions evaluate the
old path. Symlinks are matched as paths and are not traversed.

## Commands and platform overrides

`prepare` is optional and runs once in each clean clone. Repositories needing
multiple preparation steps SHOULD call a checked-in script. A preparation
result other than `pass` prevents complete evaluation and yields
`NEEDS_HUMAN`.

Every check requires a unique `id`, `mode`, `severity`, and non-empty `argv`.
The ID `prepare` is reserved. `argv` is passed directly to a process without a
shell; shell operators, expansion, and quoting have no special meaning.
`cwd` is relative to the clone root and cannot escape it. `environment` is a
literal string map overlaid on the engine's minimal environment; there is no
variable interpolation.

`platform` may contain `linux`, `macos`, and `windows`. For the current host,
provided `argv`, `cwd`, `timeout`, and `exit_classes` replace their common
values; environment keys merge over the common map. Unspecified fields retain
the common value. The resulting command must still validate.

A directly invoked repository-local launcher is an effective `argv[0]` that
resolves inside the clone rather than through the host `PATH`. Every such
common or platform-specific launcher MUST match `scope.review`. Scope is
evaluated before command execution. If a candidate changes a launcher, no
prepare/check command runs and the result is `NEEDS_HUMAN`; the changed bytes
are not executed. This rule does not make candidate source or test inputs
trusted.

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

`blocking` failures affect the verdict, and blocking errors or skipped checks
require human review. `advisory` and `informational` statuses are retained but
do not affect the verdict; advisory failures are highlighted above purely
informational observations.

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
declared report. Those rules, pairwise-disjoint exit codes, and mode/comparison
compatibility, negative codes outside the error class, and uncovered local
launchers are semantic validation errors (exit 3), even where JSON Schema
cannot express them.

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
