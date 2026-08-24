# Rate-Limiter Repair Verification

**Date:** 2026-08-24
**Host:** Windows
**Command:** `.\run.ps1 verify-repair`
**Session ID:** `rep-20260824203527-f0cfe322`

## Purpose

Prove that Release Gate's bounded repair workflow can take a known-FAIL
candidate through a scripted, human-approved repair loop and reach an
`applied` state without ever letting an automated process bypass approval.
The rate-limiter demo seeds this with a deliberate off-by-one boundary defect
(`C0`), a still-broken first repair attempt (`C1`), and a correct second
repair attempt (`C2`). `verify-repair` drives the full CLI sequence
(`repair-start` -> `repair-approve` -> `repair-request`/`repair-evaluate` x2
-> `repair-apply`) end to end and checks the state, evidence, and final
source after every step.

## Result

```text
verify-repair: C0 FAIL -> C1 FAIL -> C2 PASS -> applied
```

The run exited successfully (exit code 0) after loading the local proxy
environment from the shared demo-level `env.ps1`. The actual interpreter
reported CPython 3.12.3, resolved via `uv python find 3.12` rather than
inferred from the `Python39` install directory name.

## Whole process and stage-by-stage logs

### Stage 0 — Baseline setup and quality gauntlet

`run.ps1` loads `..\env.ps1`, resolves the real Python 3.12 executable, then
`demo.py verify-repair` recreates the workbench, installs the pinned demo
venv, and runs the full portable gauntlet against the clean baseline before
any repair session exists.

```text
INITIALIZED: ...\workbench\rate-limiter\.release-gate.yaml
Using CPython 3.12.3 interpreter at: C:\Program Files\Python\Python39\python.exe
Creating virtual environment with seed packages at: workbench\task-venv
=== orchestration controls ===
orchestration controls: 5/5 passed
=== checker controls ===
checker controls: clean, violation, and broken input passed
=== tests + coverage ===
17 passed in 3.56s
Required test coverage of 100% reached. Total coverage: 100.00%
=== types ===
Success: no issues found in 8 source files
=== lint ===
All checks passed!
=== format ===
12 files already formatted
=== supply chain ===
No known vulnerabilities found
=== must-not scans ===
must-not scans clean
=== mutation control ===
C1 killer: KILLED
C2 equivalent: SURVIVED
negative control: ok
=== mutation ===
8/8 mutants killed
=== real execution ===
burst of 5 requests from 'alice' (limit 3/sec):
[True, True, True, False, False]
'bob' is unaffected: True
after the window passes, 'alice' again: True
=== source state ===
tree:     0968d35799731615bdcb037190c2dd488cfcb57a8b5c2ce85bd8b68de744744a
=== gauntlet: all layers green ===
VALID: ...\workbench\rate-limiter\.release-gate.yaml
BASELINE GREEN at 668d8078dd4f59bf51d43e482af171cf215c4e2f
trusted base: release-gate-rate-limiter-base
```

### Stage 1 — Prepare the C0 repair candidate

`demo.py` applies the scripted C0 patch (README note plus the off-by-one
boundary defect in `_prune`), scoped to the two approved paths.

```text
M README.md
 M src/ratelimiter/__init__.py
repair candidate ready: C0 (stale graphify)
```

### Stage 2 — `repair-start`: C0 evaluated, approval requested

Release Gate runs the ordinary gate against C0, confirms it is an eligible
`FAIL` (not `PASS`, `NEEDS_HUMAN`, or a scope violation), and opens a repair
session awaiting explicit approval.

```text
REPAIR_SESSION: ...\control-evidence\_repairs\rep-20260824203527-f0cfe322
REPAIR_STATE: awaiting_approval
NEXT_ACTION: approve_or_cancel
REPAIR_REQUEST: ...\rep-20260824203527-f0cfe322\approval-request.json
REPAIR_SUMMARY: ...\rep-20260824203527-f0cfe322\repair-summary.md
REPAIR_STAGE: C0 FAIL -> approval requested
```

### Stage 3 — `repair-approve`: approval granted, attempt cap set to 2

The demo writes a simulated start approval bound to the session ID and
approves exactly `README.md` and `src/ratelimiter/__init__.py`, with a
two-attempt budget.

```text
REPAIR_SESSION: ...\control-evidence\_repairs\rep-20260824203527-f0cfe322
REPAIR_STATE: repairing
NEXT_ACTION: edit_workspace
REPAIR_STAGE: approval granted
```

### Stage 4 — `repair-request` + C1 patch + `repair-evaluate`: still FAIL

The gate hands back an isolated worktree outside the source repository. The
demo applies `C1.patch` (an over-correction that still fails the exact
boundary), then asks Release Gate to re-evaluate that candidate.

```text
REPAIR_SESSION: ...\control-evidence\_repairs\rep-20260824203527-f0cfe322
REPAIR_STATE: repairing
NEXT_ACTION: edit_workspace
WORKSPACE: C:\Users\...\Temp\release-gate-repair-ws-_oj5de8y\worktree
APPROVED_PATHS: README.md, src/ratelimiter/__init__.py
FAILED_CHECKS: quality-gauntlet
REPAIR_SESSION: ...\control-evidence\_repairs\rep-20260824203527-f0cfe322
REPAIR_STATE: repairing
NEXT_ACTION: edit_workspace
REPAIR_SUMMARY: ...\rep-20260824203527-f0cfe322\repair-summary.md
REPAIR_STAGE: C1 FAIL
```

The demo also re-hashes the source worktree here and asserts it is
byte-for-byte unchanged from C0, proving the repair edits stayed confined to
the isolated workspace.

### Stage 5 — `repair-request` + C2 patch + `repair-evaluate`: PASS

The demo requests a second attempt, applies `C2.patch` (the correct boundary
fix, keeping the approved README change), and Release Gate evaluates a
passing candidate. The session moves to a final-approval gate rather than
applying automatically.

```text
REPAIR_SESSION: ...\control-evidence\_repairs\rep-20260824203527-f0cfe322
REPAIR_STATE: repairing
NEXT_ACTION: edit_workspace
WORKSPACE: C:\Users\...\Temp\release-gate-repair-ws-_oj5de8y\worktree
APPROVED_PATHS: README.md, src/ratelimiter/__init__.py
FAILED_CHECKS: quality-gauntlet
REPAIR_SESSION: ...\control-evidence\_repairs\rep-20260824203527-f0cfe322
REPAIR_STATE: awaiting_final_approval
NEXT_ACTION: final_approval_and_apply
REPAIR_SUMMARY: ...\rep-20260824203527-f0cfe322\repair-summary.md
REPAIR_STAGE: C2 PASS -> final approval requested
```

Source isolation is re-checked again here: the source worktree still matches
the original C0 hash while C2 is only staged in the disposable workspace.

### Stage 6 — `repair-apply`: final approval, applied to source

The demo binds a final approval to the session ID, the passing candidate
tree, and the passing patch digest, then Release Gate transactionally applies
that patch to the real source worktree.

```text
REPAIR_SESSION: ...\control-evidence\_repairs\rep-20260824203527-f0cfe322
REPAIR_STATE: applied
NEXT_ACTION: none
REPAIR_SUMMARY: ...\rep-20260824203527-f0cfe322\repair-summary.md
REPAIR_STAGE: final approval granted -> applied
```

### Stage 7 — Independent oracle verification

After apply, the demo asserts the final source contains the repaired
boundary and the retained README note, then runs the hidden oracle (outside
the candidate repository) against the applied source.

```text
Using CPython 3.12.3 interpreter at: C:\Program Files\Python\Python39\python.exe
Creating virtual environment with seed packages at: workbench\oracle-venv
11 passed in 0.05s
```

### Final line

```text
verify-repair: C0 FAIL -> C1 FAIL -> C2 PASS -> applied
```

## Repair stages (state-machine summary)

```text
C0 FAIL -> approval -> C1 FAIL -> C2 PASS -> final approval -> applied
```

The corresponding state transitions were:

```text
REPAIR_STATE: awaiting_approval
NEXT_ACTION: approve_or_cancel
REPAIR_STATE: repairing
NEXT_ACTION: edit_workspace
REPAIR_STATE: repairing
NEXT_ACTION: edit_workspace
REPAIR_STATE: awaiting_final_approval
NEXT_ACTION: final_approval_and_apply
REPAIR_STATE: applied
NEXT_ACTION: none
```

## Summary

This run is the first fully successful, end-to-end repair verification on
Windows for the rate-limiter demo:

- Baseline setup, the full quality gauntlet, and all 8 scripted mutants
  passed before any repair session started.
- C0 introduced the exact-boundary defect and was correctly classified as an
  eligible `FAIL`, requiring explicit approval before any edit occurred.
- C1 (still broken) and C2 (correct fix) were evaluated only inside an
  isolated worktree outside the source repository; the source worktree was
  proven byte-for-byte unchanged from C0 at every checkpoint until apply.
- The passing C2 candidate was applied to the source only after a second,
  final approval bound to the session ID, candidate tree, and patch digest.
- The independent oracle (11 tests) passed against the applied source,
  confirming the repaired boundary is behaviorally correct, not just
  gate-shaped.
- No automated step bypassed approval; both approvals were simulated
  explicitly by the demo driver, matching the documented bounded repair
  contract.

Known non-blocking notes from this run: the `run.ps1` launcher resolves the
real Python 3.12 interpreter and reports it as such (not the `Python39`
install directory name), and the orchestration/checker self-tests
(`missing layer 'second'`, `scan error: unreadable or missing root`, etc.)
are the gauntlet's own negative-control fixtures, not failures.

