# Evidence Report — Sliding-Window Rate Limiter and Release Gate Demo

This report records the final local verification on 2026-08-21. It is evidence
for this exact source state, not a general security certification.

- Source-state tree hash:
  `f9b5b3e657e0d084db3bfcf5d5e1a541a33db88b0dd35992117c515ac8d7003b`.
  Reproduce it with `python tools/source_state.py`. The manifest hashes each
  path and file as an unambiguous, length-delimited byte sequence; it rejects
  missing, special, symlinked, unreadable, or changing inputs.
- No commit provenance is asserted. The source digest is the binding for this
  staged demo and avoids inventing provenance from the surrounding checkout.
- Local toolchain: Python 3.12.13 on macOS; development packages are pinned in
  `requirements-dev.txt`.
- Portable entry point: `python tools/gauntlet.py`. The Bash script is a POSIX
  convenience wrapper only.
- CI configuration includes Python 3.12 Windows and macOS demo jobs. This
  report records the local macOS result only; those jobs were not independently
  observed remotely for these bytes.

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

The final clean run of `tools/gauntlet.py` produced:

| Layer | Result |
|---|---|
| Orchestration controls | 5/5: omitted, unknown, duplicate, complete, and child-exit propagation |
| Checker controls | Clean input accepted; violation detected; missing input reported as an error |
| Tests and enforced coverage | 17 passed; 29/29 statements and 10/10 branches; `--cov-fail-under=100` satisfied |
| Strict types | No issues in 9 source files in the outer demo; 8 in the generated candidate |
| Ruff lint and format | Clean; 14 outer files and 12 candidate files formatted |
| Supply chain | No known vulnerabilities; local `ratelimiter` skipped because it is not on PyPI |
| Must-not scans | No wall-clock use in tests and no credential-like patterns |
| Mutation negative control | Same-size/same-mtime killer killed; equivalent edit survived |
| Production mutation | 8/8 mutants killed |
| Real execution | Burst `[True, True, True, False, False]`; independent key allowed; quota reopened after the window |
| Source-state audit | All expected layers completed before the sole all-green message |

The gauntlet uses a fixed expected-layer ledger. It rejects omitted, unknown,
and duplicate completion records, propagates child exit codes, and prints the
all-green message only after the final audit. Scanner input failures and
internal checker errors are distinct from violations.

The mutation runner disables bytecode writes, removes caches before every run,
requires genuine JUnit test failures for a kill, treats collection/tool errors
as errors, and restores the target byte-for-byte with its timestamps. Its
killer-versus-equivalent control also uses same-size, same-mtime edits to prove
cache isolation.

## Release Gate controls

`demo.py verify` created an isolated Git repository, committed the reviewed
policy as `release-gate-rate-limiter-base`, and produced these finalized results:

| Control | Changed path | Gate | Check status | Oracle | Classification |
|---|---|---|---|---|---|
| pass | `README.md` | PASS | `quality-gauntlet`: PASS | correct | `good_pass` |
| fail | `src/ratelimiter/__init__.py` | FAIL | `quality-gauntlet`: FAIL (`COMMAND_FAILED`) | wrong | `good_catch` |
| needs-human | `.release-gate.yaml` | NEEDS_HUMAN | `quality-gauntlet`: SKIPPED (`POLICY_FILE_CHANGED`) | correct | `escalated` |

Each inspector displayed `base_commit`, `candidate_tree`, `patch_sha256`, and
`config_sha256` from both `result.json` and `manifest.json`. The FAIL control
changed `>` to `>=` at the expiry boundary; the independent oracle failed two
reference-model tests. The NEEDS_HUMAN control recorded
`PATH_OUTSIDE_ALLOWED`, `PATH_REVIEW_REQUIRED`, and `POLICY_FILE_CHANGED`.

For the NEEDS_HUMAN control, the configured gauntlet is **UNAVAILABLE** as
evidence because it was SKIPPED. No substitute result is presented as a pass.
Concurrency/thread-safety and memory-bound stress layers are **N-A** for this
demo's intentionally unchanged functional scope. The external oracle is a
**SUBSTITUTED** differential check, not an independently authored attestation.

The final verifier line was:

```text
verify: PASS, FAIL, and NEEDS_HUMAN controls matched expectations
```

## Honest limits

- Release Gate reports the configured `quality-gauntlet` command as one check.
  It cannot independently attest the gauntlet's internal layer claims; those
  are supported here by reviewed source and negative controls.
- Independent fresh-context verification was not performed for this evidence
  report. Six-surface release qualification remains a separate release step.
- The specification, implementation, visible tests, policy, and oracle remain
  repository-owned artifacts. Keeping the oracle outside the candidate breaks
  candidate control, but not correlated authorship.
- The limiter is not thread-safe; expanded concurrency and memory behavior are
  outside this demo's scope and were intentionally not imported.
- A NaN-returning clock fails closed but is not rejected.
- Dependency installation and auditing require package-index/network access.
- A PASS is a configured-policy decision for one captured candidate. It is not
  a merge, deployment, security attestation, or proof that no defect exists.
