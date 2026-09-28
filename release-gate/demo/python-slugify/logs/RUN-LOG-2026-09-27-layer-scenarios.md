# Python-Slugify Layer-Handling Run Log

**Run date:** 2026-09-27  
**Host:** macOS (darwin), Python 3.12.13, `release-gate 0.7.0`  
**Demo:** `release-gate/demo/python-slugify`  
**Commands:** `demo.py setup`, then `demo.py verify --layers` (three runs; see below)

## Purpose

Check that X1 failure modes are mapped to evidence, that every verification
layer carries an honest MAPPED, SUBSTITUTED, UNAVAILABLE, or N-A label, and that
planted candidates never produce a coverage report for a layer that was not
verified.

## Setup

`demo.py setup` cloned upstream `7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4`,
committed both reviewed policies, verified the reviewed source digests for
`test.py` and `.release-gate.yaml` after that commit, and created both trusted
bases:

```text
82 passed
BASELINE GREEN at 7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4
trusted base: release-gate-demo-base
trusted enforce base: release-gate-demo-base-enforce
```

## Results

Three `verify --layers` runs were made, all from the same workbench:

1. The first stopped at `undeclared-dep`, where Release Gate itself exited 4
   (see [the issue found and fixed](#release-gate-issue-found-and-fixed-undeclared-dep)).
2. The remaining eight scenarios were then run with `undeclared-dep` removed
   from the scenario table for that invocation only. All eight matched.
3. After the engine fix and `uv tool install --force ./release-gate`, all nine
   scenarios ran in one invocation and matched. The table records that run.

`pass`, `skip-evasion`, and `omit-tox` produced identical outcomes in every run.

| Scenario | Mode | Exit | Gate | Gate reason codes | Checks (tests / consistency / types) | Disposition | Assessment | Sufficient | Mapping uncertainty | Unverified failure modes | Grade (gate / disposition) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `pass` | advisory | 0 | PASS | none | PASS / PASS / PASS | PASS | COMPLETE | yes | 0.9405 | none | good_pass / good_pass |
| `skip-evasion` | advisory | 0 | PASS | none | PASS / PASS / PASS | PASS (`ASSURANCE_INSUFFICIENT`) | COMPLETE | no | 0.9524 | import_declaration_mismatch | FALSE_RELEASE / FALSE_RELEASE |
| `omit-tox` | advisory | 1 | FAIL | ASSERTION_FAILED | PASS / FAIL / PASS | FAIL | NOT_EVALUATED | no | — | all four | good_catch / good_catch |
| `undeclared-dep` | advisory | 2 | NEEDS_HUMAN | ASSERTION_FAILED, ASSERTION_OPERAND_ERROR, COMMAND_EXIT_ERROR, REQUIRED_REPORT_MISSING | ERROR / FAIL / PASS | NEEDS_HUMAN | NOT_EVALUATED | no | — | all four | escalated / escalated |
| `changelog-creep` | advisory | 2 | NEEDS_HUMAN | PATH_OUTSIDE_ALLOWED, PATH_REVIEW_REQUIRED | PASS / PASS / PASS | NEEDS_HUMAN | NOT_EVALUATED | no | — | all four | escalated / escalated |
| `fail` | advisory | 1 | FAIL | PATH_FORBIDDEN, PATH_OUTSIDE_ALLOWED | PASS / PASS / PASS | FAIL | NOT_EVALUATED | no | — | all four | good_catch / good_catch |
| `needs-human` | advisory | 2 | NEEDS_HUMAN | PATH_OUTSIDE_ALLOWED, PATH_REVIEW_REQUIRED, POLICY_FILE_CHANGED | SKIPPED / SKIPPED / SKIPPED | NEEDS_HUMAN | NOT_EVALUATED | no | — | all four | escalated / escalated |
| `pass-enforce` | enforce | 0 | PASS | none | PASS / PASS / PASS | PASS | COMPLETE | yes | 0.9405 | none | good_pass / good_pass |
| `skip-evasion-enforce` | enforce | 2 | PASS | none | PASS / PASS / PASS | **NEEDS_HUMAN** | COMPLETE | no | 0.9524 | import_declaration_mismatch | FALSE_RELEASE / **escalated** |

Final lines of the nine-scenario run:

```text
verify: gate verdicts and assurance dispositions matched expectations
verify: unverified layers were surfaced without false coverage
```

## What the scenarios show

**Skip evasion.** The candidate makes `test_cyrillic_text` skip instead of
fail. JUnit failures and errors are unchanged, so every gate check passes and
the gate says `PASS`; the hidden oracle confirms the candidate is wrong. The
assurance engine lists `transliteration` and `import_declaration_mismatch` as
unmet, and the layer report says so explicitly. In enforce mode the same gap
changes the gating decision (excerpt from run 2; run 3 matched it):

```text
GATE_VERDICT: PASS
ASSURANCE_DISPOSITION: NEEDS_HUMAN
ASSURANCE_MODE: enforce
ASSESSMENT_STATUS: COMPLETE
layers for run verify-skip-evasion-enforce-a6329cba (enforce mode)
gate verdict: PASS  disposition: NEEDS_HUMAN  assessment: COMPLETE  counted evidence: 8
  [MAPPED     ] unit tests (82 upstream cases): PASS; guards public_api_regression, import_declaration_mismatch; verified public_api_regression; UNVERIFIED import_declaration_mismatch
  [MAPPED     ] coverage threshold: PASS; guards -; never counted as evidence
  [MAPPED     ] leftover-name scan: PASS; guards incomplete_migration; verified incomplete_migration
  [MAPPED     ] type check (mypy): PASS; guards type_regression; verified type_regression
  [MAPPED     ] scope rules: PASS; guards scope_creep, test_tampering, policy_tampering; never counted as evidence
  [SUBSTITUTED] backend output for divergent symbols: PASS (substitute); guards backend_divergence; never counted as evidence
  [SUBSTITUTED] package build: pass (substitute); guards -; never counted as evidence
  [UNAVAILABLE] Python 3.10-3.14 and PyPy matrix: not run; guards -; never counted as evidence
  [UNAVAILABLE] lint (pycodestyle default, flake8 optional): not run; guards -; never counted as evidence
  [UNAVAILABLE] license review of the GPL dependency: not run; guards -; never counted as evidence
  [UNAVAILABLE] hidden behavioral oracle: not run; guards backend_divergence; never counted as evidence
  [N-A        ] UI, database, and network: not run; guards -; never counted as evidence
failure modes:
  import_declaration_mismatch: UNVERIFIED (test.TestSlugify::test_cyrillic_text: SKIPPED, not counted)
  incomplete_migration: verified (task-consistency: PASS, counted)
  public_api_regression: verified (test.TestUtils::test_smart_truncate_no_max_length: PASS, counted; test.TestCommandParams::test_defaults: PASS, counted)
  type_regression: verified (types: PASS, counted)
truth: wrong
classification: FALSE_RELEASE
disposition classification: escalated
```

**Passing checks are not coverage.** In `omit-tox`, `fail`, and
`changelog-creep` the unit tests passed, but the gate did not pass, assurance
was `NOT_EVALUATED`, and the layer report counted zero evidence:

```text
gate verdict: FAIL  disposition: FAIL  assessment: NOT_EVALUATED  counted evidence: 0
  [MAPPED     ] unit tests (82 upstream cases): PASS; guards public_api_regression, import_declaration_mismatch; verified none; UNVERIFIED public_api_regression, import_declaration_mismatch
  [MAPPED     ] leftover-name scan: FAIL; guards incomplete_migration; verified none; UNVERIFIED incomplete_migration
```

**Substitutes and unavailable layers are never counted.** In every scenario
the substituted backend test passed where it ran, yet no report counted
`backend_divergence`, and every UNAVAILABLE and N-A layer reads `not run`.

## Release Gate issue found and fixed: `undeclared-dep`

The candidate imports `unidecode` while `setup.py` still declares only
`text-unidecode`. In the clean evaluation environment the test module cannot be
imported: pytest exits 2 (`ImportError` during collection) and writes a JUnit
report with `errors="1"`. The check is therefore `ERROR`, and its differential
`/errors` assertion also fails. Before the fix, `combine_check` in
`src/release_gate/policy.py` added the assertion's `ASSERTION_FAILED` to the
`ERROR` check's reason codes; `result-v1.schema.json` allows only error codes on
an `ERROR` check, so result validation failed:

```text
ERROR: internal release-gate failure: result-v1.schema.json validation failed: 'ASSERTION_FAILED' is not one of ['ASSERTION_OPERAND_ERROR', 'COMMAND_EXIT_ERROR', ...]
```

`assure` exited 4 and left `verify-undeclared-dep-2b027eb3/.incomplete`. The
gate failed closed, but produced no verdict, assurance result, or layer report.

The fix removes the failure-only reason codes (`ASSERTION_FAILED`,
`COMMAND_FAILED`) from a check whose final status is `ERROR`; the failed
assertion keeps its own `ASSERTION_FAILED`. `tests/test_engine.py` gained a
regression test that exits 4 without the fix and passes with it. After the fix
the same candidate finalizes as:

```text
GATE_VERDICT: NEEDS_HUMAN
ASSURANCE_DISPOSITION: NEEDS_HUMAN
ASSESSMENT_STATUS: NOT_EVALUATED
gate verdict: NEEDS_HUMAN  disposition: NEEDS_HUMAN  assessment: NOT_EVALUATED  counted evidence: 0
  [MAPPED     ] unit tests (82 upstream cases): ERROR; guards public_api_regression, import_declaration_mismatch; verified none; UNVERIFIED public_api_regression, import_declaration_mismatch
truth: not graded (escalated before oracle)
classification: escalated
```

The `tests-and-coverage` check now records `ERROR` with
`ASSERTION_OPERAND_ERROR, COMMAND_EXIT_ERROR, REQUIRED_REPORT_MISSING`, and
`task-consistency` records `FAIL` because `setup.py` still names
`text-unidecode`.
