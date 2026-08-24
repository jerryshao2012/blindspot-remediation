# Rate-Limiter Demo Run Log

**Run date:** 2026-08-24  
**Host:** Windows  
**Demo:** `release-gate/demo/rate-limiter`  
**Command:** `uv run --python 3.12 --no-project python demo.py verify`

## Purpose

Prove that `demo.py verify` — the fastest, non-interactive path through this
demo — actually exercises every claim the demo makes about Release Gate in a
single run: an independent oracle that can kill all eight scripted mutants, a
committed policy that is reconstructed and reused as the trusted base, and all
three possible gate verdicts (`PASS`, `FAIL`, `NEEDS_HUMAN`) produced from the
same base by three different, deliberately scripted candidate changes. `verify`
must reach its final printed line for the demo to be considered proven; an
earlier green section is not sufficient, because `verify` fails on any setup,
oracle, gate-result, or reset failure.

## Outcome

```text
verify: PASS, FAIL, and NEEDS_HUMAN controls matched expectations
```

The complete automated verification passed. The command exited successfully
and the demo reset the generated workbench to the trusted base after completing
all controls.

## Runtime

The command selected the following actual interpreter:

```text
Using CPython 3.12.3 interpreter at:
C:\Program Files\Python\Python39\python.exe
```

The version was verified from the interpreter runtime as Python `3.12.3`.
The directory name `Python39` was not used to determine the version.

## Whole process and stage-by-stage logs

`verify` runs as a single command, but it internally performs six distinct
stages in order: baseline setup, the quality gauntlet against that baseline,
the PASS control, the FAIL control, the NEEDS_HUMAN control, and a final reset.
Each control stage resets the candidate to the trusted base first, so the
three controls are independent of each other.

### Stage 0 — Baseline setup

```text
INITIALIZED: ...\workbench\rate-limiter\.release-gate.yaml
BASELINE GREEN at 8c84597f1e26acb1233cf6abb6c2fda120331c96
trusted base: release-gate-rate-limiter-base
```

The generated workbench was initialized, the reviewed policy was committed,
and the trusted base was created successfully.

### Stage 1 — Quality gauntlet against the clean baseline

| Layer | Result |
|---|---|
| Orchestration controls | 5/5 passed |
| Checker controls | Clean, violation, and broken-input cases passed |
| Tests and coverage | 17 passed; 100% statement and branch coverage |
| Strict types | No issues in 8 source files |
| Lint | All checks passed |
| Format | 12 files already formatted |
| Supply chain | No known vulnerabilities found |
| Must-not scans | Clean |
| Mutation control | Killer killed; equivalent survived; negative control passed |
| Production mutation | 8/8 mutants killed |
| Real execution | Expected burst and window-reset behavior |
| Source state | Manifest and candidate tree recorded |

Key functional output:

```text
burst of 5 requests from 'alice' (limit 3/sec):
[True, True, True, False, False]
'bob' is unaffected: True
after the window passes, 'alice' again: True
```

The gauntlet also reported:

```text
17 passed
Required test coverage of 100% reached. Total coverage: 100.00%
8/8 mutants killed
=== gauntlet: all layers green ===
```

### Stage 2 — PASS control (`README.md` only)

Candidate resets to the trusted base, applies a patch that changes only
`README.md`, then runs Release Gate against `release-gate-rate-limiter-base`.

```text
control ready: pass
VERDICT: PASS
RESULT: ...\workbench\control-evidence\verify-pass-2c44c67e\result.json
```

`demo.py inspect` on that result reported:

```text
verdict: PASS
reason codes: none
changed paths: README.md
check quality-gauntlet: PASS
```

`demo.py grade` then ran the independent oracle against the candidate and
classified it:

```text
truth: correct
classification: good_pass
```

### Stage 3 — FAIL control (behavioral regression in `src/ratelimiter/__init__.py`)

Candidate resets again, then applies a patch that introduces an exact-boundary
regression in the rate limiter itself.

```text
control ready: fail
VERDICT: FAIL
RESULT: ...\workbench\control-evidence\verify-fail-7927f7c8\result.json
```

```text
verdict: FAIL
reason codes: COMMAND_FAILED
changed paths: src/ratelimiter/__init__.py
check quality-gauntlet: FAIL (COMMAND_FAILED)
```

The independent oracle disagreed with the candidate's own test suite and
caught the injected regression, so grading classified this as the gate
correctly blocking a bad change:

```text
truth: wrong
classification: good_catch
```

### Stage 4 — NEEDS_HUMAN control (candidate edits its own policy)

Candidate resets a third time, then applies a patch that changes
`.release-gate.yaml` — the policy file that judges the candidate. Release Gate
detects this before running any configured check.

```text
control ready: needs-human
VERDICT: NEEDS_HUMAN
RESULT: ...\workbench\control-evidence\verify-needs-human-16b3cc69\result.json
```

```text
verdict: NEEDS_HUMAN
reason codes: PATH_OUTSIDE_ALLOWED, PATH_REVIEW_REQUIRED, POLICY_FILE_CHANGED
changed paths: .release-gate.yaml
check quality-gauntlet: SKIPPED (POLICY_FILE_CHANGED)
```

The configured `quality-gauntlet` check never ran because a candidate cannot
change the policy that judges it. The independent oracle still passed against
the (unmodified) candidate code, and grading classified the verdict as
correctly escalated to a human:

```text
truth: correct
classification: escalated
```

### Stage 5 — Final reset

`verify` resets the generated candidate back to the trusted base one last time
before printing its final line, so the workbench is left clean for the next
run.

```text
reset: release-gate-rate-limiter-base
verify: PASS, FAIL, and NEEDS_HUMAN controls matched expectations
```

### Summary table of the three controls

| Control | Changed path | Verdict | Check | Oracle | Classification |
|---|---|---|---|---|---|
| `pass` | `README.md` | `PASS` | `quality-gauntlet: PASS` | Correct | `good_pass` |
| `fail` | `src/ratelimiter/__init__.py` | `FAIL` | `quality-gauntlet: FAIL (COMMAND_FAILED)` | Wrong | `good_catch` |
| `needs-human` | `.release-gate.yaml` | `NEEDS_HUMAN` | `quality-gauntlet: SKIPPED (POLICY_FILE_CHANGED)` | Correct | `escalated` |

## Source state

```text
base commit: 8c84597f1e26acb1233cf6abb6c2fda120331c96
candidate tree: afd2388aee8c5f0df3c662c7121e00c3c1ade650
patch sha256: d1a02141b00a9343243cde1c3d878304801895b7c11a1f4f4864e79f2fd0b7a5
config sha256: 5d5f20e744ad6c5104fa6c6fb679f578c309e8a98ece6202822b764cddec1b9a
```

The PASS candidate changed only `README.md`. The final reset restored the
trusted base before the command completed.

## Warnings

The run printed this warning several times:

```text
The `UV_NATIVE_TLS` environment variable is deprecated in favor of
`UV_SYSTEM_CERTS`.
```

The current demo policy uses `UV_SYSTEM_CERTS=true` for Windows gate commands.
The warning indicates that the outer PowerShell session still has the old
`UV_NATIVE_TLS` variable set. It is non-fatal. To remove the warning from
future runs:

```powershell
Remove-Item Env:UV_NATIVE_TLS -ErrorAction SilentlyContinue
$env:UV_SYSTEM_CERTS = "true"
```

The gate also reported:

```text
WARNING: OBSERVABILITY_PATH_UNSAFE
```

This is a non-gating observability publication warning. The gate still produced
complete result and manifest evidence, and the verdicts were unchanged. The
quality checks and control campaign passed despite this optional dashboard
publication warning.

## Design assessment

This run meets the rate-limiter demo design contract:

- The actual Python runtime is Python 3.12.3.
- Baseline setup and isolated dependency preparation completed.
- The quality gauntlet completed all expected layers.
- The PASS, FAIL, and NEEDS_HUMAN controls matched their expected verdicts.
- The independent oracle classified the controls correctly.
- The trusted base was restored at the end of the run.
- The final required verification line was printed.

The only residual issue is the non-gating `OBSERVABILITY_PATH_UNSAFE` warning,
which does not invalidate the release-gate control results.

## Summary

This was a first fully successful, non-interactive `verify` run for the
rate-limiter demo on Windows:

- Baseline setup created the trusted base and passed the full quality
  gauntlet, including all 8 scripted mutants, before any control ran.
- Each of the three scripted controls (`pass`, `fail`, `needs-human`) reset to
  the same trusted base independently, so their results are directly
  comparable.
- The gate produced the expected verdict for every control: `PASS` for a
  documentation-only change, `FAIL` for an injected behavioral regression, and
  `NEEDS_HUMAN` for a candidate that edited its own policy file.
- The independent oracle, run outside the candidate repository, agreed with
  every verdict's real-world correctness and was classified as
  `good_pass` / `good_catch` / `escalated` respectively — not `FALSE_RELEASE`
  or `FALSE_BLOCK`.
- The workbench was returned to the trusted base by the final reset, and the
  command printed its required final line, so the run counts as complete
  under this demo's own definition (an earlier green section is not enough).
- The two warnings observed (`UV_NATIVE_TLS` deprecation,
  `OBSERVABILITY_PATH_UNSAFE`) are both non-gating and did not affect any
  verdict.

