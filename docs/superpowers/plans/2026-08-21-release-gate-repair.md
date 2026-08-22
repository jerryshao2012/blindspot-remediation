# Release Gate Repair Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit, easy-to-run `$release-gate repair --base <ref>` workflow that can repair eligible deterministic gate failures while keeping `release-gate run` immutable.

**Architecture:** The existing release gate remains the only verdict oracle and continues to produce unchanged `PASS`, `FAIL`, and `NEEDS_HUMAN` evidence. A new deterministic repair controller manages sessions, isolated workspaces, attempt lineage, budgets, eligibility, and final apply safety; the portable skill drives diagnosis and code edits through that controller. The first release requires no repository setup, uses a bundled generic repair workflow, and optionally consumes base-trusted `.release-gate/repair/` playbooks when present.

**Tech Stack:** Python 3.11+, argparse, Pydantic-style existing models where useful, Git CLI, JSON Schema 2020-12, pytest, mypy, ruff, existing release-gate evidence and skill packaging scripts.

---

## Approved Product Decisions

- User-facing flow is one explicit invocation: `$release-gate repair --base <ref>`.
- The user sees one short start approval summary and, only after a passing repaired candidate, one final diff/apply approval.
- Automatic repair is eligible only for verified `FAIL` results caused by blocking command or assertion failures with complete evidence.
- Stop immediately for `PASS`, `NEEDS_HUMAN`, scope findings, policy changes, launcher changes, repair-harness changes, skipped checks, execution errors, invalid evidence, exit 3/4, repeated candidates, or budget exhaustion.
- Default budget is original candidate plus at most two repaired candidates: `C0`, `C1`, and `C2`.
- The source worktree and real Git index must not change before final apply approval.
- Lesson proposals are generated as reviewable artifacts only; they never rewrite harness guidance automatically.
- Existing `release-gate run`, result schema, manifest schema, verdict precedence, dashboard meaning, CI behavior, and release assets remain backward compatible.

## File Structure

- Create `release-gate/src/release_gate/repair/models.py`: session states, attempt records, approval documents, repair requests, and JSON serialization helpers.
- Create `release-gate/src/release_gate/repair/controller.py`: deterministic repair state machine, eligibility checks, attempt evaluation, resume, and final apply orchestration.
- Create `release-gate/src/release_gate/repair/workspace.py`: isolated clone creation, patch application/export, path enforcement, source recapture matching, and rollback-safe final apply.
- Create `release-gate/src/release_gate/repair/evidence.py`: `_repairs/<session-id>/` artifact writes, session manifest, summary markdown, and lesson proposal generation.
- Create `release-gate/src/release_gate/repair/playbooks.py`: optional base-commit playbook discovery and validation.
- Create `release-gate/src/release_gate/repair/__init__.py`: package boundary.
- Modify `release-gate/src/release_gate/cli.py`: add hidden controller-oriented `repair-*` subcommands and keep public usage concise.
- Modify `release-gate/skills/release-gate/SKILL.md`: add explicit `repair` workflow with simple UX and safety constraints.
- Create `release-gate/skills/release-gate/references/repair.md`: detailed skill-side repair procedure.
- Modify `release-gate/scripts/build_skill_archives.py` and `release-gate/scripts/verify_release_assets.py`: include and verify the repair reference.
- Modify docs: `release-gate/README.md`, `release-gate/docs/cli.md`, `release-gate/docs/design.md`, `release-gate/docs/evidence.md`, `release-gate/docs/security.md`, and `release-gate/docs/qualification.md`.
- Add tests under `release-gate/tests/test_repair_*.py`, plus skill/archive/docs tests where needed.

## Task 1: Repair Session Models and Schemas

**Files:**
- Create: `release-gate/src/release_gate/repair/__init__.py`
- Create: `release-gate/src/release_gate/repair/models.py`
- Test: `release-gate/tests/test_repair_models.py`

- [ ] **Step 1: Write failing model tests**

  Cover stable JSON round-trips for:
  - `RepairState`: `awaiting_approval`, `repairing`, `awaiting_final_approval`, `stopped`, `applied`.
  - `RepairStopReason`: `already_pass`, `ineligible_verdict`, `ineligible_reason_codes`, `policy_changed`, `launcher_changed`, `harness_changed`, `invalid_evidence`, `attempt_budget_exhausted`, `repeated_candidate`, `source_changed`, `rollback_failed`.
  - `RepairAttempt`: candidate label, gate run id, base commit, candidate tree, patch digest, result digest, manifest digest, verdict, reason codes, failed check ids.
  - `RepairSession`: version, session id, repo path, base ref, base commit, approved paths, attempt cap, attempts, state, next action, created/updated timestamps.

  Run: `cd release-gate && uv run pytest tests/test_repair_models.py -q`
  Expected: FAIL because the package and models do not exist.

- [ ] **Step 2: Implement minimal dataclasses**

  Use frozen dataclasses or existing project model style. Store enums as lowercase strings in JSON. Keep schema closed by validating required fields on load; do not add a public JSON Schema yet unless tests prove it is needed.

- [ ] **Step 3: Add digest helpers**

  Add `sha256_bytes(data: bytes) -> str` and `sha256_file(path: Path) -> str` helpers in `repair/models.py` only if no local reusable helper fits cleanly.

- [ ] **Step 4: Run tests**

  Run: `cd release-gate && uv run pytest tests/test_repair_models.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add release-gate/src/release_gate/repair release-gate/tests/test_repair_models.py
  git commit -m "feat(release-gate): add repair session models"
  ```

## Task 2: Eligibility From Existing Gate Evidence

**Files:**
- Create: `release-gate/src/release_gate/repair/controller.py`
- Test: `release-gate/tests/test_repair_eligibility.py`

- [ ] **Step 1: Write failing eligibility matrix tests**

  Use small result/manifest fixtures, not full gate executions. Assert:
  - `PASS` returns terminal `already_pass`.
  - `NEEDS_HUMAN` is ineligible.
  - Exit 3/4 or missing result/manifest is ineligible.
  - `FAIL` is eligible only when all contributing root reasons are `COMMAND_FAILED` or `ASSERTION_FAILED`.
  - Scope reason codes are ineligible: `PATH_FORBIDDEN`, `PATH_OUTSIDE_ALLOWED`, `PATH_REVIEW_REQUIRED`.
  - Any check with status `ERROR` or `SKIPPED` is ineligible.
  - Advisory failures producing human review are ineligible.
  - Policy or launcher change reason codes are ineligible.

  Run: `cd release-gate && uv run pytest tests/test_repair_eligibility.py -q`
  Expected: FAIL because the controller does not exist.

- [ ] **Step 2: Implement `assess_attempt()`**

  Input: a gate result path and manifest path. Output: an eligibility object containing state, stop reason, failed check ids, allowed root reason codes, and human-readable explanation.

- [ ] **Step 3: Verify evidence before classification**

  Call existing `release_gate.evidence.verify_run()` on the gate run directory before reading result semantics. Invalid evidence must stop as `invalid_evidence`.

- [ ] **Step 4: Run tests**

  Run: `cd release-gate && uv run pytest tests/test_repair_eligibility.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add release-gate/src/release_gate/repair/controller.py release-gate/tests/test_repair_eligibility.py
  git commit -m "feat(release-gate): classify repair eligibility"
  ```

## Task 3: Repair Evidence Namespace

**Files:**
- Create: `release-gate/src/release_gate/repair/evidence.py`
- Modify: `release-gate/src/release_gate/observability.py`
- Test: `release-gate/tests/test_repair_evidence.py`
- Test: `release-gate/tests/test_observability.py`

- [ ] **Step 1: Write failing evidence tests**

  Assert the controller writes session artifacts under `<evidence-root>/_repairs/<session-id>/`:
  - `repair-session-v1.json`
  - `repair-summary.md`
  - `approval-request.json`
  - `lesson-proposal.md` only when useful data exists
  - `repair-manifest.json`

  Assert all writes are atomic enough for interrupted sessions: no partial JSON should be treated as valid on resume.

- [ ] **Step 2: Write failing observability skip test**

  Add a directory named `_repairs` next to normal run directories and assert dashboard collection ignores it without warnings.

- [ ] **Step 3: Implement repair evidence writer**

  Follow the existing evidence style: append or replace only session-owned files, compute SHA-256 digests, use relative artifact paths, and never copy gate run evidence. Reference gate attempts by result and manifest digest.

- [ ] **Step 4: Update observability scanners**

  Teach both `dir_fd` and path fallback scanners to skip `_repairs` alongside `_observability`.

- [ ] **Step 5: Run tests**

  Run: `cd release-gate && uv run pytest tests/test_repair_evidence.py tests/test_observability.py -q`
  Expected: PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add release-gate/src/release_gate/repair/evidence.py release-gate/src/release_gate/observability.py release-gate/tests/test_repair_evidence.py release-gate/tests/test_observability.py
  git commit -m "feat(release-gate): retain repair session evidence"
  ```

## Task 4: Isolated Repair Workspace

**Files:**
- Create: `release-gate/src/release_gate/repair/workspace.py`
- Test: `release-gate/tests/test_repair_workspace.py`

- [ ] **Step 1: Write failing workspace tests**

  Use temporary Git repositories. Cover:
  - Create disposable clone at base commit.
  - Apply the original candidate patch to form `C0`.
  - Export repaired patch and candidate tree.
  - Reject edits outside approved paths.
  - Reject unchanged candidate.
  - Reject repeated candidate tree or patch digest.
  - Never mutate the source worktree or source index during workspace operations.

- [ ] **Step 2: Implement clone and patch helpers**

  Use Git CLI with closed environments similar to `release_gate.git`. Keep temporary workspaces outside source and evidence roots. Avoid shell invocation.

- [ ] **Step 3: Implement path enforcement**

  Approved paths are:
  - original `result.scope.changed_paths`
  - optional base-trusted playbook extra paths for failed checks
  - minus any forbidden or review-required paths from the base policy

  Use the same gitwildmatch/pathspec semantics as the gate policy where possible.

- [ ] **Step 4: Run tests**

  Run: `cd release-gate && uv run pytest tests/test_repair_workspace.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add release-gate/src/release_gate/repair/workspace.py release-gate/tests/test_repair_workspace.py
  git commit -m "feat(release-gate): isolate repair workspaces"
  ```

## Task 5: Optional Base-Trusted Playbooks

**Files:**
- Create: `release-gate/src/release_gate/repair/playbooks.py`
- Test: `release-gate/tests/test_repair_playbooks.py`

- [ ] **Step 1: Write failing playbook tests**

  Cover:
  - Missing `.release-gate/repair/` returns the bundled generic workflow.
  - Playbooks are loaded only from the selected base commit.
  - Candidate changes to `.release-gate/repair/**` make automatic repair ineligible.
  - Per-check playbook path allowances are optional and closed to the gate allowed scope.
  - Malformed playbook metadata is ignored with a warning in the approval request, not treated as passed assurance.

- [ ] **Step 2: Implement base loader**

  Use `git show <base>:.release-gate/repair/...` style reads through the same resolved base commit used by the gate. Never read candidate or working-tree playbooks for repair authority.

- [ ] **Step 3: Implement generic fallback**

  The fallback gives the agent only result/manifest/log evidence, failed check ids, changed paths, and the approved edit boundary.

- [ ] **Step 4: Run tests**

  Run: `cd release-gate && uv run pytest tests/test_repair_playbooks.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add release-gate/src/release_gate/repair/playbooks.py release-gate/tests/test_repair_playbooks.py
  git commit -m "feat(release-gate): load base-trusted repair playbooks"
  ```

## Task 6: Controller State Machine and Private CLI Protocol

**Files:**
- Modify: `release-gate/src/release_gate/repair/controller.py`
- Modify: `release-gate/src/release_gate/cli.py`
- Test: `release-gate/tests/test_repair_controller.py`
- Test: `release-gate/tests/test_cli_config.py`

- [ ] **Step 1: Write failing state-machine tests**

  Test the internal protocol, not agent prose:
  - `repair-start` runs `C0` through existing `run_gate()`, writes approval request, and stops or awaits approval.
  - `repair-approve` validates exact approval JSON and enters `repairing`.
  - `repair-request` emits failed checks, reason codes, evidence paths, allowed paths, and attempt number.
  - `repair-evaluate` runs the gate for `C1` or `C2`, records lineage, and either requests another repair, stops, or awaits final approval.
  - Attempt cap is enforced at two repairs.
  - Resume reloads session JSON and reconstructs missing disposable workspace from retained patches.

- [ ] **Step 2: Add private subcommands**

  Add argparse subcommands intended for the skill:
  - `repair-start --repo PATH --base REF [--output PATH] [--session-id ID]`
  - `repair-approve --session PATH --approval PATH`
  - `repair-request --session PATH`
  - `repair-evaluate --session PATH`
  - `repair-finalize --session PATH`
  - `repair-apply --session PATH --approval PATH`
  - `repair-cancel --session PATH`

  Keep `release-gate --help` focused. Public docs should describe `$release-gate repair --base REF` as the skill workflow, not require users to run these protocol commands manually.

- [ ] **Step 3: Add stable stdout lines**

  Every protocol command prints:
  - `REPAIR_SESSION: <path>`
  - `REPAIR_STATE: <state>`
  - `NEXT_ACTION: <action>`

  It may also print `REPAIR_REQUEST: <path>` or `REPAIR_SUMMARY: <path>` when present.

- [ ] **Step 4: Preserve existing CLI behavior**

  Existing `--version`, `init`, `validate`, and `run` tests must be unchanged. Invalid repair protocol usage exits 3. Internal controller failure exits 4.

- [ ] **Step 5: Run tests**

  Run: `cd release-gate && uv run pytest tests/test_repair_controller.py tests/test_cli_config.py -q`
  Expected: PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add release-gate/src/release_gate/repair/controller.py release-gate/src/release_gate/cli.py release-gate/tests/test_repair_controller.py release-gate/tests/test_cli_config.py
  git commit -m "feat(release-gate): add repair controller protocol"
  ```

## Task 7: Final Apply Safety

**Files:**
- Modify: `release-gate/src/release_gate/repair/workspace.py`
- Modify: `release-gate/src/release_gate/repair/controller.py`
- Test: `release-gate/tests/test_repair_apply.py`

- [ ] **Step 1: Write failing apply tests**

  Cover:
  - Source recapture must exactly match `C0` before final apply.
  - Apply uses a temporary index and does not stage unrelated files.
  - Post-apply recapture must exactly match the passing candidate.
  - Source changes between approval and apply stop as `source_changed`.
  - Apply failure rolls back changed files where possible and records rollback status.
  - The command never commits, pushes, merges, or deploys.

- [ ] **Step 2: Implement final approval document**

  Require approval JSON to include session id, final candidate tree, final patch digest, and a user approval timestamp. Reject approval for a different session or candidate.

- [ ] **Step 3: Implement transactional apply**

  Reuse candidate capture concepts from `release_gate.git`. Apply only the final patch to the source after identity match. Verify candidate identity after apply. On failure, restore from pre-apply patch/state without using destructive broad reset commands.

- [ ] **Step 4: Run tests**

  Run: `cd release-gate && uv run pytest tests/test_repair_apply.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add release-gate/src/release_gate/repair release-gate/tests/test_repair_apply.py
  git commit -m "feat(release-gate): safely apply repaired candidates"
  ```

## Task 8: Skill Workflow and Packaged References

**Files:**
- Modify: `release-gate/skills/release-gate/SKILL.md`
- Create: `release-gate/skills/release-gate/references/repair.md`
- Modify: `release-gate/scripts/build_skill_archives.py`
- Modify: `release-gate/scripts/verify_release_assets.py`
- Test: `release-gate/tests/test_skill.py`
- Test: `release-gate/tests/test_skill_archives.py`
- Test: `release-gate/tests/validate_skill.py`

- [ ] **Step 1: Write failing skill tests**

  Assert:
  - The skill documents explicit `repair` invocation only.
  - Repair workflow reads `references/repair.md`.
  - Repair instructions forbid retrying `NEEDS_HUMAN`, editing policy/evidence, changing verdicts, installing dependencies, or using network access.
  - The skill archive includes `references/repair.md`.
  - Archive verification rejects a missing or mismatched repair reference.

- [ ] **Step 2: Update `SKILL.md`**

  Add a concise `repair` section:
  - Run compatibility preflight first.
  - Call controller protocol commands only as instructed by `references/repair.md`.
  - Show the user one approval summary before repairs.
  - Edit only the controller-provided workspace and approved paths.
  - Stop exactly when the controller says to stop.
  - Present final diff/evidence before `repair-apply`.

- [ ] **Step 3: Add `references/repair.md`**

  Include the private protocol loop and response templates. Keep user-facing language short: "Repair stopped", "Repair needs approval", "Repair passed and is ready to apply".

- [ ] **Step 4: Update archive builder and verifier**

  Include `release-gate/references/repair.md` in every skill tarball and deterministic asset verification.

- [ ] **Step 5: Run tests**

  Run: `cd release-gate && uv run pytest tests/test_skill.py tests/test_skill_archives.py -q && uv run python tests/validate_skill.py`
  Expected: PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add release-gate/skills/release-gate release-gate/scripts/build_skill_archives.py release-gate/scripts/verify_release_assets.py release-gate/tests/test_skill.py release-gate/tests/test_skill_archives.py release-gate/tests/validate_skill.py
  git commit -m "feat(release-gate): teach skill the repair workflow"
  ```

## Task 9: Docs and Qualification

**Files:**
- Modify: `release-gate/README.md`
- Modify: `release-gate/docs/cli.md`
- Modify: `release-gate/docs/design.md`
- Modify: `release-gate/docs/evidence.md`
- Modify: `release-gate/docs/security.md`
- Modify: `release-gate/docs/qualification.md`
- Modify: `release-gate/CHANGELOG.md`
- Test: `release-gate/tests/test_release_workflows.py`
- Test: `release-gate/tests/test_release_assets.py`

- [ ] **Step 1: Write failing docs/qualification tests**

  Add assertions for:
  - `repair` documented as a skill workflow around `run`.
  - Docs state the gate never repairs during `run`.
  - Evidence docs define `_repairs`.
  - Security docs describe untrusted logs and no network/dependency install in the repair worker.
  - Qualification docs require one repaired-to-pass case and one no-retry `NEEDS_HUMAN` case.

- [ ] **Step 2: Update docs**

  Keep adoption copy simple:
  - "Run `$release-gate repair --base main`."
  - "Approve the bounded repair session."
  - "Review the final diff and evidence."

  Put private controller command details in developer docs only.

- [ ] **Step 3: Update changelog**

  Add an unreleased entry describing the explicit repair workflow and unchanged gate verdict contracts.

- [ ] **Step 4: Run tests**

  Run: `cd release-gate && uv run pytest tests/test_release_workflows.py tests/test_release_assets.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add release-gate/README.md release-gate/docs release-gate/CHANGELOG.md release-gate/tests/test_release_workflows.py release-gate/tests/test_release_assets.py
  git commit -m "docs(release-gate): document bounded repair workflow"
  ```

## Task 10: End-to-End Repair Demo and Regression Suite

**Files:**
- Create: `release-gate/tests/test_repair_integration.py`
- Modify: `.github/workflows/release-gate-ci.yml`
- Optionally create: `release-gate/demo/repair/README.md`

- [ ] **Step 1: Write failing integration tests**

  Build two temporary repositories:
  - A deterministic failing test where the repair worker simulation edits an approved source file and reaches `PASS` within one attempt.
  - A `NEEDS_HUMAN` case where no workspace edit or second gate run occurs.

  The simulation should call controller protocol commands and perform a simple deterministic edit. Do not call an LLM in tests.

- [ ] **Step 2: Add Windows/macOS-safe test helpers**

  Avoid shell scripts. Use Python subprocess with argument arrays and path-safe temp directories.

- [ ] **Step 3: Update CI**

  Ensure the repair integration tests run in the existing Ubuntu, macOS, and Windows matrix. Keep timeout reasonable and do not add network dependencies.

- [ ] **Step 4: Run targeted integration**

  Run: `cd release-gate && uv run pytest tests/test_repair_integration.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add release-gate/tests/test_repair_integration.py .github/workflows/release-gate-ci.yml
  git commit -m "test(release-gate): cover bounded repair workflow"
  ```

## Task 11: Full Verification and Graph Update

**Files:**
- No planned source changes beyond fixes required by verification.

- [ ] **Step 1: Run full release-gate test suite**

  Run: `cd release-gate && uv run pytest --cov=release_gate --cov-report=term-missing -q`
  Expected: PASS and coverage at or above the configured threshold.

- [ ] **Step 2: Run static checks**

  Run: `cd release-gate && uv run mypy src/release_gate`
  Expected: PASS.

  Run: `cd release-gate && uv run ruff check src tests scripts`
  Expected: PASS.

- [ ] **Step 3: Run packaging checks**

  Run: `cd release-gate && uv run python scripts/sync_schemas.py`
  Expected: `SCHEMAS IN SYNC`.

  Run: `cd release-gate && uv run python scripts/sync_release_version.py --check`
  Expected: no diff/error.

  Run: `cd release-gate && uv run python -m build --no-isolation`
  Expected: wheel and sdist build successfully.

  Run: `cd release-gate && uv run python scripts/smoke_installed.py`
  Expected: installed CLI smoke test passes.

  Run: `cd release-gate && uv run python tests/validate_skill.py`
  Expected: skill validation passes.

- [ ] **Step 4: Run deterministic archive check**

  Run the same archive build twice in a temp directory and diff the outputs, matching CI behavior.
  Expected: no differences.

- [ ] **Step 5: Update graphify**

  From repository root, run: `graphify update .`
  Expected: graph updates without blocking errors.

- [ ] **Step 6: Final commit**

  ```bash
  git status --short
  git add <only intended changed files>
  git commit -m "feat(release-gate): add bounded repair harness"
  ```

## Acceptance Checklist

- [ ] `$release-gate repair --base <ref>` is the only user-facing repair entry point.
- [ ] Existing `release-gate run` behavior, stdout, exit codes, result schema, manifest schema, and dashboard semantics remain unchanged.
- [ ] Repair can start without repository-specific setup.
- [ ] Optional `.release-gate/repair/` playbooks are loaded only from the base commit.
- [ ] `NEEDS_HUMAN`, scope findings, policy/launcher/playbook changes, errors, skipped work, invalid evidence, and repeated candidates stop without edit/retry.
- [ ] At most two repaired candidates are evaluated.
- [ ] Original source worktree and real index are unchanged until final apply approval.
- [ ] Every attempt has verified ordinary gate evidence and chained repair-session evidence.
- [ ] Successful repairs emit a reviewable final diff and optional lesson proposal, but never self-promote future instructions.
- [ ] Cross-platform CI passes on Ubuntu, macOS, and Windows.

## Review Note

The intended plan-review subagent could not run in this Codex session because both attempts failed with an environment authentication refresh error before any review work began. Treat Task 11 verification plus the first implementation checkpoint review as mandatory before merging.
