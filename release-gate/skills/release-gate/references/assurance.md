# Assurance mapping reference

Use this reference during guided `init`. It adds questions and review criteria;
it does not add policy fields, execute repository code, or change Release Gate's
configured-policy-only verdict contract.

## User-approved assurance map

Build a user-approved assurance map before rendering the policy.

Before rendering a policy, show one row for every identified failure mode or
assurance claim:

- the failure mode or assurance claim;
- the repository-declared command or report that detects it, with source file
  and key citation;
- candidate or differential mode;
- severity; and
- known limitations, including what the check cannot detect.

Ask the user to approve each row. Prefer direct project checks because Release
Gate records their statuses independently. A report-only command is not a gate
unless its exit status enforces the claimed threshold.

Classify each omitted layer honestly:

- `N-A`: the failure mode or surface does not apply;
- `UNAVAILABLE`: the applicable tool or evidence is unavailable and nothing ran;
- `SUBSTITUTED`: another check ran instead; state what the substitute cannot detect.

Never describe `N-A`, `UNAVAILABLE`, `SUBSTITUTED`, `ERROR`, or `SKIPPED` work as
passed.

## Aggregate gauntlets

Accept an aggregate command only after reviewing cited source that:

- declares a fixed expected-layer manifest;
- records a layer complete only after its command succeeds;
- rejects omitted, unknown, and duplicate layers;
- emits all-green only after the final completion audit; and
- runs negative controls for omission, child failure, unknown layer, and duplicate
  completion.

Record the aggregate boundary as a limitation: Release Gate can attest the
aggregate process and exit status, but cannot independently attest unreported
internal layers.

## Custom checker integrity

Custom scanners and report readers must fail closed on unreadable or missing
input, missing or stale reports, unexpected exit codes, and internal failures.
Require a clean positive control, a known violation, and a broken-input negative
control. Coverage commands must enforce the approved threshold in their exit
status, for example with `--cov-fail-under`.

Prefer the project's mutation tool. If a manual mutation runner is approved, its
reviewed source must prove each mutant was executed, count only genuine test
failures as kills, classify collection/tool exits as errors, isolate bytecode or
equivalent caches, and restore the source byte-for-byte in every outcome. Require
a same-size, same-mtime killer-versus-equivalent negative control when timestamped
bytecode caches are relevant.

Initialization only proposes these controls from repository declarations. Never
execute them during `init`.
