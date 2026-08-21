# Evidence Report — Sliding-Window Rate Limiter and Release Gate Demo

This report records the final local verification on 2026-08-21. It is evidence
for this exact source state, not a general security certification.

- Source-state tree hash: `66b32f3768c083a5`. Reproduce it with
  `./tools/source_state.sh`; the hash covers the library, visible tests,
  portable gauntlet, policy, controls, driver, README, and hidden oracle.
- Outer repository commit reported during the run: `e950f96`. The tree hash is
  authoritative for this moved, staged demo; the outer commit only identifies
  the surrounding checkout before these changes are committed.
- Local toolchain: Python 3.12.13 on macOS; development packages are pinned in
  `requirements-dev.txt`.
- Portable entry point: `python tools/gauntlet.py`. The Bash script is a POSIX
  convenience wrapper only.
- CI configuration: the root `release-gate-ci.yml` now includes a Python 3.12
  Windows/macOS job that runs `demo.py verify`. This report records the local
  macOS result; it does not claim that the new CI job has run remotely yet.

## Spec-to-test and oracle mapping

| Behavior | Visible evidence | Independent oracle | Status |
|---|---|---|---|
| Requests up to the limit are allowed | Scenario test | Reference traces | pass |
| Requests over the limit are denied | Scenario test | Reference traces | pass |
| Denials do not consume quota or memory | Scenario and storage test | Storage snapshot | pass |
| Old requests expire individually | Scenario test | Brute-force model | pass |
| Exact boundary remains limited | Deterministic boundary test | Boundary trace | pass |
| Keys are isolated | Scenario and property P2 | Interleaved traces | pass |
| Invalid and non-finite construction is rejected | Parameterized scenarios | Independent parameter matrix | pass |
| Backward clock movement fails closed | Scenario test | Explicit rollback denial | pass |
| Allowed count never exceeds the limit | Property P1 | Deterministic generated traces | pass |
| No real clock in tests | Must-not scan | Oracle-owned clock | pass |

The oracle lives outside the generated candidate repository. It ran 11 tests
against the baseline and was then proven non-vacuous against all eight scripted
mutants. Every mutant was killed.

## Portable gauntlet result

The final fresh baseline run of `tools/gauntlet.py` produced:

| Layer | Result |
|---|---|
| Tests | 17 passed, 0 failed |
| Coverage | 29/29 statements and 10/10 branches; 100% |
| Strict types | No issues in 7 source files |
| Ruff lint and format | Clean; 10 files formatted |
| Supply chain | No known vulnerabilities; local `ratelimiter` package skipped because it is not on PyPI |
| Must-not scans | No wall-clock use in tests and no credential-like patterns |
| Mutation | 8/8 mutants killed |
| Real execution | Burst `[True, True, True, False, False]`; independent key allowed; quota reopened after the window |

The mutation runner restores the target byte-for-byte, including CRLF line
endings. The driver removes coverage, cache, and editable-install artifacts
after a successful baseline check so they cannot contaminate the candidate.

## Release Gate controls

`demo.py verify` created an isolated Git repository, committed the reviewed
policy as `release-gate-rate-limiter-base`, and produced these finalized results:

| Control | Changed path | Gate | Oracle | Classification |
|---|---|---|---|---|
| pass | `README.md` | PASS | correct | `good_pass` |
| fail | `src/ratelimiter/__init__.py` | FAIL | wrong | `good_catch` |
| needs-human | `.release-gate.yaml` | NEEDS_HUMAN | correct | `escalated` |

The FAIL control changed `>` to `>=` at the expiry boundary. The blocking
`quality-gauntlet` recorded `COMMAND_FAILED`, and the independent oracle failed
two reference-model tests. The NEEDS_HUMAN control recorded
`PATH_OUTSIDE_ALLOWED`, `PATH_REVIEW_REQUIRED`, and `POLICY_FILE_CHANGED`; the
configured gauntlet was skipped, as required when the judging policy changes.

The final verifier line was:

```text
verify: PASS, FAIL, and NEEDS_HUMAN controls matched expectations
```

## Honest limits

- The specification, implementation, visible tests, policy, and oracle remain
  repository-owned artifacts. Keeping the oracle outside the candidate breaks
  candidate control, but not correlated authorship.
- The limiter is not thread-safe; locking remains outside this demo's scope.
- A NaN-returning clock fails closed but is not rejected.
- Dependency installation and auditing require package-index/network access.
- A PASS is a policy decision for one captured candidate. It is not a merge,
  deployment, security attestation, or proof that no defect exists.
