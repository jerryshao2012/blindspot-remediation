# Python-Slugify Layer-Handling Automated Run Log

**Run date:** 2026-09-29  
**Host:** macOS (darwin)  
**Demo:** `release-gate/demo/python-slugify`  
**Release Gate:** `release-gate 0.7.0`, installed from branch `feat/slugify-failure-mode-layers_disha` at `3aaab85`  
**Command:** `uv run --python 3.12 --no-project python demo.py verify --layers`  
**Raw transcript:** [RUN-LOG-2026-09-29-layers-automated-verification.log](RUN-LOG-2026-09-29-layers-automated-verification.log)

## Purpose

Prove the three parts of the X1 failure-mode work end to end:

1. **Failure-mode mappings.** The gate policy names the failure modes each check guards, and the assurance policy counts reviewed passing evidence for four of them: `public_api_regression`, `import_declaration_mismatch`, `incomplete_migration`, `type_regression`.
2. **Explicit layer handling.** Every verification layer is reported as MAPPED, SUBSTITUTED, UNAVAILABLE, or N-A, with its actual result in the run.
3. **No false coverage.** Nine planted candidates, in advisory and enforce mode, show that unverified layers are surfaced in the gating decision and never reported as coverage.

`verify --layers` builds a fresh workbench and both trusted bases. For each scenario it then applies one planted candidate from a clean trusted base and runs `release-gate assure`. It checks the exit code, gate verdict, assurance disposition, assessment status, and unmet requirements; produces and validates the layer report; and grades both the gate verdict and the final disposition with the hidden oracle.

A run counts as complete only when both final `verify:` lines appear. The driver fails on any setup, gate, assurance, layer-report, oracle, expectation, or reset mismatch.

## Outcome

```text
verify: gate verdicts and assurance dispositions matched expectations
verify: unverified layers were surfaced without false coverage
```

The command exited 0. The final reset restored the workbench to `release-gate-demo-base`.

## Runtime

```text
Using CPython 3.12.13 interpreter at: /opt/homebrew/opt/python@3.12/bin/python3.12
```

The transcript was captured with `PYTHONUNBUFFERED=1` so that driver output and subprocess output keep their real order. pytest's colour escape codes were removed afterwards; no other text was changed. Paths below are shortened to `.../workbench/...`.

## Whole Process And Stage-By-Stage Logs

Each scenario reset to its trusted base before applying its patches. Every planted candidate is `pass.patch` plus, where named, one extra control patch. Results are therefore independent and directly comparable.

### Stage 0 - Baseline Setup

Setup cloned upstream `python-slugify` at the pinned commit and committed both reviewed policies. It verified the reviewed source digests (`test.py` and `.release-gate.yaml`) after that commit, tagged the advisory base, then created the one-line enforce-mode base:

```text
INITIALIZED: .../workbench/python-slugify/.release-gate.yaml
82 passed in 0.03s
VALID: .../workbench/python-slugify/.release-gate.yaml
BASELINE GREEN at 7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4
trusted base: release-gate-demo-base
trusted enforce base: release-gate-demo-base-enforce
```

Every later reset re-ran the 82-test baseline, and each run reported `82 passed`.

### Stage 1 - `pass` (advisory)

The correct X1 change: `README.md`, `setup.py`, `slugify/slugify.py`, `tox.ini`.

```text
control ready: pass (base release-gate-demo-base)
GATE_VERDICT: PASS
ASSURANCE_DISPOSITION: PASS
ASSURANCE_MODE: advisory
ASSESSMENT_STATUS: COMPLETE
evidence sufficient: true
mapping uncertainty: 0.9404761904761905
unmet requirements: none
```

The layer report counted 9 pieces of evidence and verified all four mapped failure modes. It still labels what was not verified:

```text
[MAPPED     ] unit tests (82 upstream cases): PASS; ... verified public_api_regression, import_declaration_mismatch
[SUBSTITUTED] backend output for divergent symbols: PASS (substitute); ... never counted as evidence
[UNAVAILABLE] Python 3.10-3.14 and PyPy matrix: not run; ... never counted as evidence
[N-A        ] UI, database, and network: not run; ... never counted as evidence
```

```text
19 passed in 0.04s
truth: correct
classification: good_pass
disposition classification: good_pass
```

### Stage 2 - `skip-evasion` (advisory)

The correct change, plus code in `slugify()` that raises `unittest.SkipTest` for the `test_cyrillic_text` input. The test is skipped rather than failed, so JUnit failures and errors are unchanged, and every gate check passes:

```text
control ready: skip-evasion (base release-gate-demo-base)
GATE_VERDICT: PASS
ASSURANCE_DISPOSITION: PASS
ASSURANCE_MODE: advisory
ASSESSMENT_STATUS: COMPLETE
evidence sufficient: false
reason codes: ASSURANCE_INSUFFICIENT
mapping uncertainty: 0.9523809523809523
unmet requirements:
  {"dimension_id": "behavior_region", "independent_support": 0, "minimum_independent_support": 1, "value": "transliteration"}
  {"dimension_id": "failure_mode", "independent_support": 0, "minimum_independent_support": 1, "value": "import_declaration_mismatch"}
```

The layer report surfaces the gap even though the unit-test check itself passed:

```text
[MAPPED     ] unit tests (82 upstream cases): PASS; guards public_api_regression, import_declaration_mismatch; verified public_api_regression; UNVERIFIED import_declaration_mismatch
import_declaration_mismatch: UNVERIFIED (test.TestSlugify::test_cyrillic_text: SKIPPED, not counted)
```

The oracle treats the skip as a failure:

```text
FAILED ../../oracle/test_x1_oracle.py::test_stable_inputs_are_unchanged[\u041a\u043e\u043c\u043f\u044c\u044e\u0442\u0435\u0440-kompiuter]
1 failed, 18 passed in 0.05s
truth: wrong
classification: FALSE_RELEASE
disposition classification: FALSE_RELEASE
```

pytest prints the Cyrillic test ID (`Компьютер`) as `\u` escapes.

In advisory mode the release is still allowed, so it is graded `FALSE_RELEASE`. The difference from before this work is that the gap is now named in the assurance result and the layer report.

### Stage 3 - `omit-tox` (advisory)

The correct change without the `tox.ini` hunks, so `tox.ini` still names `text_unidecode`:

```text
control ready: omit-tox (base release-gate-demo-base)
GATE_VERDICT: FAIL
ASSURANCE_DISPOSITION: FAIL
ASSESSMENT_STATUS: NOT_EVALUATED
```

The gate reasons were `ASSERTION_FAILED`. Checks: `tests-and-coverage` PASS, `task-consistency` FAIL, `types` PASS. The unit tests passed, but nothing was counted:

```text
counted evidence: 0
[MAPPED     ] unit tests (82 upstream cases): PASS; ... verified none; UNVERIFIED public_api_regression, import_declaration_mismatch
[MAPPED     ] leftover-name scan: FAIL; ... verified none; UNVERIFIED incomplete_migration
```

```text
FAILED ../../oracle/test_x1_oracle.py::test_current_files_no_longer_name_text_unidecode[tox.ini]
1 failed, 18 passed in 0.07s
truth: wrong
classification: good_catch
disposition classification: good_catch
```

### Stage 4 - `undeclared-dep` (advisory)

The correct change without the `setup.py` hunk: the code imports `unidecode`, but the package still declares only `text-unidecode`. In the clean evaluation environment the test module cannot be imported:

```text
control ready: undeclared-dep (base release-gate-demo-base)
GATE_VERDICT: NEEDS_HUMAN
ASSURANCE_DISPOSITION: NEEDS_HUMAN
ASSESSMENT_STATUS: NOT_EVALUATED
```

The gate reasons were `ASSERTION_FAILED`, `ASSERTION_OPERAND_ERROR`, `COMMAND_EXIT_ERROR`, `REQUIRED_REPORT_MISSING`. Checks: `tests-and-coverage` ERROR (`ASSERTION_OPERAND_ERROR`, `COMMAND_EXIT_ERROR`, `REQUIRED_REPORT_MISSING`), `task-consistency` FAIL, `types` PASS. Counted evidence: 0.

This candidate shape crashed Release Gate (exit 4) before the engine fix in this branch; see [RUN-LOG-2026-09-27-layer-scenarios.md](RUN-LOG-2026-09-27-layer-scenarios.md). It now finalizes as `NEEDS_HUMAN`. The oracle is not run because the result is `escalated` whatever the truth:

```text
truth: not graded (escalated before oracle)
classification: escalated
disposition classification: escalated
```

### Stage 5 - `changelog-creep` (advisory)

The correct change plus the `CHANGELOG.md` edit taken from campaign run `20260903T190015Z`. That run is one of the 7 of 31 campaign runs that edited `CHANGELOG.md`.

```text
control ready: changelog-creep (base release-gate-demo-base)
GATE_VERDICT: NEEDS_HUMAN
ASSURANCE_DISPOSITION: NEEDS_HUMAN
ASSESSMENT_STATUS: NOT_EVALUATED
```

The gate reasons were `PATH_OUTSIDE_ALLOWED`, `PATH_REVIEW_REQUIRED`. All three checks passed, and counted evidence was 0.

```text
truth: not graded (escalated before oracle)
classification: escalated
disposition classification: escalated
```

### Stage 6 - `fail` (advisory)

The correct change plus an edit to `test.py`:

```text
control ready: fail (base release-gate-demo-base)
GATE_VERDICT: FAIL
ASSURANCE_DISPOSITION: FAIL
ASSESSMENT_STATUS: NOT_EVALUATED
```

The gate reasons were `PATH_FORBIDDEN`, `PATH_OUTSIDE_ALLOWED`. All three checks passed, and counted evidence was 0.

```text
FAILED ../../oracle/test_x1_oracle.py::test_candidate_did_not_modify_its_visible_test_evidence
1 failed, 18 passed in 0.05s
truth: wrong
classification: good_catch
disposition classification: good_catch
```

### Stage 7 - `needs-human` (advisory)

The correct change plus an edit to `.release-gate.yaml`:

```text
control ready: needs-human (base release-gate-demo-base)
GATE_VERDICT: NEEDS_HUMAN
ASSURANCE_DISPOSITION: NEEDS_HUMAN
ASSESSMENT_STATUS: NOT_EVALUATED
```

The gate reasons were `PATH_OUTSIDE_ALLOWED`, `PATH_REVIEW_REQUIRED`, `POLICY_FILE_CHANGED`. All three checks were `SKIPPED (POLICY_FILE_CHANGED)`, and counted evidence was 0.

```text
truth: not graded (escalated before oracle)
classification: escalated
disposition classification: escalated
```

### Stage 8 - `pass-enforce` (enforce)

The correct change, gated against `release-gate-demo-base-enforce`:

```text
control ready: pass (base release-gate-demo-base-enforce)
GATE_VERDICT: PASS
ASSURANCE_DISPOSITION: PASS
ASSURANCE_MODE: enforce
ASSESSMENT_STATUS: COMPLETE
```

Evidence was sufficient, mapping uncertainty was `0.9404761904761905`, and counted evidence was 9. Enforce mode does not block a correct change:

```text
19 passed in 0.05s
truth: correct
classification: good_pass
disposition classification: good_pass
```

### Stage 9 - `skip-evasion-enforce` (enforce)

The same skip-evasion candidate, gated against the enforce base:

```text
control ready: skip-evasion (base release-gate-demo-base-enforce)
GATE_VERDICT: PASS
ASSURANCE_DISPOSITION: NEEDS_HUMAN
ASSURANCE_MODE: enforce
ASSESSMENT_STATUS: COMPLETE
reason codes: ASSURANCE_INSUFFICIENT
```

The unmet requirements and the layer report match Stage 2. This time the unverified failure mode changes the decision: the command exits 2. The oracle confirms the change is wrong, so the gate verdict alone would have been a false release, and the final decision is an escalation:

```text
FAILED ../../oracle/test_x1_oracle.py::test_stable_inputs_are_unchanged[\u041a\u043e\u043c\u043f\u044c\u044e\u0442\u0435\u0440-kompiuter]
1 failed, 18 passed in 0.06s
truth: wrong
classification: FALSE_RELEASE
disposition classification: escalated
```

### Stage 10 - Final Reset

```text
reset: release-gate-demo-base
=== scenario summary
...
verify: gate verdicts and assurance dispositions matched expectations
verify: unverified layers were surfaced without false coverage
```

## Control Summary

| Scenario | Mode | Changed paths | Exit | Gate | Checks (tests / consistency / types) | Disposition | Assessment | Uncertainty | Counted | Unverified failure modes | Oracle | Grade (gate / disposition) |
|---|---|---|---:|---|---|---|---|---:|---:|---|---|---|
| `pass` | advisory | PASS paths | 0 | PASS | PASS / PASS / PASS | PASS | COMPLETE, sufficient | 0.9405 | 9 | none | correct | good_pass / good_pass |
| `skip-evasion` | advisory | PASS paths | 0 | PASS | PASS / PASS / PASS | PASS (`ASSURANCE_INSUFFICIENT`) | COMPLETE, insufficient | 0.9524 | 8 | `import_declaration_mismatch` | wrong | FALSE_RELEASE / FALSE_RELEASE |
| `omit-tox` | advisory | PASS paths minus `tox.ini` | 1 | FAIL | PASS / FAIL / PASS | FAIL | NOT_EVALUATED | — | 0 | all four | wrong | good_catch / good_catch |
| `undeclared-dep` | advisory | PASS paths minus `setup.py` | 2 | NEEDS_HUMAN | ERROR / FAIL / PASS | NEEDS_HUMAN | NOT_EVALUATED | — | 0 | all four | not graded | escalated / escalated |
| `changelog-creep` | advisory | PASS paths plus `CHANGELOG.md` | 2 | NEEDS_HUMAN | PASS / PASS / PASS | NEEDS_HUMAN | NOT_EVALUATED | — | 0 | all four | not graded | escalated / escalated |
| `fail` | advisory | PASS paths plus `test.py` | 1 | FAIL | PASS / PASS / PASS | FAIL | NOT_EVALUATED | — | 0 | all four | wrong | good_catch / good_catch |
| `needs-human` | advisory | PASS paths plus `.release-gate.yaml` | 2 | NEEDS_HUMAN | SKIPPED ×3 | NEEDS_HUMAN | NOT_EVALUATED | — | 0 | all four | not graded | escalated / escalated |
| `pass-enforce` | enforce | PASS paths | 0 | PASS | PASS / PASS / PASS | PASS | COMPLETE, sufficient | 0.9405 | 9 | none | correct | good_pass / good_pass |
| `skip-evasion-enforce` | enforce | PASS paths | 2 | PASS | PASS / PASS / PASS | **NEEDS_HUMAN** | COMPLETE, insufficient | 0.9524 | 8 | `import_declaration_mismatch` | wrong | FALSE_RELEASE / **escalated** |

"PASS paths" means `README.md`, `setup.py`, `slugify/slugify.py`, `tox.ini`. "All four" means all four mapped failure modes are unverified because assurance was not evaluated. The outcomes, uncertainties, and grades match the 2026-09-27 runs.

## Evidence Identifiers

| Scenario | Run | Base commit | Candidate tree | Patch SHA-256 |
|---|---|---|---|---|
| `pass` | `verify-pass-007d1e42` | `3b04dc58f5e21831cf55991f1de3100cd3b843e0` | `ac4bb17609602e127fa568b2e886efeff34e4d01` | `7e8bd4232c587b4929d3921502a5b5252f499461110540b4fa79001303d2fa9f` |
| `skip-evasion` | `verify-skip-evasion-9af28da3` | `3b04dc58f5e21831cf55991f1de3100cd3b843e0` | `4545ff35500dc4dc9932f86413f7fc127e256921` | `dd45948d6f9bec0817adc324e33fbea66e9cf018f4404c88daf6690383118294` |
| `omit-tox` | `verify-omit-tox-da5952bf` | `3b04dc58f5e21831cf55991f1de3100cd3b843e0` | `cfe5332d975f40bf6f2bc4566d45654459a172a0` | `5336a47a62d574efc8558f87752b03bb4dc118134040d02ea2fd4ab53e350436` |
| `undeclared-dep` | `verify-undeclared-dep-48dbe2e6` | `3b04dc58f5e21831cf55991f1de3100cd3b843e0` | `aada11d6ccafc4558444151287d682eb1488aab3` | `21f6a94097888e82564b565c2435c71ed6e2353486b9df62d766906b8ae445ff` |
| `changelog-creep` | `verify-changelog-creep-81fe2c65` | `3b04dc58f5e21831cf55991f1de3100cd3b843e0` | `1a6b9e71b12a05613ad032702cf348c9a750c348` | `3ce2791b7f827981aa8f3b295a67d72879a7da7f04b56744c0df7a86efc7a08a` |
| `fail` | `verify-fail-bc3ffada` | `3b04dc58f5e21831cf55991f1de3100cd3b843e0` | `37ca071edc2aebc64de7a6348d828848d4ecb1af` | `b285f3bfb5eb50d1e393bd7cfa938f9f55c00488533e4a68f160deb6de042a23` |
| `needs-human` | `verify-needs-human-0660270d` | `3b04dc58f5e21831cf55991f1de3100cd3b843e0` | `36bef17aeb207063f0df9d3af1f8b14fb137db67` | `b40ca7b69734e5b714d32c5e5b4f74184882c4f3bfd5e6e00dba81c366a2f497` |
| `pass-enforce` | `verify-pass-enforce-a00af0d0` | `813055970939991f61d82e1c6bc61eff0ef6cf2c` | `0f9d9dc2759da870bdd2c83635848daecc5b1cd0` | `7e8bd4232c587b4929d3921502a5b5252f499461110540b4fa79001303d2fa9f` |
| `skip-evasion-enforce` | `verify-skip-evasion-enforce-f7acefe5` | `813055970939991f61d82e1c6bc61eff0ef6cf2c` | `baec5e4da25a2b127a6226a8e7631cf22f064a35` | `dd45948d6f9bec0817adc324e33fbea66e9cf018f4404c88daf6690383118294` |

`3b04dc5…` is `release-gate-demo-base`; `8130559…` is `release-gate-demo-base-enforce`, whose only change is `mode: enforce`. The same planted patch therefore has the same patch SHA-256 against both bases (`pass` / `pass-enforce`, `skip-evasion` / `skip-evasion-enforce`). The candidate trees differ because they include the base's assurance policy.

All nine results used gate config SHA-256:

```text
b1ca5925ec0a446001455a9d57f745ca6c921ba2d91b429a0d4706bb964d96b5
```

Assurance policy SHA-256:

| Base | Mode | Policy SHA-256 |
|---|---|---|
| `release-gate-demo-base` | advisory | `55b86fefe71d6747c4eccec1d119edbb7f58caafa271d0be676f28a7630ae428` |
| `release-gate-demo-base-enforce` | enforce | `886cf71acc6531937e769549eabd6005a8210c673884bcc1253efc860727e700` |

The baseline recorded upstream commit `7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4`. Gate runs lasted about 7 seconds each (`needs-human` stopped in 1 ms because its checks were skipped).

## Warnings

Git emitted line-ending notices during setup:

```text
warning: in the working copy of '.gitignore', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of '.release-gate-assurance.yaml', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of '.release-gate.yaml', LF will be replaced by CRLF the next time Git touches it
```

They come from the workbench's `core.autocrlf=true`, which setup sets on purpose. Git stores these files with LF, so the reviewed source digests and policy comparisons are unaffected. The notices did not change any check, verdict, or disposition.

## Summary

This macOS run completed the full layer-handling campaign on the PR branch:

- Setup created and validated both trusted bases; every baseline run passed the 82-test suite.
- **Task 1:** the four mapped failure modes were verified by named tests and checks on every correct change, and each result traces to a reviewed test or check.
- **Task 2:** every run labelled all 12 layers. Substituted, unavailable, and not-applicable layers were never counted, even when the substitute passed.
- **Task 3:** skip evasion passed the gate but was flagged `ASSURANCE_INSUFFICIENT`, with `import_declaration_mismatch` reported as unverified. In enforce mode the same candidate became `NEEDS_HUMAN`, so a false release became an escalation. Every `FAIL` and `NEEDS_HUMAN` scenario counted zero evidence, even where individual checks passed.
- The `undeclared-dep` candidate, which crashed Release Gate before this branch's engine fix, now finalizes as `NEEDS_HUMAN`.
- Final reset restored the workbench, and the driver printed both required completion lines.
