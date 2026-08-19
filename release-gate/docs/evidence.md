# Evidence Contract

At the default effective evidence root, every completed run has this exact
layout:

```text
.release-gate/runs/<run-id>/
├── result.json
├── manifest.json
├── candidate.patch
├── effective-config.json
├── trace.json
└── controls/
    └── <control-id>/
        ├── base/
        │   ├── stdout.log
        │   ├── stderr.log
        │   └── reports/...
        └── candidate/
            ├── stdout.log
            ├── stderr.log
            └── reports/...
```

For an accepted custom `--output`, the subtree beginning with
`<run-id>/` is identical; only the effective root replaces
`.release-gate/runs`. The manifest stores paths relative to the run directory,
so its contents do not depend on the host root.

The default root is eligible only when the literal `.release-gate` and `runs`
components beneath the canonical repository root are absent or real
directories inspected without following links. A POSIX symlink or any Windows
reparse point/junction at either component is invalid, even if it resolves to
the same directory or to an otherwise safe location. Missing default
components are created only after candidate capture, one at a time with
no-follow/no-reparse operations. The engine pins their identities for evidence
I/O and rechecks them before and after capture, after creation, after clone
placement, before commands, and around finalization. Thus only the actual,
nonredirected default subtree receives the in-repository exception.

Candidate-only checks omit `base/`. A **control ID** is the globally unique
configured `id` of either a preparation item or a check. Each preparation
item's phase is `prepare` in the manifest; the manifest field is `control_id`
for both phases.
A configured report retains its bytes below `reports/<report-id>` with a safe
extension selected only by its parser: `.xml` for `junit-xml` and `.json` for
`coverage-json` or `json-metrics`. The longest generated filename is therefore
69 characters for a 64-character report ID and remains within the component
limit. An arbitrary source suffix is never copied into the evidence name.
Absent or truncated artifacts are represented by reason codes in the result,
trace, and manifest; empty stand-in files are not fabricated.

## Portable path components

Run IDs are 1-128 ASCII characters, begin with an ASCII letter or digit, use
only letters, digits, `.`, `_`, and `-`, and cannot end in `.`. Preparation,
check, and report IDs use the stricter 1-64-character lowercase grammar in the
configuration contract. Neither grammar permits a case-insensitive DOS device
basename (`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, or `LPT1`-`LPT9`), even
with an extension. Default run IDs use a separator-free UTC timestamp and a
random suffix that satisfy this grammar.

Every other artifact path component is 1-128 Unicode code points in NFC. It
MUST NOT contain ASCII controls U+0000-U+001F or U+007F, any of
`< > : " / \ | ? *`, or end in an ASCII space or `.`. Empty, `.`, and `..`
components and the same case-insensitive DOS device basenames, including with
extensions, are invalid. An artifact path uses `/` separators, contains at
most 32 components, and is at most 1,024 Unicode code points in total.

Before filesystem access, the engine enforces this grammar and NFC. It rejects
casefold-equivalent run-directory siblings and casefold-equivalent artifact
paths so evidence remains portable to case-insensitive filesystems.

## Stable result

`result.json`, validated by `schemas/result-v1.schema.json`, is the stable
machine interface. It contains:

- contract version, run ID, verdict, corresponding exit code, and reason codes;
- base commit, reconstructed candidate tree, patch digest, and policy digest;
- start/end timestamps and duration;
- scope findings as `changed_paths`, `outside_allowed_paths`,
  `forbidden_paths`, and `review_required_paths`;
- each check's mode, severity, status, reason codes, and assertion outcomes; and
- the relative `manifest.json` path.

The `checks` array has exactly one item for each check in
`effective-config.json`, in declaration order. At index `i`, `id`, `mode`, and
`severity` equal those of effective check `i`. This remains true after policy
or launcher review, preparation failure, budget exhaustion, or interruption:
unrun checks stay in place as `SKIPPED`. Preparation IDs do not appear in this
array; preparation executions are recorded in the manifest and trace.

Consumers decide from `verdict`, not from log text. Human messages and trace
event wording may evolve within v1. A `PASS` result means only that the
candidate satisfied the recorded policy.

## Timestamp profile

Every `created_at`, `started_at`, and `finished_at` value in result or manifest
uses the Release Gate v1 RFC 3339 profile, a documented strict subset:

```text
YYYY-MM-DDTHH:MM:SS[.1-9-digits](Z|+HH:MM|-HH:MM)
```

The spelling is ASCII with a year from 0001 through 9999 and uppercase `T` and
`Z`. The zone is mandatory.
Numeric offsets range through `+14:00` and `-14:00`; an hour of 14 requires
minutes `00`, and the RFC 3339 unknown-local-offset spelling `-00:00` is
rejected. Seconds are `00`-`59`, so leap-second spellings are rejected.
Month lengths and Gregorian leap years must be real. The engine emits UTC with
`Z`; verifiers accept the other profile offsets without rewriting stored
evidence.

JSON Schema `format` is annotation-only unless a validator enables format
assertion. Runtime validation therefore MUST use
`Draft202012Validator(..., format_checker=FormatChecker())` with the
distribution's `jsonschema[format]` dependency **and** a strict full-string
profile parser that verifies calendar reality, fraction length, offset range,
unknown offset, and leap-second rules. The custom profile parser is
authoritative; using `FormatChecker` or a general-purpose datetime parser
alone is insufficient. This validation applies while producing and while
verifying evidence.

## V1 reason-code registry

Reason-code arrays contain no duplicates and are sorted by ASCII code-point
order. A context with no applicable diagnostic uses an empty array; successful
scope, assertion, and root contexts are therefore empty, while a passing
execution/check may carry the explicitly allowed non-verdict diagnostics. The
engine never invents a success code. Unknown codes and codes used outside the
contexts below are invalid. Adding or changing a code or its meaning requires
a contract/schema version bump; v1 has no vendor-extension reason codes.

| Code | Valid context and meaning |
|---|---|
| `ASSERTION_FAILED` | check, assertion, root: valid operands did not satisfy the comparison |
| `ASSERTION_OPERAND_ERROR` | check, assertion, root: required pointer/value/type was unavailable or invalid |
| `COMMAND_EXIT_ERROR` | execution, check, root: exit was explicitly classified `error` |
| `COMMAND_EXIT_UNCLASSIFIED` | execution, check, root: exit was in no configured class |
| `COMMAND_FAILED` | execution, check, root: exit was an ordinary classified `fail` |
| `COMMAND_SIGNALLED` | execution, check, root: subprocess returned a negative POSIX signal code |
| `COMMAND_SPAWN_FAILED` | execution, check, root: executable, including a missing executable, could not be started |
| `COMMAND_TIMED_OUT` | execution, check, root: configured timeout expired |
| `CONTROL_LAUNCHER_REVIEW` | skipped execution/check, root: a directly invoked repository launcher changed |
| `EVIDENCE_BUDGET_EXHAUSTED` | execution/check/skip, root: retained-evidence capacity prevented required work or evidence |
| `INHERITED_ENVIRONMENT_MISSING` | execution, check, root: an allowlisted host variable was absent |
| `OPERATOR_INTERRUPTED` | execution/check/skip, root: an operator interruption was safely finalized |
| `OPTIONAL_REPORT_MISSING` | passing/failing execution or check only: an unreferenced optional report was absent |
| `PATH_FORBIDDEN` | scope and root: a changed path matched the denylist |
| `PATH_OUTSIDE_ALLOWED` | scope and root: a changed path matched no allowlist pattern |
| `PATH_REVIEW_REQUIRED` | scope and root: a changed path requires review |
| `POLICY_FILE_CHANGED` | skipped execution/check, root: candidate changed `.release-gate.yaml` |
| `PREPARATION_FAILED` | skipped execution/check, root: a preparation control did not pass |
| `REPORT_PARSE_FAILED` | check and root: a present declared report could not be parsed |
| `REPORT_PATH_UNSAFE` | check and root: report resolution escaped or named a non-regular file |
| `REPORT_TOO_LARGE` | check and root: a present declared report exceeded its whole-file limit |
| `REQUIRED_CONTROL_SKIPPED` | skipped execution/check and root: required work did not execute |
| `REQUIRED_REPORT_MISSING` | check and root: a required report was absent |
| `STREAM_TRUNCATED` | execution/check only: retained stdout or stderr is a prefix of a fully drained stream |

Scope arrays use only the three `PATH_*` codes. An assertion uses `[]` when
true, `ASSERTION_FAILED` when false, and `ASSERTION_OPERAND_ERROR` when its
outcome is unknown. A `PASS` execution/check may contain only the two
non-verdict diagnostics; `FAIL`, `ERROR`, and `SKIPPED` require at least one
cause allowed for that status. Every trace reason comes from this same
registry.

An execution has at most one terminal-cause code, selected in this precedence
when conditions overlap: operator interruption, timeout, signal/forced
termination, missing inherited environment, spawn failure, configured `error`
exit, unclassified exit, then ordinary classified `fail`. A skipped execution
instead has its applicable registered skip causes. Stream truncation and an
optional missing report are orthogonal diagnostics and may accompany a terminal
cause.
Required-report and assertion error codes attach to the aggregate check;
`OPTIONAL_REPORT_MISSING` may also identify the affected check-phase execution
but never a preparation. Preparation executions always have an empty metrics
map. A preparation terminal cause is recorded on that execution; the root and
dependent skipped controls additionally use `PREPARATION_FAILED`.
Policy and launcher preflights use their named code on every skipped control.
`REQUIRED_CONTROL_SKIPPED` is used only when required work is absent without a
narrower registered skip cause. Each `PATH_*` code is present if and only if
its corresponding scope path array is nonempty; general scope findings do not
short-circuit configured controls.

The result root array is the sorted union of atomic codes that contribute to
the final verdict plus run-level causes. Informational failures and optional
diagnostics remain in their child contexts unless they contribute under the
verdict rules. `manifest.json.reason_codes` exactly equals the result root
array. Finalization and verification enforce ordering, context, aggregation,
and equality in addition to JSON Schema validation.

A `FAIL` root can contain only `ASSERTION_FAILED`, `COMMAND_FAILED`,
`PATH_FORBIDDEN`, and `PATH_OUTSIDE_ALLOWED`. `NEEDS_HUMAN` must contain at
least one needs-capable atom rather than only the latter two scope failures;
an assertion/command failure qualifies only when its advisory severity makes
it human-reviewable, which is verified against the effective configuration.

## Manifest and verification

`manifest.json`, validated by `schemas/manifest-v1.schema.json`, is written
last. Its artifact array MUST contain `result.json`, `candidate.patch`,
`effective-config.json`, and `trace.json` exactly once, plus every retained
control log/report exactly once. It MUST NOT inventory `manifest.json`, because
a file cannot contain its own final digest. It records:

- the resolved base commit and reconstructed candidate tree;
- candidate patch and effective-configuration digests;
- engine version;
- operating-system, machine, and Python runtime identity;
- exact argv, clone-relative working directory, `control_id`, phase, and side
  for executions;
- environment variable names (never environment values);
- exit classification, timestamps, durations, normalized metrics, and reason
  codes; and
- artifact path, media type, retained size, digest, and any truncation facts.

### Execution lifecycle

Each scheduled preparation/check side has one manifest execution record in
schedule order, even when it is skipped. Preparation items appear first in
declaration order, base then candidate for each item when a base workspace is
required and candidate only otherwise. Checks follow in declaration order;
each differential check is base then candidate and each candidate check has
only candidate. The `control_id`, `phase`, `side`, `argv`, `cwd`, and final
environment-name set must equal the corresponding resolved effective-policy
slot. Finalization and verification enforce that cross-document identity,
cardinality, and order; JSON Schema cannot derive it from the manifest alone.

The lifecycle fields have these closed correlations:

| Classification/cause | `exit_code` | `timed_out` | Required lifecycle reason |
|---|---:|---:|---|
| `pass` | integer 0 through 4,294,967,295 | `false` | none |
| `fail` | integer 0 through 4,294,967,295 | `false` | `COMMAND_FAILED` |
| `error`, configured error exit | integer 0 through 4,294,967,295 | `false` | `COMMAND_EXIT_ERROR` |
| `error`, unclassified exit | integer 0 through 4,294,967,295 | `false` | `COMMAND_EXIT_UNCLASSIFIED` |
| `error`, POSIX signal | integer -2,147,483,648 through -1 | `false` | `COMMAND_SIGNALLED` |
| `error`, spawn failure | `null` | `false` | `COMMAND_SPAWN_FAILED` |
| `error`, inherited environment absent | `null` | `false` | `INHERITED_ENVIRONMENT_MISSING` |
| `error`, safely finalized operator interruption | `null` | `false` | `OPERATOR_INTERRUPTED` |
| `error`, timeout | `null` | `true` | `COMMAND_TIMED_OUT` |
| `skipped` | `null` | `false` | applicable registered skip cause |

The timeout record deliberately does not retain the return code produced by
subsequent platform-specific process-tree termination. A negative subprocess
return always uses the signal row, never a configured/unclassified-exit row.
`EVIDENCE_BUDGET_EXHAUSTED` can arise before a process or after its exit, so it
does not by itself choose between an integer and null exit field; a skipped
budget-limited execution still follows the skipped row. At most one registered
terminal cause appears, using the precedence in the reason-code section.

Preparation and skipped executions always have an empty metrics map. Only a
check-phase execution may carry report metrics or
`OPTIONAL_REPORT_MISSING`. Passing/failing check executions may also carry
`STREAM_TRUNCATED` without changing their lifecycle class. All other
classification, reason, phase, side, and metric combinations are invalid.

Each execution retains at most 64 assertion-referenced scalar metrics. Its key
is `<report-id>#<RFC6901-pointer>`; an empty pointer therefore appears as, for
example, `metrics#`, while `/` appears as `metrics#/`. Non-finite numbers and
unbounded report structures are never copied into the manifest. Retained
numbers are finite IEEE 754 binary64 values, encoded in the shortest
round-tripping JSON form with negative zero normalized to `0` and at most 24
ASCII bytes. All `duration_ms` fields are nonnegative signed 64-bit integers.

Recorded process exit codes preserve the inclusive range -2,147,483,648
through 4,294,967,295, covering negative POSIX signal return codes and unsigned
Windows 32-bit statuses. Signal termination still classifies as an evidence
error.

Artifact paths follow the portable component grammar above and are
repository-style relative paths. Thus leading `./`, empty/dot components,
trailing `/`, absolute/drive/UNC/device forms, and backslashes are invalid.
Each retained artifact has exactly one entry. Semantic validation rejects
duplicate lexical paths and any pair whose NFC strings have equal Unicode
`casefold()` values, even on a case-sensitive host, so a Windows verifier
cannot alias them. It also reserves the manifest's own NFC-plus-casefold key:
no artifact path may be equal under that comparison to `manifest.json`,
including `Manifest.json` and non-ASCII casefold aliases.

Verification walks the run directory (excluding `manifest.json`) and rejects
missing, extra, aliased, duplicate, changed-size, or changed-digest retained
artifacts. The exclusion is the same NFC-plus-casefold manifest key, not only
an exact-case spelling. Callers that transport evidence SHOULD hash or sign
the complete directory with an external system.

Local evidence is **tamper-evident, not immutable**. The manifest detects
changes relative to the manifest, but anyone able to rewrite both artifacts
and manifest can replace the evidence. V1 never claims filesystem immutability,
digital signing, provenance attestation, transparency logging, or remote
write-once storage.

## Supporting artifacts

`candidate.patch` is the exact binary-safe patch captured through an
invocation-owned temporary index and temporary Git object directory. Source
objects are exposed only as read-only Git alternates, using the host path-list
separator and Git's quoting rules; newly staged blobs never enter the source
or shared object database. `effective-config.json` is canonical JSON for the
validated, defaulted, platform-resolved base policy. Their SHA-256 values are
repeated in both result and manifest.

`trace.json` is a chronological JSON array of bounded engine events. Each
event uses a closed set of engine-defined fields and its canonical UTF-8 JSON
encoding is at most 500 bytes; untrusted text is represented by bounded IDs,
counts, digests, or reason codes rather than copied verbatim. At most 2,048
events are retained, including one slot reserved for a terminal summary. With
array commas/brackets, this is at most 1,026,049 bytes and therefore below the
1 MiB sublimit. It may be used for diagnosis but is not the stable decision
API. Logs preserve raw retained process bytes; the CLI does not replay
untrusted control characters to the terminal. Parsed reports are copied before
their source clones are removed.

## Size and time limits

- stdout and stderr: 1 MiB retained per stream per execution by default;
  configurable up to 10 MiB;
- each report: 5 MiB by default; configurable up to 50 MiB;
- complete run: configurable from 16 MiB through a hard 200 MiB maximum; and
- each prepare/check process: 600 seconds by default; configurable up to
  86,400 seconds.

Streams beyond their retention limit are drained and hashed to avoid process
deadlock; the artifact entry records original byte count, retained byte count,
full-stream digest, and retained-artifact digest. Reports are not truncated
before parsing. Any present unsafe, oversized, or unparsable report is an
evidence error; `required: false` permits only absence. Any such error, a
missing required report, or a report that cannot be retained whole under the
total budget makes assurance unavailable and yields `NEEDS_HUMAN`.

### Deterministic byte accounting

The total is the sum of exact byte lengths of every retained regular file
beneath the run directory: `candidate.patch`, `effective-config.json`,
`result.json`, `trace.json`, `manifest.json`, each retained control stream and
report, and `.incomplete` when safely present. Directories, pathnames,
filesystem allocation units, external staging files, and already-unlinked
same-directory temporary files are not counted. Temporary files may never
allow the final retained set to exceed the limit. The manifest does not
self-inventory, but its bytes still count. A complete package MUST be at or
below `limits.total_bytes` and the 200 MiB hard ceiling.

The `.incomplete` marker, when the safe-handle rules permit one, is an empty
regular file and contributes zero bytes; it never appears in a complete run.

Before candidate evaluation, the engine reads at most 1 MiB of raw UTF-8
configuration, serializes at most 1 MiB of canonical effective JSON, captures
the exact patch in staging outside the run, and measures both. A patch larger
than 200 MiB is always invalid; the operative feasibility test is stricter:

```text
patch_bytes + effective_config_bytes + 7,340,032 <= total_bytes
```

The 7 MiB reserve is fixed as 2 MiB for `result.json`, 4 MiB for
`manifest.json`, and 1 MiB for `trace.json`. Preflight also materializes a
maximum-size serialization skeleton from the effective policy, captured
changed-path inventory, configured sides, 24-byte numeric/4,096-code-point
string scalar limits, 19-digit duration limits, and artifact count
and proves each reserved file fits its sublimit. Any read overflow, infeasible
sum, or oversize skeleton is invalid input/configuration (exit 3): candidate
evaluation has not begun, no verdict or `result.json` is promised, and staged
files are discarded. Once accepted, the exact patch and effective
configuration are never compressed, truncated, or omitted.

The optional-evidence allowance is
`total_bytes - patch_bytes - effective_config_bytes - 7,340,032`. It is
allocated in this stable order: controls in configuration order, preparation
or check base side before candidate side, stdout before stderr, then reports
in report declaration order. Before a process starts, stdout and stderr each
receive a fixed quota no larger than `stream_bytes`; concurrent arrival order
cannot change the allocation. Unused stream quota returns only after both
streams close. A report is admitted only when its entire measured byte length
fits both its report limit and the remaining allowance; it is never retained
partially. A missing optional report uses `OPTIONAL_REPORT_MISSING`; a present
invalid/oversized report uses its `REPORT_*` error; and a report omitted for
total capacity uses `EVIDENCE_BUDGET_EXHAUSTED`.

`STREAM_TRUNCATED` alone means output exceeded its configured per-stream cap
and is non-verdict diagnostic. If the total allowance forces a stream quota
below that cap or prevents a later artifact/control, the affected context also
uses `EVIDENCE_BUDGET_EXHAUSTED` and the run becomes `NEEDS_HUMAN`.

When the allowance cannot support newly required evidence, the engine stops
scheduling controls, emits `EVIDENCE_BUDGET_EXHAUSTED`, and preserves one
ordered result entry per configured check, marking unrun checks `SKIPPED` with
the narrower `EVIDENCE_BUDGET_EXHAUSTED` cause. It still writes bounded result,
trace, and manifest from the untouched reserve and returns `NEEDS_HUMAN`. The
trace's final reserved slot summarizes any coalesced diagnostic events and
carries the budget reason when applicable. Any result over 2 MiB, manifest
over 4 MiB, trace over 1 MiB, or completed total over the configured limit
after the preflight proof is an engine invariant violation (exit 4), not a
different verdict.

## Finalization and retention

Files are created with restrictive permissions subject to host support and
are written through same-directory temporary files. `result.json` is renamed
into place only when complete; `manifest.json` is the final file. A completed
directory has no `.incomplete` marker. For the default root, opens and renames
are relative to pinned, no-follow-verified directory identities, which are
rechecked immediately before and after these final renames. A substitution
after evaluation starts yields exit 4 and no valid evidence package;
`.incomplete` is written only when the engine still holds a verified safe
directory. Run IDs are append-only: reruns use new IDs and never overwrite
prior evidence, including an NFC-plus-casefold sibling on a case-sensitive
host.

V1 does not prescribe retention duration or remote storage. Organizations may
copy, sign, or retain the package according to their own controls without
changing the local contract.
