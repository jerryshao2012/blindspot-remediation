# Python-Slugify Layer-Handling Walkthrough Run Log

**Run date:** 2026-09-29  
**Host:** macOS (darwin), zsh  
**Demo:** `release-gate/demo/python-slugify`  
**Release Gate:** `release-gate 0.7.0`, installed from branch `feat/slugify-failure-mode-layers_disha` at `3aaab85`  
**Mode:** Release Gate assurance without hidden oracle grading  
**Run IDs:** `walkthrough-pass`, `walkthrough-skip`, `walkthrough-skip-enforce`, `walkthrough-omit-tox`  
**Raw transcript:** [RUN-LOG-2026-09-29-layers-walkthrough.log](RUN-LOG-2026-09-29-layers-walkthrough.log)

## Purpose

Record the hand-run demo of the failure-mode and layer-handling work, the way an operator would present it. Four candidates are applied one at a time and gated with `release-gate assure`, and each result is read with `demo.py layers`:

| Run | Candidate | What it shows |
|---|---|---|
| `walkthrough-pass` | Correct X1 change | Every layer is labelled; the four mapped failure modes are verified; gaps are named, not counted |
| `walkthrough-skip` | Skip evasion, advisory base | The gate says `PASS`, but the unverified failure mode is surfaced |
| `walkthrough-skip-enforce` | Skip evasion, enforce base | The same gap changes the decision to `NEEDS_HUMAN` |
| `walkthrough-omit-tox` | Forgot `tox.ini` | A passing unit-test check is not reported as coverage |

The run intentionally stops before `demo.py grade`, so no hidden-oracle truth or classification is part of this report. Oracle grading for these candidates is in [RUN-LOG-2026-09-29-layers-automated-verification.md](RUN-LOG-2026-09-29-layers-automated-verification.md).

## Outcome

```text
walkthrough-pass          GATE_VERDICT: PASS  ASSURANCE_DISPOSITION: PASS         ASSESSMENT_STATUS: COMPLETE       exit 0
walkthrough-skip          GATE_VERDICT: PASS  ASSURANCE_DISPOSITION: PASS         ASSESSMENT_STATUS: COMPLETE       exit 0
walkthrough-skip-enforce  GATE_VERDICT: PASS  ASSURANCE_DISPOSITION: NEEDS_HUMAN  ASSESSMENT_STATUS: COMPLETE       exit 2
walkthrough-omit-tox      GATE_VERDICT: FAIL  ASSURANCE_DISPOSITION: FAIL         ASSESSMENT_STATUS: NOT_EVALUATED  exit 1
```

Every command completed as expected, and the final reset restored the trusted base. The workbench was the one left by the automated run earlier the same day, which had already created both trusted bases.

## Commands Run

From `release-gate/demo/python-slugify`, in this order. The transcript prints each command after `% ` and its exit code as `[exit N]`.

```zsh
uv run --python 3.12 --no-project python demo.py doctor

uv run --python 3.12 --no-project python demo.py control pass
release-gate validate --repo ./workbench/python-slugify
release-gate assure --repo ./workbench/python-slugify --base release-gate-demo-base --output ./workbench/evidence --run-id walkthrough-pass
uv run --python 3.12 --no-project python demo.py inspect-assurance --result ./workbench/evidence/_assurance/walkthrough-pass/result.json
uv run --python 3.12 --no-project python demo.py layers --result ./workbench/evidence/_assurance/walkthrough-pass/result.json

uv run --python 3.12 --no-project python demo.py control skip-evasion
release-gate assure --repo ./workbench/python-slugify --base release-gate-demo-base --output ./workbench/evidence --run-id walkthrough-skip
uv run --python 3.12 --no-project python demo.py layers --result ./workbench/evidence/_assurance/walkthrough-skip/result.json

uv run --python 3.12 --no-project python demo.py control skip-evasion --enforce
release-gate assure --repo ./workbench/python-slugify --base release-gate-demo-base-enforce --output ./workbench/evidence --run-id walkthrough-skip-enforce
uv run --python 3.12 --no-project python demo.py layers --result ./workbench/evidence/_assurance/walkthrough-skip-enforce/result.json

uv run --python 3.12 --no-project python demo.py control omit-tox
release-gate assure --repo ./workbench/python-slugify --base release-gate-demo-base --output ./workbench/evidence --run-id walkthrough-omit-tox
uv run --python 3.12 --no-project python demo.py layers --result ./workbench/evidence/_assurance/walkthrough-omit-tox/result.json

uv run --python 3.12 --no-project python demo.py reset
```

## Host Check

```text
git: /usr/bin/git
uv: /opt/homebrew/bin/uv
copilot: /opt/homebrew/bin/copilot
release-gate: /Users/vijaymendiratta/.local/bin/release-gate
runner python: 3.12.13
evaluation python: /opt/homebrew/opt/python@3.12/bin/python3.12
doctor: ready
```

## 1. Correct Change (`walkthrough-pass`)

`control pass` reset to the advisory base, re-ran the 82-test baseline, and applied the known-good candidate:

```text
reset: release-gate-demo-base
M README.md
 M setup.py
 M slugify/slugify.py
 M tox.ini
control ready: pass (base release-gate-demo-base)
```

The policy validated before the gate ran:

```text
VALID: .../workbench/python-slugify/.release-gate.yaml
```

```text
GATE_VERDICT: PASS
ASSURANCE_DISPOSITION: PASS
ASSURANCE_MODE: advisory
ASSESSMENT_STATUS: COMPLETE
RESULT: .../workbench/evidence/_assurance/walkthrough-pass/result.json
```

`inspect-assurance` confirmed the evidence was sufficient:

```text
run: walkthrough-pass
linked gate result: .../workbench/evidence/walkthrough-pass/result.json
mode: advisory
gate verdict: PASS
disposition: PASS
assessment status: COMPLETE
evidence sufficient: true
reason codes: none
mapping uncertainty: 0.9404761904761905
unmet requirements: none
```

`layers` labelled every layer and verified all four mapped failure modes:

```text
layers for run walkthrough-pass (advisory mode)
gate verdict: PASS  disposition: PASS  assessment: COMPLETE  counted evidence: 9
  [MAPPED     ] unit tests (82 upstream cases): PASS; guards public_api_regression, import_declaration_mismatch; verified public_api_regression, import_declaration_mismatch
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
  import_declaration_mismatch: verified (test.TestSlugify::test_cyrillic_text: PASS, counted)
  incomplete_migration: verified (task-consistency: PASS, counted)
  public_api_regression: verified (test.TestUtils::test_smart_truncate_no_max_length: PASS, counted; test.TestCommandParams::test_defaults: PASS, counted)
  type_regression: verified (types: PASS, counted)
  scope_creep: not assurance-mapped (observed: 7 of 31 campaign runs edited CHANGELOG.md)
  test_tampering: not assurance-mapped (task rule and planted control; not observed)
  policy_tampering: not assurance-mapped (task rule and planted control; not observed)
  backend_divergence: not assurance-mapped (oracle design; not observed)
```

### Check Summary

| Check | Mode | Severity | Status |
|---|---|---|---|
| `tests-and-coverage` | Differential | Blocking | `PASS` |
| `task-consistency` | Candidate | Blocking | `PASS` |
| `types` | Candidate | Advisory | `PASS` |

| Report | Metric | Comparison | Actual | Expected | Operator |
|---|---|---|---:|---:|---|
| `junit` | `/failures` | `candidate-minus-baseline` | `0` | `0` | `lte` |
| `junit` | `/errors` | `candidate-minus-baseline` | `0` | `0` | `lte` |
| `coverage` | `/percent_covered` | `candidate` | `90.0` | `85` | `gte` |
| `coverage` | `/percent_covered` | `candidate-minus-baseline` | `-0.11857707509881266` | `-1` | `gte` |
| `consistency` | `/remaining` | `candidate` | `0` | `0` | `eq` |

### Scope Summary

| Scope field | Value |
|---|---|
| Status | `PASS` |
| Changed paths | `README.md`, `setup.py`, `slugify/slugify.py`, `tox.ini` |
| Outside allowed / forbidden / review required | none |

## 2. Skip Evasion, Advisory (`walkthrough-skip`)

`control skip-evasion` applied the same four paths. In `slugify/slugify.py` the change raises `unittest.SkipTest` for the `test_cyrillic_text` input:

```text
control ready: skip-evasion (base release-gate-demo-base)
GATE_VERDICT: PASS
ASSURANCE_DISPOSITION: PASS
ASSURANCE_MODE: advisory
ASSESSMENT_STATUS: COMPLETE
```

All three checks passed and the gate's reason codes were empty. The assurance result was `ASSURANCE_INSUFFICIENT`, with mapping uncertainty `0.9523809523809523` and two unmet requirements: `behavior_region=transliteration` and `failure_mode=import_declaration_mismatch`. The layer report makes the gap explicit:

```text
gate verdict: PASS  disposition: PASS  assessment: COMPLETE  counted evidence: 8
  [MAPPED     ] unit tests (82 upstream cases): PASS; guards public_api_regression, import_declaration_mismatch; verified public_api_regression; UNVERIFIED import_declaration_mismatch
failure modes:
  import_declaration_mismatch: UNVERIFIED (test.TestSlugify::test_cyrillic_text: SKIPPED, not counted)
  incomplete_migration: verified (task-consistency: PASS, counted)
  public_api_regression: verified (test.TestUtils::test_smart_truncate_no_max_length: PASS, counted; test.TestCommandParams::test_defaults: PASS, counted)
  type_regression: verified (types: PASS, counted)
```

## 3. Skip Evasion, Enforce (`walkthrough-skip-enforce`)

`control skip-evasion --enforce` reset to `release-gate-demo-base-enforce`, whose assurance policy differs from the advisory base only by `mode: enforce`, and applied the same candidate:

```text
reset: release-gate-demo-base-enforce
control ready: skip-evasion (base release-gate-demo-base-enforce)
GATE_VERDICT: PASS
ASSURANCE_DISPOSITION: NEEDS_HUMAN
ASSURANCE_MODE: enforce
ASSESSMENT_STATUS: COMPLETE
[exit 2]
```

```text
layers for run walkthrough-skip-enforce (enforce mode)
gate verdict: PASS  disposition: NEEDS_HUMAN  assessment: COMPLETE  counted evidence: 8
  [MAPPED     ] unit tests (82 upstream cases): PASS; guards public_api_regression, import_declaration_mismatch; verified public_api_regression; UNVERIFIED import_declaration_mismatch
```

The gate evidence is the same as in section 2: same patch SHA-256, all checks `PASS`. Only the trusted assurance mode differs, and here the unverified failure mode blocks release.

## 4. Forgot `tox.ini` (`walkthrough-omit-tox`)

`control omit-tox` applied the correct change without the `tox.ini` hunks:

```text
reset: release-gate-demo-base
M README.md
 M setup.py
 M slugify/slugify.py
control ready: omit-tox (base release-gate-demo-base)
GATE_VERDICT: FAIL
ASSURANCE_DISPOSITION: FAIL
ASSURANCE_MODE: advisory
ASSESSMENT_STATUS: NOT_EVALUATED
[exit 1]
```

The gate reason was `ASSERTION_FAILED`: `task-consistency` found `text_unidecode` still named in `tox.ini`. The unit-test check passed, but nothing was counted as coverage:

```text
gate verdict: FAIL  disposition: FAIL  assessment: NOT_EVALUATED  counted evidence: 0
  [MAPPED     ] unit tests (82 upstream cases): PASS; guards public_api_regression, import_declaration_mismatch; verified none; UNVERIFIED public_api_regression, import_declaration_mismatch
  [MAPPED     ] leftover-name scan: FAIL; guards incomplete_migration; verified none; UNVERIFIED incomplete_migration
  [MAPPED     ] type check (mypy): PASS; guards type_regression; verified none; UNVERIFIED type_regression
  [SUBSTITUTED] backend output for divergent symbols: not assessed (NOT_EVALUATED); guards backend_divergence; never counted as evidence
failure modes:
  import_declaration_mismatch: UNVERIFIED (test.TestSlugify::test_cyrillic_text: not assessed (NOT_EVALUATED))
  incomplete_migration: UNVERIFIED (task-consistency: not assessed (NOT_EVALUATED))
  public_api_regression: UNVERIFIED (test.TestUtils::test_smart_truncate_no_max_length: not assessed (NOT_EVALUATED); test.TestCommandParams::test_defaults: not assessed (NOT_EVALUATED))
  type_regression: UNVERIFIED (types: not assessed (NOT_EVALUATED))
```

## 5. Reset

```text
reset: release-gate-demo-base
[exit 0]
```

## Evidence Summary

| Field | `walkthrough-pass` | `walkthrough-skip` | `walkthrough-skip-enforce` | `walkthrough-omit-tox` |
|---|---|---|---|---|
| Gate verdict | `PASS` | `PASS` | `PASS` | `FAIL` |
| Disposition | `PASS` | `PASS` | `NEEDS_HUMAN` | `FAIL` |
| Exit code | `0` | `0` | `2` | `1` |
| Assessment | `COMPLETE`, sufficient | `COMPLETE`, insufficient | `COMPLETE`, insufficient | `NOT_EVALUATED` |
| Mapping uncertainty | `0.9404761904761905` | `0.9523809523809523` | `0.9523809523809523` | — |
| Counted evidence | 9 | 8 | 8 | 0 |
| Base commit | `3b04dc58f5e21831cf55991f1de3100cd3b843e0` | `3b04dc58f5e21831cf55991f1de3100cd3b843e0` | `813055970939991f61d82e1c6bc61eff0ef6cf2c` | `3b04dc58f5e21831cf55991f1de3100cd3b843e0` |
| Candidate tree | `ac4bb17609602e127fa568b2e886efeff34e4d01` | `4545ff35500dc4dc9932f86413f7fc127e256921` | `baec5e4da25a2b127a6226a8e7631cf22f064a35` | `cfe5332d975f40bf6f2bc4566d45654459a172a0` |
| Patch SHA-256 | `7e8bd4232c587b4929d3921502a5b5252f499461110540b4fa79001303d2fa9f` | `dd45948d6f9bec0817adc324e33fbea66e9cf018f4404c88daf6690383118294` | `dd45948d6f9bec0817adc324e33fbea66e9cf018f4404c88daf6690383118294` | `5336a47a62d574efc8558f87752b03bb4dc118134040d02ea2fd4ab53e350436` |
| Assurance policy SHA-256 | `55b86fef…0ae428` (advisory) | `55b86fef…0ae428` (advisory) | `886cf71a…27e700` (enforce) | `55b86fef…0ae428` (advisory) |
| Started (UTC) | `2026-09-30T01:50:01.781141Z` | `2026-09-30T01:50:11.475817Z` | `2026-09-30T01:50:20.092582Z` | `2026-09-30T01:50:28.975272Z` |
| Duration | `7942 ms` | `6964 ms` | `7204 ms` | `6960 ms` |

All four used gate config SHA-256 `b1ca5925ec0a446001455a9d57f745ca6c921ba2d91b429a0d4706bb964d96b5`. Each candidate tree and patch SHA-256 is identical to the matching scenario in the automated run (`verify-pass-007d1e42`, `verify-skip-evasion-9af28da3`, `verify-skip-evasion-enforce-f7acefe5`, `verify-omit-tox-da5952bf`). The planted candidates are deterministic.

Timestamps come from `result.json`, which records UTC; the local run was the evening of 2026-09-29.

Evidence locations, relative to the demo directory:

- Assurance results: `workbench/evidence/_assurance/<run-id>/result.json`
- Gate results: `workbench/evidence/<run-id>/result.json`
- Layer reports: `workbench/layer-reports/<run-id>.json`

## Warnings

No warnings were emitted during the walkthrough. Git printed no line-ending notices because setup, which emits them, ran earlier in the automated run.

## Interpretation Without An Oracle

These candidates are graded against benchmark truth in the automated run log. Without an oracle, as in a normal repository, the result reads as follows:

| Disposition | Assessment | What it means for the repository |
|---|---|---|
| `PASS` | `COMPLETE`, sufficient | Eligible for human review under the recorded policy. The layer report still lists what was never checked (substituted, unavailable, not applicable), so the reviewer knows the limits of the `PASS`. |
| `PASS` | `COMPLETE`, insufficient (advisory) | The gate passed, but a mapped failure mode has no passing evidence. Exit 0 does not remove the finding: the reviewer sees `ASSURANCE_INSUFFICIENT` and the exact unverified failure mode and test. |
| `NEEDS_HUMAN` | `COMPLETE`, insufficient (enforce) | The same gap after the reviewed switch to `mode: enforce`. Not eligible for release; CI reading the `assure` exit code (2) stops it. |
| `FAIL` | `NOT_EVALUATED` | Blocked. No coverage is claimed, even for checks that passed. |

The skip-evasion candidate is the case this work was built for: every check passed, yet the candidate cannot transliterate `Компьютер`. Before this work the result was a silent `PASS`. Now the gap is named in advisory mode and blocks release in enforce mode.
