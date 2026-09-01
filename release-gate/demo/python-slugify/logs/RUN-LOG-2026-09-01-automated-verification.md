# Python-Slugify Demo Run Log

**Run date:** 2026-09-01  
**Host:** Windows  
**Demo:** `release-gate/demo/python-slugify`  
**Command:** `uv run --python 3.12 --no-project python demo.py verify`

## Purpose

Prove that `demo.py verify` completes the Python-Slugify Release Gate demo's
non-interactive verification path. The run establishes a green trusted base,
then evaluates three independent scripted candidate changes from that same
base. It verifies that Release Gate returns `PASS` for an approved functional
change, `FAIL` when the candidate alters protected test evidence, and
`NEEDS_HUMAN` when the candidate alters the policy that judges it. An
independent oracle grades each verdict after the gate finishes.

A run counts as complete only when `verify` reaches its final line. Earlier
successful baseline or control output is insufficient because the driver fails
on setup, gate, oracle, expectation, or reset failures.

## Outcome

```text
verify: PASS, FAIL, and NEEDS_HUMAN controls matched expectations
```

Complete automated verification passed with exit code 0. The final reset
restored the generated workbench to the trusted base.

## Runtime

The command used this interpreter:

```text
Using CPython 3.12.3 interpreter at:
C:\Program Files\Python\Python39\python.exe
```

Runtime reported Python `3.12.3`; the `Python39` directory name does not
identify the interpreter version.

## Whole Process And Stage-By-Stage Logs

`verify` performed baseline setup, then PASS, FAIL, and NEEDS_HUMAN controls.
Each control reset to `release-gate-demo-base` before applying its patch, so
results are independent and directly comparable.

### Stage 0 - Baseline Setup

The driver created the workbench policy, installed the task environment, and
ran the baseline test suite successfully.

```text
INITIALIZED: ...\workbench\python-slugify\.release-gate.yaml
82 passed in 0.31s
VALID: ...\workbench\python-slugify\.release-gate.yaml
BASELINE GREEN at 7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4
trusted base: release-gate-demo-base
```

The run then reset the candidate and re-ran the baseline tests before each
control. Those repeated baseline checks passed `82` tests in `0.16s`, `0.12s`,
`0.18s`, and `0.13s` respectively.

### Stage 1 - PASS Control

The PASS patch changed four approved paths: `README.md`, `setup.py`,
`slugify/slugify.py`, and `tox.ini`.

```text
control ready: pass
VERDICT: PASS
RESULT: ...\workbench\evidence\verify-pass-eb950ca5\result.json
```

```text
verdict: PASS
reason codes: none
changed paths: README.md, setup.py, slugify/slugify.py, tox.ini
check tests-and-coverage: PASS
check task-consistency: PASS
check types: PASS
```

The independent oracle passed all `16` tests and classified the release as
correct:

```text
truth: correct
classification: good_pass
```

### Stage 2 - FAIL Control

The FAIL patch included the approved PASS paths plus `test.py`. Policy marks
`test.py` forbidden, so Release Gate rejected the candidate even though its
configured checks passed.

```text
control ready: fail
VERDICT: FAIL
RESULT: ...\workbench\evidence\verify-fail-919fb415\result.json
```

```text
verdict: FAIL
reason codes: PATH_FORBIDDEN, PATH_OUTSIDE_ALLOWED
changed paths: README.md, setup.py, slugify/slugify.py, test.py, tox.ini
outside allowed: test.py
forbidden: test.py
check tests-and-coverage: PASS
check task-consistency: PASS
check types: PASS
```

The external oracle deliberately detected the modified visible test evidence:

```text
1 failed, 15 passed in 2.61s
truth: wrong
classification: good_catch
```

Expected oracle failure was
`test_candidate_did_not_modify_its_visible_test_evidence`; it confirmed the
candidate changed `test.py`, validating this control's `FAIL` verdict.

### Stage 3 - NEEDS_HUMAN Control

The NEEDS_HUMAN patch included the PASS paths plus `.release-gate.yaml`, the
policy file used to evaluate the candidate. Release Gate escalated before
executing configured checks.

```text
control ready: needs-human
VERDICT: NEEDS_HUMAN
RESULT: ...\workbench\evidence\verify-needs-human-1c23605b\result.json
```

```text
verdict: NEEDS_HUMAN
reason codes: PATH_OUTSIDE_ALLOWED, PATH_REVIEW_REQUIRED, POLICY_FILE_CHANGED
changed paths: .release-gate.yaml, README.md, setup.py, slugify/slugify.py, tox.ini
outside allowed: .release-gate.yaml
review required: .release-gate.yaml
check tests-and-coverage: SKIPPED (POLICY_FILE_CHANGED)
check task-consistency: SKIPPED (POLICY_FILE_CHANGED)
check types: SKIPPED (POLICY_FILE_CHANGED)
```

The oracle passed all `16` tests because candidate behavior remained correct;
it classified the escalation as expected:

```text
truth: correct
classification: escalated
```

### Stage 4 - Final Reset

After the final control, `verify` reset the workbench to the trusted base and
re-ran the baseline suite before reporting success.

```text
reset: release-gate-demo-base
verify: PASS, FAIL, and NEEDS_HUMAN controls matched expectations
```

## Control Summary

| Control | Changed paths | Verdict | Checks | Oracle | Classification |
|---|---|---|---|---|---|
| `pass` | `README.md`, `setup.py`, `slugify/slugify.py`, `tox.ini` | `PASS` | All three passed | Correct | `good_pass` |
| `fail` | PASS paths plus `test.py` | `FAIL` | All three passed | Wrong | `good_catch` |
| `needs-human` | PASS paths plus `.release-gate.yaml` | `NEEDS_HUMAN` | All skipped | Correct | `escalated` |

## Evidence Identifiers

| Control | Run | Base commit | Candidate tree | Patch SHA-256 |
|---|---|---|---|---|
| `pass` | `verify-pass-eb950ca5` | `6ed84c287736ce2a256b5c9798e4bcc2df628d3c` | `24fa968d82e846d71573f686a2c74e5c342869a0` | `7e8bd4232c587b4929d3921502a5b5252f499461110540b4fa79001303d2fa9f` |
| `fail` | `verify-fail-919fb415` | `6ed84c287736ce2a256b5c9798e4bcc2df628d3c` | `9b4ddb34dee3eae6c31308eec17f2c1182b3b8ac` | `b285f3bfb5eb50d1e393bd7cfa938f9f55c00488533e4a68f160deb6de042a23` |
| `needs-human` | `verify-needs-human-1c23605b` | `6ed84c287736ce2a256b5c9798e4bcc2df628d3c` | `a5261a1545ede98141ed3116b8fdf64e77868eb6` | `0b5f81d7a5a90dda3e6f5c797b4a0ca8202166984e3143ed95118c6e8d707b57` |

All three results used config SHA-256:

```text
853db4b43f2001c4ed3251b6ac96478b09eb82f2d75bc7c5a22f639041c9f6c1
```

The baseline recorded upstream commit
`7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4`. The per-control evidence uses
`6ed84c287736ce2a256b5c9798e4bcc2df628d3c`, trusted candidate base including
committed demo policy.

## Warnings

Git emitted this non-blocking mode warning when applying candidate patches:

```text
warning: setup.py has type 100644, expected 100755
```

Git also emitted an LF-to-CRLF conversion notice for `.gitignore` during
initialization. Neither warning changed policy, configured check results, or
control verdicts.

Each Release Gate invocation reported:

```text
WARNING: OBSERVABILITY_PATH_UNSAFE
```

This non-gating observability publication warning did not prevent result or
manifest creation. All expected verdicts and oracle classifications completed.

## Summary

This Windows run completed Python-Slugify's full automated Release Gate control
campaign:

- Baseline setup created and validated `release-gate-demo-base`; all baseline
  runs passed the `82`-test suite.
- PASS allowed approved functional change after all configured checks and
  independent oracle verification passed.
- FAIL blocked a candidate that modified protected test evidence, even though
  candidate checks were green; independent oracle confirmed change.
- NEEDS_HUMAN escalated a candidate policy edit before candidate checks ran,
  while independent oracle confirmed behavior remained correct.
- Each control began from same trusted base, emitted result and manifest
  evidence, and completed with expected oracle classification.
- Final reset restored workbench and driver printed required completion line.

Observed Git and observability warnings were non-gating and did not affect
verification outcome.