# Standalone Release Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `@subagent-driven-development` (recommended) or `@executing-plans` to execute
> this checklist task by task. Use `@test-driven-development` for every
> behavior change and `@verification-before-completion` before each completion
> claim.

**Goal:** Build the independent Python 3.11+ CLI and portable skill specified
by the v1 contracts in `release-gate/`.

**Architecture:** A small `release_gate` package owns configuration, Git
reconstruction, clean workspaces, process execution, report parsing, policy,
and evidence. Commands execute without a shell in separate base/candidate
clones on a trusted host. No A/B package, plugin, adapter, or demo runtime is a
dependency.

**Tech stack:** Python 3.11+, `argparse`, `subprocess`, `pathlib`, `dataclasses`,
PyYAML, jsonschema, defusedxml, `pathspec==1.1.1` (Git wildmatch), pytest,
pytest-cov, Ruff, mypy, and Git CLI.

---

Each task is a red-green-refactor slice. Commit only after its focused and
regression tests pass. Keep public behavior behind the checked-in v1 schemas;
do not silently extend the contract.

### Task 1: Package and contract test harness

**Files:** create `release-gate/pyproject.toml`,
`release-gate/src/release_gate/__init__.py`,
`release-gate/src/release_gate/py.typed`,
`release-gate/tests/test_contract_schemas.py`, and
`release-gate/tests/test_package_boundaries.py`.

- [ ] Write tests that load all three schemas with
  `Draft202012Validator.check_schema`, validate every example, and reject
  representative unknown fields and invalid versions.
- [ ] Write an AST/import test proving `release_gate` imports no repository
  A-series/B-series modules and a filesystem test proving it does not depend
  on `demo/gate`.
- [ ] Run `python -m pytest tests/test_contract_schemas.py tests/test_package_boundaries.py -q`;
  expect failure because the package metadata does not exist.
- [ ] Add Python `>=3.11`, console entry point `release-gate = release_gate.cli:main`,
  runtime dependencies, strict test/type/lint settings, and package the v1
  schemas as resources.
- [ ] Re-run the focused tests, then `python -m pytest -q`; expect pass.
- [ ] Commit with `build(release-gate): scaffold independent package`.

### Task 2: Configuration loading and semantic validation

**Files:** create `release-gate/src/release_gate/config.py`,
`release-gate/src/release_gate/models.py`, and
`release-gate/tests/test_config.py`.

- [ ] Write failing parameterized tests proving the exact
  `allowed_paths`/`forbidden_paths`/`review_required_paths` keys work and the
  legacy key spellings are rejected, plus YAML/schema errors, unknown keys,
  POSIX/drive/UNC/traversal paths, overlapping/out-of-range exit classes,
  invalid assertion references/modes, defaults, and limits.
- [ ] Test `prepare` as an ordered array, required IDs, duplicate IDs within
  preparation and globally across preparation/checks, stable ordering, and
  base-required/candidate-always workspace selection.
- [ ] Test the closed `inherit_environment` list separately from literal
  `environment`: literal-over-inherited precedence, missing host names,
  platform-list replacement and literal overlay, POSIX case sensitivity,
  Windows case-insensitive collisions/canonicalization, all-platform `HOME`
  reservation, POSIX `TMPDIR`, the additional Windows
  `USERPROFILE`/`HOMEDRIVE`/`HOMEPATH`/`TEMP`/`TMP` names, and the
  `RELEASE_GATE_` prefix.
- [ ] Test common and all three platform overlays, including the semantic rule
  that every directly invoked repository-local launcher is covered by
  `review_required_paths`.
- [ ] Run `python -m pytest tests/test_config.py -q`; expect the first case to
  fail because `load_config` is absent.
- [ ] Implement safe YAML loading, bundled-schema validation, immutable typed
  models, semantic checks, defaults, and deterministic Linux/macOS/Windows
  overlay resolution.
- [ ] Ensure diagnostics identify the YAML/JSON path and never echo secret-like
  environment values.
- [ ] Run the focused tests, `python -m mypy src/release_gate`, and
  `python -m ruff check src tests`; expect all pass.
- [ ] Commit with `feat(release-gate): validate versioned policy`.

### Task 3: Trusted base policy and temporary-index capture

**Files:** create `release-gate/src/release_gate/git.py` and
`release-gate/tests/test_git_capture.py`.

- [ ] Write failing repository-fixture tests proving policy comes from the
  peeled base commit; candidate add/modify/rename/delete of
  `.release-gate.yaml` cannot take effect, triggers `POLICY_FILE_CHANGED`, and
  is distinguished from invalid or missing base policy.
- [ ] Add cases for staged, unstaged, deleted, renamed, executable-mode,
  binary, Unicode/space-containing, non-ignored untracked, and ignored files;
  snapshot index bytes and `git status` before capture.
- [ ] Run `python -m pytest tests/test_git_capture.py -q`; expect failure because
  capture is absent.
- [ ] Implement ref resolution, `git show` base-policy loading, an isolated
  temporary index initialized from base, `git add -A`, binary-safe patch
  emission, and explicit exclusion of the engine evidence root.
- [ ] Assert the real index/status are byte-for-byte unchanged and the patch
  digest is deterministic in repeated runs.
- [ ] Run focused/full tests and commit with
  `feat(release-gate): capture worktree from trusted base`.

### Task 4: Independent clean workspaces

**Files:** create `release-gate/src/release_gate/workspaces.py` and
`release-gate/tests/test_workspaces.py`.

- [ ] Write failing tests that require two different clone roots at the same
  base commit, apply the patch only to candidate, verify a candidate tree ID,
  and detect an unapplicable or escaping patch.
- [ ] Test that generated files in one clone never appear in the other and that
  both clones are removed after success and exceptions while evidence remains.
- [ ] Run `python -m pytest tests/test_workspaces.py -q`; expect failure.
- [ ] Implement offline clean clones without shared build directories,
  detached checkout, safe binary patch application, tree writing, and bounded
  cleanup.
- [ ] Re-run focused/full tests and commit with
  `feat(release-gate): reconstruct isolated base and candidate`.

### Task 5: Cross-platform process runner and budgets

**Files:** create `release-gate/src/release_gate/process.py` and
`release-gate/tests/test_process.py`.

- [ ] Write failing helper-process tests for pass/fail/error/unlisted exits,
  negative POSIX signal returns, Windows 32-bit statuses through 4,294,967,295,
  spawn failure, timeout, direct argv with spaces, minimal environment,
  clone-specific `HOME` on every operating system, POSIX `TMPDIR`, consistent
  Windows home/temp aliases, and clone-contained `cwd`.
- [ ] Verify no host variable, including `PATH`, is inherited unless listed;
  requested missing names are `ERROR`; literal values win over inherited
  values; engine-owned home/temp variables win and are clone-specific; and
  Windows reserved-name and collision checks are case-insensitive.
- [ ] Add stream tests at, below, and above 1 MiB and 10 MiB, proving both pipes
  are drained, full-stream and retained digests differ correctly, and no
  deadlock occurs.
- [ ] Run `python -m pytest tests/test_process.py -q`; expect failure.
- [ ] Implement `shell=False` execution, platform-specific process-tree
  termination, monotonic durations, bounded concurrent pipe draining, hashing,
  and reason-coded outcomes.
- [ ] Run focused tests on the current OS and commit with
  `feat(release-gate): run bounded trusted-host controls`.

### Task 6: Reports, metrics, and assertions

**Files:** create `release-gate/src/release_gate/reports.py`,
`release-gate/src/release_gate/assertions.py`, fixtures under
`release-gate/tests/fixtures/reports/`, and tests
`release-gate/tests/test_reports.py` and
`release-gate/tests/test_assertions.py`.

- [ ] Write failing golden tests for nested JUnit aggregation, coverage.py JSON,
  JSON Metrics plus RFC 6901 pointers, malformed data, non-finite values, XML
  entities, missing/escaping/special files, and 5 MiB/50 MiB boundaries.
- [ ] Write a full comparison matrix for candidate, baseline,
  candidate-minus-baseline and `eq/ne/gt/gte/lt/lte`, including type and
  missing-operand errors.
- [ ] Run both focused test modules; expect failure.
- [ ] Implement the three closed-set parsers and pure assertion evaluator; do
  not introduce a parser registry, dynamic import, plugin, or adapter.
- [ ] Re-run focused/full tests and commit with
  `feat(release-gate): evaluate bounded report metrics`.

### Task 7: Scope, check status, and verdict policy

**Files:** create `release-gate/src/release_gate/policy.py` and
`release-gate/tests/test_policy.py`.

- [ ] Write pathspec Git-wildmatch conformance tests for `*`, `?`, bracket
  classes, slashless basename matching, slash anchoring, trailing `/`,
  including nested `x/foo/file` matching `foo/`, `**/x`, `a/**/b`, `a/**`,
  dotfiles, case sensitivity, rename old/new paths, deletion old paths, and
  symlinks without traversal. Reject leading `!/#`, trailing whitespace,
  backslash, drive/UNC, empty, `.`, and `..` components.
- [ ] Write the full verdict matrix: blocking `FAIL` -> `FAIL`; advisory
  `FAIL` -> `NEEDS_HUMAN`; informational `FAIL` is recorded only; every
  timeout, missing tool/environment, signal, unclassified exit, preparation
  failure, required-report problem, assertion operand error, and required
  `SKIPPED` -> `NEEDS_HUMAN` for every severity.
- [ ] Cover `allowed_paths`/`forbidden_paths`/`review_required_paths` overlaps,
  candidate/differential exit rules, preparation failure, and simultaneous
  `FAIL`/`ERROR` to prove `NEEDS_HUMAN` precedence.
- [ ] Prove a changed common or platform-specific local launcher prevents every
  repository command from running and produces `NEEDS_HUMAN` with
  `CONTROL_LAUNCHER_REVIEW`.
- [ ] Prove an early blocking/advisory classified failure still runs the other
  differential side and every later check in declaration order. Separately
  prove policy/launcher preflight review and preparation failure skip all
  remaining configured commands with reason-coded `SKIPPED` results.
- [ ] Run `python -m pytest tests/test_policy.py -q`; expect failure.
- [ ] Implement pure deterministic policy functions and stable uppercase reason
  codes; keep precedence and scope enforcement non-configurable.
- [ ] Run focused/full tests and commit with
  `feat(release-gate): decide three-way verdicts`.

### Task 8: Atomic evidence package

**Files:** create `release-gate/src/release_gate/evidence.py`,
`release-gate/src/release_gate/trace.py`, and
`release-gate/tests/test_evidence.py`.

- [ ] Write failing tests for the exact documented tree, restrictive creation,
  artifact hashes/sizes, base/candidate/config/engine identity, commands,
  durations, metrics, timestamps, environment names, and reason codes.
- [ ] Verify `result.json` and `manifest.json` against bundled schemas and add a
  tamper test proving `result.json`, `candidate.patch`, `effective-config.json`,
  and `trace.json` appear exactly once, `manifest.json` never self-inventories,
  and changed/missing/extra/duplicate artifacts fail verification.
- [ ] Reject artifact aliases `./x`, `a//b`, `a/./b`, `a/../b`, trailing `/`,
  absolute/drive/UNC/device/backslash paths, non-NFC strings, duplicate paths,
  NFC+Unicode-casefold collisions such as `Log.txt`/`log.txt`, and every
  NFC+casefold alias of the reserved `manifest.json` path.
- [ ] Test stream truncation metadata, total 200 MiB exhaustion using injected
  small test limits, existing-run refusal, atomic rename, interrupted
  finalization, `.incomplete`, and manifest-last ordering.
- [ ] Run `python -m pytest tests/test_evidence.py -q`; expect failure.
- [ ] Implement canonical JSON, SHA-256 inventory, atomic writes, verification,
  and cleanup without claiming immutability, signing, or attestation.
- [ ] Re-run focused/full tests and commit with
  `feat(release-gate): finalize tamper-evident runs`.

### Task 9: Orchestrator and CLI

**Files:** create `release-gate/src/release_gate/engine.py`,
`release-gate/src/release_gate/cli.py`,
`release-gate/tests/test_engine.py`, and `release-gate/tests/test_cli.py`.

- [ ] Write failing end-to-end tests for `init`, `validate`, and `run`, stable
  stdout lines, stderr diagnostics, no-overwrite behavior, base-policy loading,
  generic/Python/Node policies, and complete result paths.
- [ ] Prove candidate add/modify/rename/delete of `.release-gate.yaml` and a
  changed covered launcher execute zero repository commands, mark every
  preparation/check control `SKIPPED`, finalize `NEEDS_HUMAN`, and use base
  policy.
- [ ] Prove multiple preparation IDs execute base then candidate per item in
  declaration order, skip base when no differential check exists, and stop all
  remaining work after any preparation non-pass.
- [ ] Cover exits 0/1/2/3/4 and assert a schema-valid result for every 0/1/2
  path; inject finalization failure to distinguish exit 4 from
  `NEEDS_HUMAN`.
- [ ] Add interruption tests and prove expected tool/report failures finalize
  to exit 2 while preflight errors do not claim a verdict.
- [ ] Run `python -m pytest tests/test_engine.py tests/test_cli.py -q`; expect
  failure.
- [ ] Implement the fixed orchestration flow and argparse entry point without
  A3 request compatibility, adapters, or plugin hooks.
- [ ] Run focused/full tests and commit with
  `feat(release-gate): expose init validate and run`.

### Task 10: Portable skill

**Files:** create `release-gate/skill/release-gate/SKILL.md` and
`release-gate/tests/test_skill_contract.py`.

- [ ] Write a failing test that checks the skill invokes the standalone binary,
  requires an explicit base, consumes `result.json`, preserves all three
  verdict spellings, never edits/retries/reinterprets policy or results, and
  never performs or authorizes merge/deployment after `PASS`.
- [ ] Run `python -m pytest tests/test_skill_contract.py -q`; expect failure.
- [ ] Write the minimal portable skill with no machine-specific paths and no
  dependency on `demo/gate` or a plugin.
- [ ] Run focused/full tests and commit with
  `feat(release-gate): add portable invocation skill`.

### Task 11: Cross-platform release verification

**Files:** create `.github/workflows/release-gate-ci.yml` only after repository
owners approve CI scope; update `release-gate/README.md` with actual install
commands and supported versions after packaging is proven.

- [ ] Run on Python 3.11, 3.12, and 3.13 across Ubuntu, macOS, and Windows:
  `python -m pytest -q`, `python -m mypy src/release_gate`, and
  `python -m ruff check src tests`.
- [ ] On every OS, run black-box PASS, FAIL, NEEDS_HUMAN, invalid-config, and
  injected-internal-failure cases and archive their schema-valid evidence.
- [ ] Exercise each platform override and native timeout/process-tree cleanup;
  compare verdict and reason-code parity across operating systems.
- [ ] Build wheel/sdist, install each into a clean environment, invoke all three
  CLI commands outside this monorepo, and inspect archives to prove no A/B or
  demo package is included.
- [ ] Re-run legacy demo commands separately and verify
  `demo/gate/gate.sh` and `demo/gate/SKILL.md` are byte-for-byte unchanged.
- [ ] Commit verified workflow/docs with
  `test(release-gate): verify standalone gate across platforms`.

### Task 12: Adoption qualification

**Files:** add only new fixtures under `release-gate/tests/fixtures/adoption/`
and update canonical `release-gate/docs/adoption.md` with measured results.

- [ ] Create intentionally tracked generic, Python, and Node fixture repos with
  deterministic local dependencies and policies derived from the examples.
- [ ] For each fixture, prove untouched PASS, planted blocking FAIL,
  advisory FAIL/timeout/broken-tool NEEDS_HUMAN, informational ordinary FAIL
  non-contribution, review-required scope NEEDS_HUMAN, candidate policy tamper
  under base policy with zero commands, and evidence tamper detection.
- [ ] Reproduce the legacy demo's untouched, lazy, missing-tool, and
  scope-tamper control semantics without changing legacy files.
- [ ] Record gate version, config digest, base commit, candidate tree, result
  digest, operating system, and reason codes for every qualification run.
- [ ] Complete a final security review of command execution, path handling,
  XML/JSON parsing, environment minimization, and artifact disclosure.
- [ ] Run the entire cross-platform matrix once more and commit with
  `test(release-gate): qualify v1 adoption fixtures`.
