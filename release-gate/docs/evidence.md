# Evidence Contract

Every completed run has this exact layout:

```text
.release-gate/runs/<run-id>/
├── result.json
├── manifest.json
├── candidate.patch
├── effective-config.json
├── trace.json
└── controls/
    └── <check-id>/
        ├── base/
        │   ├── stdout.log
        │   ├── stderr.log
        │   └── reports/...
        └── candidate/
            ├── stdout.log
            ├── stderr.log
            └── reports/...
```

Candidate-only checks omit `base/`. Each ordered preparation item uses its own
configured `id` in the same globally unique namespace as check IDs; its phase
is `prepare` in the manifest. The manifest field named `check_id` carries that
preparation ID when `phase` is `prepare`; it is the control ID for both phases.
A configured report retains its bytes below `reports/<report-id>` with a safe
extension derived from the source path.
Absent or truncated artifacts are represented by reason codes in the result,
trace, and manifest; empty stand-in files are not fabricated.

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

Consumers decide from `verdict`, not from log text. `reason_codes` are stable
uppercase identifiers; human messages and trace events are descriptive and
may evolve within v1. A `PASS` result means only that the candidate satisfied
the recorded policy.

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
- exact argv, clone-relative working directory, phase and side for executions;
- environment variable names (never environment values);
- exit classification, timestamps, durations, normalized metrics, and reason
  codes; and
- artifact path, media type, retained size, digest, and any truncation facts.

Recorded process exit codes preserve the inclusive range -2,147,483,648
through 4,294,967,295, covering negative POSIX signal return codes and unsigned
Windows 32-bit statuses. Signal termination still classifies as an evidence
error.

Artifact paths are Unicode NFC, repository-style relative paths. They cannot
start `./`, contain empty, `.` or `..` components, end `/`, use backslashes,
or be absolute/drive/UNC/device paths. Each retained artifact has exactly one
entry. Semantic validation rejects duplicate lexical paths and any pair whose
NFC strings have equal Unicode `casefold()` values, even on a case-sensitive
host, so a Windows verifier cannot alias them. It also reserves the manifest's
own NFC-plus-casefold key: no artifact path may be equal under that comparison
to `manifest.json`, including `Manifest.json` and non-ASCII casefold aliases.

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

`candidate.patch` is the exact binary-safe patch captured through the
temporary index. `effective-config.json` is canonical JSON for the validated,
defaulted, platform-resolved base policy. Their SHA-256 values are repeated in
both result and manifest.

`trace.json` is a chronological JSON array of bounded engine events. It may be
used for diagnosis but is not the stable decision API. Logs preserve raw
retained process bytes; the CLI does not replay untrusted control characters
to the terminal. Parsed reports are copied before their source clones are
removed.

## Size and time limits

- stdout and stderr: 1 MiB retained per stream per execution by default;
  configurable up to 10 MiB;
- each report: 5 MiB by default; configurable up to 50 MiB;
- complete run: 200 MiB maximum retained evidence; and
- each prepare/check process: 600 seconds by default; configurable up to
  86,400 seconds.

Streams beyond their retention limit are drained and hashed to avoid process
deadlock; the artifact entry records original byte count, retained byte count,
full-stream digest, and retained-artifact digest. Reports are not truncated
before parsing. A required oversized report or exhausted total budget makes
evidence incomplete and therefore yields `NEEDS_HUMAN`.

## Finalization and retention

Files are created with restrictive permissions subject to host support and
are written through same-directory temporary files. `result.json` is renamed
into place only when complete; `manifest.json` is the final file. A completed
directory has no `.incomplete` marker. Run IDs are append-only: reruns use new
IDs and never overwrite prior evidence.

V1 does not prescribe retention duration or remote storage. Organizations may
copy, sign, or retain the package according to their own controls without
changing the local contract.
