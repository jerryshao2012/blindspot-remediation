# Release Gate Demo Private Campaign Report Design

**Date:** 2026-08-20
**Status:** Approved for implementation planning
**Scope:** `release-gate/demo/python-slugify/` only

## Purpose

The reusable Release Gate reports what decision its configured policy made. Its
continuous observability report intentionally knows only `PASS`, `FAIL`, and
`NEEDS_HUMAN`; it cannot identify a false release because that classification
also requires hidden-oracle truth.

The `python-slugify` demo already owns a hidden oracle and a `demo.py grade`
command that combines the oracle result with the gate verdict. This change will
make grading persist a private, duplicate-safe campaign record and refresh a
private JSON and HTML campaign report. The report will expose explicit counts,
denominators, and Wilson uncertainty bounds without changing the gate verdict,
gate evidence, public decision dashboard, reusable CLI, or portable skill.

## Goals

- Automatically record a real demo trial when `demo.py grade` completes.
- Detect and report `FALSE_RELEASE` outcomes by joining the recorded gate result
  with private oracle truth.
- Preserve one stable record per gate `run_id` and refuse conflicting reuse.
- Produce machine-readable JSON and a self-contained HTML report.
- Report counts with denominators, including both false releases per total
  oracle-valid trials and false releases given `PASS`.
- Report two-sided 95% Wilson intervals for campaign proportions.
- Record optional AI wall time, usage, model, and human intervention without
  estimating missing values.
- Keep hidden-oracle information outside the candidate repository and outside
  Release Gate's public observability files.
- Make deterministic verification controls exercise grading without polluting
  the campaign sample.

## Non-goals

- No new `release-gate` CLI command or portable-skill subcommand.
- No change to `result.json`, `manifest.json`, gate verdicts, exit meanings, or
  normal observability schemas.
- No automatic merge, deployment, retry, or modification of gate evidence.
- No claim that a local ignored directory provides encryption or protection
  from an administrator on the host.
- No cross-repository production campaign service in this change.
- No inference of missing token, cost, timing, or model data.
- No qualification claim based only on the generated report.

## Considered Approaches

### 1. Extend `demo.py grade` (selected)

The existing trusted grading boundary owns oracle execution and classification,
so it is the smallest place to persist private campaign truth. One command
performs the already-required grade and refreshes the report.

### 2. Add a separate demo reporter

A second script could ingest grade output, but it would duplicate result
parsing and create an avoidable handoff where a grade can be printed but never
recorded.

### 3. Add reusable CLI and skill commands

This would make campaign reporting generic, but it would expand the product
contract, require a generic private-oracle protocol, and tempt assistants to
access hidden evaluation material during normal gate operation. That is outside
this demo-focused requirement.

## Trust Boundary

The data flow remains one-way:

```text
candidate workbench
    -> Release Gate run
    -> tamper-evident gate result and candidate.patch
    -> private demo grader reconstructs recorded candidate
    -> hidden oracle
    -> private campaign record and report
```

Oracle truth must never feed back into `result.json`, change the gate verdict,
or cause an automatic gate retry. The portable Release Gate skill remains
unchanged and therefore never reads or reports hidden-oracle data.

The report directory will be
`release-gate/demo/python-slugify/private-campaign/`, outside the generated
candidate repository. It will be added to that demo's `.gitignore`. "Private"
means local, ignored, and not linked from the public gate dashboard. It is not
encrypted; operators remain responsible for filesystem access to the checkout.

## User Interface

The existing grade command gains optional campaign metadata:

```bash
python3 demo.py grade \
  --result "/absolute/path/to/result.json" \
  --run-kind trial \
  --wall-seconds 103 \
  --usage-value 16.6 \
  --usage-unit AIC \
  --model claude-haiku-4.5 \
  --human-step none
```

Only `--result` remains required. `--run-kind` is a closed choice of `trial`,
`re-gate`, or `control` and defaults to `trial`. Only `trial` records enter the
primary campaign denominators. A human-fixed rerun must use `re-gate`; a
manually graded deterministic control must use `control`. Missing optional
values are stored as `null` and displayed as `unknown`. `--usage-value` and
`--usage-unit` must either both be supplied or both be omitted. Numeric values
must be finite and non-negative. Text metadata is length-bounded and treated as
display data, never as a command. `--human-step` remains descriptive metadata;
it does not select the statistical cohort.

Successful grading continues to print truth and classification, followed by:

```text
CAMPAIGN_RECORD: <absolute-path-to-record.json>
CAMPAIGN_REPORT: <absolute-path-to-index.html>
CAMPAIGN_DATA: <absolute-path-to-campaign-v1.json>
```

A read-only regeneration command rebuilds aggregate outputs from stored records
without invoking the gate or oracle:

```bash
python3 demo.py campaign-report
```

The internal `demo.py verify` control flow will call grading with campaign
recording disabled. Controls therefore validate classification logic but do not
enter the real-trial denominator. The README will tell operators not to use
the default `trial` kind for manually demonstrated controls or re-gates; a
primary campaign row represents one independent trial.

## Candidate-to-Oracle Binding

Campaign truth must describe the candidate identified by the supplied gate
result, not whichever files happen to remain in the mutable workbench.

Before running the oracle, grading will:

1. Resolve and parse `result.json` and require its complete evidence package.
2. Read `candidate.patch` from the same run directory.
3. Verify its SHA-256 equals `result.json.patch_sha256`.
4. Reconstruct a fresh disposable oracle workspace from
   `result.json.base_commit` plus the recorded patch.
5. Verify the reconstructed Git tree equals `result.json.candidate_tree`.
6. Install the candidate and run the hidden oracle against that reconstructed
   workspace.

The oracle source remains outside the reconstructed repository. The disposable
workspace and its virtual environment are removed in all outcomes. This permits
grading a completed run even after the main workbench was reset and prevents a
stale workbench from being paired with an unrelated `result.json`.

## Stored Record

Each successful or oracle-error grading attempt writes
`private-campaign/records/<run-id>.json`. The v1 record contains:

- schema version and run ID;
- gate verdict, finish time, gate duration, base commit, candidate tree,
  patch SHA-256, and configuration SHA-256;
- SHA-256 of the complete source `result.json` bytes;
- oracle truth (`true`, `false`, or `null` for evaluator error);
- classification: `good_pass`, `FALSE_RELEASE`, `FALSE_BLOCK`, `good_catch`,
  `escalated`, or `oracle_error`;
- SHA-256 of the hidden oracle source;
- grading timestamp;
- structured run kind (`trial`, `re-gate`, or `control`);
- optional AI wall seconds, usage value/unit, model, and human-step text.

The record contains no oracle test names, assertions, stdout, stderr, candidate
source, environment values, or secrets. The report presents classifications
and aggregate metrics, not hidden test details.

## Idempotency and Conflicts

The run ID is the record identity.

- If no record exists, grading publishes one atomically.
- If an existing record has the same stable gate/oracle identity and identical
  supplied metadata, grading is idempotent: it preserves the original record
  and grading timestamp, then regenerates the report.
- If the same run ID is presented with a different result hash, patch/config
  identity, oracle identity/outcome, or metadata, grading stops with a conflict
  error and does not overwrite the record or aggregate report.

Operators must provide optional metadata on the first recorded grade. Later
metadata editing is outside v1; this avoids an untracked mutable history.

## Oracle Errors

An inability to produce trustworthy oracle truth is not evidence that the
candidate is wrong. If repository reconstruction succeeds but oracle setup or
execution cannot yield a binary correct/wrong result, grading records
`oracle_error` with `oracle_truth: null`, refreshes the report, and returns a
non-zero command status after printing the record/report paths.

Oracle errors count in total attempted grades and in an explicit oracle-error
count. They are excluded from every correctness and false-release denominator.
No error is silently converted into `wrong`, `FAIL`, or `NEEDS_HUMAN`.

Failures before a record can be safely bound to a valid run—invalid result,
missing or mismatched patch, candidate-tree mismatch, unsafe path, or invalid
metadata—produce no campaign record.

## Aggregate Report

`campaign-v1.json` is deterministically rebuilt from valid record files sorted
by `(gate finished time, run_id)`. `index.html` is a self-contained escaped view
of the same data. Both include a generation hash derived from the ordered record
identities so consumers can detect mismatched JSON and HTML generations. The
report lists every stored record but computes primary safety, automation, cost,
and Wilson metrics only from records whose run kind is `trial`. Re-gates and
controls have separate counts and tables and never enter primary denominators.

The report includes raw counts and denominators for:

- total records and counts by run kind;
- primary trial attempts, oracle-valid primary trials, and primary-trial oracle
  errors;
- `good_pass`, `FALSE_RELEASE`, `FALSE_BLOCK`, `good_catch`, and `escalated`;
- automated decisions (`PASS` or `FAIL`) per oracle-valid trial;
- false releases per oracle-valid total;
- false releases given `PASS`;
- false blocks per oracle-valid total;
- escalations per oracle-valid total.

Each primary-trial proportion contains numerator, denominator, point estimate,
lower bound, upper bound, confidence level `0.95`, and method `wilson`. A zero
denominator produces `null` estimate and bounds rather than an invented zero.

Timing and usage summaries state their own known-value denominators. Wall time
reports count, total, mean, minimum, and maximum. Usage is grouped by exact unit
and reports the same fields; unlike units are never added together. Unknown
values remain visible through missing-value counts. Model and human-step values
are categorical counts, not quality scores.

The report states these limitations prominently:

- a gate `PASS` is not proof of correctness;
- the private oracle supplies the truth label;
- small samples have wide uncertainty;
- repeated X1 trials measure X1 repeatability, not general Release Gate safety;
- correlated trials and benchmark/oracle quality limit interpretation.

## Wilson Calculation

The demo will implement the two-sided Wilson score interval using only the
Python standard library. The event of interest is passed explicitly—for
example, `false_releases` successes in `automated_passes` trials. The function
will validate `0 <= events <= trials` and `0 < confidence < 1`.

The implementation will be checked against the README's zero-event examples:
approximately 43% for 0/5, 28% for 0/10, 16% for 0/20, 11% for 0/30, and 4%
for 0/100 at 95% confidence.

## Filesystem and Publication Behavior

- `private-campaign/` and `records/` are created outside the candidate
  repository with owner-only permissions where the host supports them.
- Symlink/reparse redirection of the private root, records directory, existing
  record, or aggregate outputs is refused.
- Regeneration validates every discovered record against the supported v1
  shape and semantics. A malformed, unsupported, symlinked, or conflicting
  record stops regeneration; it is never skipped or partially counted, and the
  last complete aggregate outputs remain untouched.
- JSON and HTML are first written to unique sibling temporary files, flushed,
  and atomically replaced.
- A record is published before aggregates. If aggregate refresh fails, the
  command reports the warning/error and `campaign-report` can rebuild from the
  durable record.
- Report generation never changes the already recorded gate result or exit
  meaning.
- Dynamic HTML content is escaped; the report contains no executable external
  scripts or network resources.

## Documentation Changes

The demo README will:

- explain why the normal gate dashboard cannot identify false releases;
- document the extended `grade` command and `campaign-report` regeneration;
- show the private output layout and privacy limitations;
- define every classification and denominator;
- distinguish controls, independent trials, and human-assisted re-gates;
- explain the Wilson table and the limits of repeated X1 trials.

The root Release Gate README may link to the demo section, but the portable
skill and reusable CLI command summary remain unchanged.

## Testing Strategy

Implementation will follow test-first development. Tests will cover:

1. Parser acceptance and validation for optional campaign metadata and the
   `campaign-report` command.
2. Exact classification for all gate/oracle combinations and `oracle_error`.
3. Candidate patch digest and candidate-tree binding, including stale-workbench
   grading and mismatch refusal.
4. First record publication, idempotent repeat, and conflicting run-ID refusal.
5. Oracle-error persistence and exclusion from correctness denominators.
6. Wilson known values, zero denominators, and invalid inputs.
7. Counts and distinct denominators for false releases per total versus given
   `PASS`.
8. Primary-trial cohort selection excludes structured `re-gate` and `control`
   records regardless of descriptive human-step text.
9. Known/unknown wall-time and usage aggregation, including separation by unit.
10. Deterministic JSON/HTML generation, generation-hash agreement, and HTML
   escaping.
11. Atomic publication failure behavior, fail-closed malformed-record handling,
    and symlink/reparse refusal.
12. `verify` controls do not create campaign records.
13. `.gitignore` and README documentation contain the private-output contract.
14. Existing Release Gate, observability, demo, skill, archive, and packaging
    tests remain unchanged in meaning and continue to pass.

## Acceptance Criteria

- Grading a recorded wrong candidate with gate verdict `PASS` creates a
  `FALSE_RELEASE` record and displays it in private JSON and HTML reports.
- The normal Release Gate dashboard still displays only gate decisions and is
  byte-contract compatible with v0.3.0 behavior.
- Regrading an identical run cannot double-count it; conflicting reuse cannot
  overwrite it.
- The campaign report exposes numerators, denominators, and Wilson bounds rather
  than a composite quality score.
- Hidden oracle contents remain outside candidate and public evidence/report
  artifacts.
- Structured `control` and `re-gate` records are visible but excluded from every
  independent primary-trial metric and denominator.
- The demo documentation provides a complete macOS and Windows workflow.
