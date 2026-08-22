# Release Gate 0.6.0 Repair Loop and Graphify Plan

## Goal
Complete the bounded repair product while preserving human approval, deterministic gate decisions, isolated workspace edits, and non-gating Graphify guidance.

## Decisions
- Target release: 0.6.0; retain 0.5.0 as the bounded-controller milestone.
- The assistant diagnoses and edits only in the approved isolated workspace.
- The user approves repair start and final source application.
- Graphify remains optional, read-only, untrusted, and non-gating.
- Use one skill-level Graphify diagnosis after eligible C0 assessment, bounded to failed checks and approved/changed paths.
- Keep the Python controller Graphify-free and preserve existing result, manifest, repair-session, and verdict contracts.

## Implementation
1. Make `SKILL.md` and `references/repair.md` explicit state dispatchers. When evaluation returns `repairing` plus `edit_workspace`, request the workspace again, let the assistant revise it, and evaluate again. Stop on `none`; present final evidence on `final_approval_and_apply`.
2. Add skill contract tests and a CLI integration test for C0 FAIL -> C1 FAIL -> C2 PASS -> final approval -> applied. Add repeated-candidate end-to-end coverage.
3. Add one optional C0 Graphify query in the skill. Require compatibility preflight, existing non-stale graph, read-only host access, changed/approved-path bounds, direct source verification, and separate untrusted hints. Missing, stale, failing, malformed, or adversarial Graphify must not retry, block, change scope, budget, verdict, commands, or approvals.
4. Expand qualification schema, validator, tests, and documentation from 18 to 21 cases with `repair-pass-within-budget`, `repair-needs-human-stopped`, and `repair-graphify-adversarial`. Require the C1/C2 loop and Graphify safety observations on all six surfaces.
5. Bump to 0.6.0 through `scripts/sync_release_version.py`, update release documentation/workflows, build deterministic RC assets twice, run the complete test suite, run `graphify update .`, and qualify a real RC before promotion.

## Verification gates
- Focused skill and repair integration tests pass before qualification edits.
- Qualification tests reject missing cases, markers, duplicate cases, wrong outcomes, reused evidence, stale tags, and placeholder hashes.
- All six assistant surfaces produce unique evidence for the exact RC assets and the full 21-case corpus.
- Final promotion uses the exact qualified RC commit and byte-identical assets.

## Scope exclusions
No autonomous source apply, no Graphify runtime dependency, no Graphify rebuild during repair, no per-attempt Graphify queries, no new repair diagnosis schema, and no attempt-budget increase.
