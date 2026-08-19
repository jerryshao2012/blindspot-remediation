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
PyYAML, `jsonschema[format]`, defusedxml, `pathspec==1.1.1` (Git wildmatch),
pytest, pytest-cov, Ruff, mypy, and Git CLI. JSON Schema format checking is an
explicit dependency but does not replace the gate's strict timestamp parser.

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
  representative unknown fields and invalid versions. Add shared contract
  probes for portable run/control/report IDs, per-component artifact paths,
  and the empty RFC 6901 root pointer. Prove result/manifest reason-code enums
  have the documented parity and reject unknown or wrong-context codes. Pass
  an explicit `FormatChecker` for every schema validation path and include a
  regression demonstration that `format` is otherwise annotation-only.
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
- [ ] Exercise every declared count/string boundary and raw/effective UTF-8
  1 MiB limits: 32 preparations, 128 checks, 16 reports and 64 assertions per
  check, 256 scope/exit entries, 64 argv/each-environment entries, the
  198-name effective manifest bound, and the documented
  128/1,024/4,096-code-point limits. Reject non-finite numeric values and an
  individual report limit above effective `limits.report_bytes`. Exercise the
  finite binary64 endpoints, one value beyond each endpoint, negative-zero
  normalization, shortest round-trip encodings through 24 bytes, and
  nonnegative signed-64-bit duration boundaries.
- [ ] Test `prepare` as an ordered array, required IDs, duplicate IDs within
  preparation and globally across preparation/checks, stable ordering, and
  base-required/candidate-always workspace selection.
- [ ] Test 1-64-character lowercase preparation/check/report IDs at both
  length boundaries. Reject trailing dots, ASCII controls, Windows-illegal
  characters, and case-insensitive `CON`/`PRN`/`AUX`/`NUL`/`COM1`-`COM9`/
  `LPT1`-`LPT9` basenames with and without extensions.
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
  snapshot index bytes, refs, `git status`, and filename/content inventories of
  both per-worktree and shared Git object databases before capture.
- [ ] Run `python -m pytest tests/test_git_capture.py -q`; expect failure because
  capture is absent.
- [ ] Implement ref resolution, `git show` base-policy loading, an isolated
  temporary index plus temporary `GIT_OBJECT_DIRECTORY` initialized from base,
  source/common objects exposed as read-only `GIT_ALTERNATE_OBJECT_DIRECTORIES`,
  `git add -A`, binary-safe patch
  emission, and exclusion of descendants of only the literal default
  `.release-gate/runs/` subtree after a no-follow inspection of the node and
  its parent. Prove a tracked or untracked candidate symlink/reparse/junction
  at `.release-gate` or `runs` is rejected rather than masked and a custom
  in-repository path cannot create another exclusion.
- [ ] Scrub every ambient `GIT_*` variable, rebuild a closed capture
  environment, and test native `os.pathsep` plus
  Git quoting for alternate paths containing spaces, quotes, and the platform
  separator. Set and test `GIT_OPTIONAL_LOCKS=0` on every source read. Keep the
  temporary object store through patch/tree emission; test linked worktrees
  and pre-existing validated alternates.
- [ ] Assert the real index/status/refs and both source object stores are
  byte-for-byte unchanged and the patch digest is deterministic in repeated
  runs. Destination validation and every
  exit-3 redirect rejection must not create, delete, replace, or follow a
  source entry before capture.
- [ ] Run focused/full tests and commit with
  `feat(release-gate): capture worktree from trusted base`.

### Task 4: Independent clean workspaces

**Files:** create `release-gate/src/release_gate/workspaces.py` and
`release-gate/tests/test_workspaces.py`.

- [ ] Write failing tests that require two different clone roots at the same
  base commit, apply the patch only to candidate, verify a candidate tree ID,
  and detect an unapplicable or escaping patch.
- [ ] Require canonical component-aware disjointness among the effective run
  directory, source/Git metadata, and both clones, including symlink aliases
  and Windows case variants; retry clone placement or fail before execution.
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
- [ ] Exercise the complete normalized lifecycle matrix: pass/fail and
  configured/unclassified exits retain nonnegative integers with
  `timed_out: false`; a negative return becomes `COMMAND_SIGNALLED`; timeout
  discards the termination return and uses null/true; missing executable maps
  to `COMMAND_SPAWN_FAILED` with null/false; missing inherited environment and
  safely finalized interruption also use null/false; and skipped records use
  null/false with empty metrics. Reject every mismatched reason,
  classification, exit, and timeout combination.
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
- [ ] Prove an absent, unreferenced optional report is only
  `OPTIONAL_REPORT_MISSING`; an assertion that needs it is `ERROR`; and a
  present optional report that is unsafe, oversized, or unparsable is `ERROR`.
- [ ] Cover the empty pointer `""` selecting the whole document, `/` selecting
  an empty-key member, `//`, and `~0`/`~1` escapes. Reject a bare name, `~2`,
  and a dangling `~`; include scalar root `json-metrics` assertions.
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
  classes, slashless basename matching, one leading `/` root anchor, slash
  anchoring, trailing `/`,
  including nested `x/foo/file` matching `foo/`, `**/x`, `a/**/b`, `a/**`,
  dotfiles, case sensitivity, rename old/new paths, deletion old paths, and
  symlinks without traversal. Prove `/foo` matches root `foo` and descendants
  such as `foo/x` while excluding `x/foo`; `/*.md` excludes `docs/x.md`; and
  `/docs/` is root-directory-only. Prove `/README.md` selects that root entry
  and also its descendants when the entry is a directory; pattern matching
  does not infer a file type. Reject bare `/`, `//`, leading `!/#`,
  trailing whitespace, backslash, drive/UNC/device syntax including after an
  anchor, empty, `.`, and `..` components.
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
  codes; keep precedence and scope enforcement non-configurable. Test the
  complete v1 registry, context allowlists, empty no-diagnostic contexts,
  ASCII-sorted/deduplicated arrays, root aggregation, and rejection of unknown
  or vendor codes. Reject `NEEDS_HUMAN` containing only forbidden/outside scope
  failure atoms, and reject `ERROR` containing only a non-verdict diagnostic.
  Reject generic `REQUIRED_CONTROL_SKIPPED` beside a narrower skip cause. Scope
  failures do not short-circuit configured controls. For each manifest
  execution, reject multiple terminal-cause codes; ensure preparation metrics
  are empty and preparation reasons cannot contain report diagnostics.
- [ ] Run focused/full tests and commit with
  `feat(release-gate): decide three-way verdicts`.

### Task 8: Atomic evidence package

**Files:** create `release-gate/src/release_gate/evidence.py`,
`release-gate/src/release_gate/timestamps.py`,
`release-gate/src/release_gate/trace.py`, and
`release-gate/tests/test_evidence.py`.

- [ ] Write failing tests for the exact documented tree, restrictive creation,
  artifact hashes/sizes, base/candidate/config/engine identity, commands,
  durations, metrics, timestamps, environment names, `control_id` for both
  preparation and check executions, and reason codes. Reject every unrecognized
  execution identifier field.
- [ ] Test manifest lifecycle conditionals directly: pass/fail require a
  nonnegative integer and false timeout; skipped requires null/false/empty
  metrics; configured/unclassified exit errors require a nonnegative integer;
  spawn/missing-environment/interruption require null/false; timeout requires
  null/true in both directions; signal requires a negative integer/false; and
  every negative exit requires the signal reason. No execution has multiple
  terminal causes. Reject report diagnostics or metrics on preparation and
  metrics on skipped work.
- [ ] Implement and test the strict timestamp parser plus schema
  `FormatChecker`. Accept real leap day, `Z`, fractions of 1 and 9 digits,
  `+00:00`, `+14:00`, `-14:00`, and `-00:30`. Reject a missing zone, space or
  lowercase separator, year 0000, non-leap February 29, February 30, hour 24,
  second 60 even on historical leap-second dates, empty or 10-digit fractions,
  `+14:01`, `+15:00`, `-00:00`, and trailing newline. Prove the emitter always
  writes uppercase UTC `Z` and every result/manifest timestamp is checked by
  both validators.
- [ ] Verify `result.json` and `manifest.json` against bundled schemas and add a
  tamper test proving `result.json`, `candidate.patch`, `effective-config.json`,
  and `trace.json` appear exactly once, `manifest.json` never self-inventories,
  and changed/missing/extra/duplicate artifacts fail verification.
- [ ] Reject artifact aliases `./x`, `a//b`, `a/./b`, `a/../b`, trailing `/`,
  absolute/drive/UNC/backslash paths, ASCII controls, Windows-illegal
  `<>:"|?*`, trailing dot/space components, and all case variants of DOS
  device basenames with extensions. Exercise 1/128/129-code-point component,
  32/33-component, and 1,024/1,025-code-point path boundaries.
- [ ] Reject non-NFC components, duplicate paths, NFC+Unicode-casefold
  collisions such as `Log.txt`/`log.txt`, and every NFC+casefold alias of the
  reserved `manifest.json` path. Prove the closed `.xml`/`.json` report-name
  mapping keeps a maximum-length report ID within the component limit.
- [ ] Test exact byte accounting over every retained regular file, including
  the non-inventoried manifest and safe `.incomplete`; exclude directories,
  pathnames, allocation units, and discarded temporary files. Exercise 16 MiB
  and 200 MiB total boundaries and prove a complete package never exceeds its
  configured total.
- [ ] Test the fixed 7 MiB finalization reserve and 2/4/1 MiB sublimits using
  injected small analogues: exact-fit and one-byte-over patch/config sums,
  accepted exact patches never truncated, whole-or-omitted reports, stable
  control/base/candidate/stdout/stderr/report allocation, concurrent stream
  arrival independence, quota return, budget-stop SKIPPED checks, and trace's
  500-byte-event/2,048-event boundaries with its reserved terminal summary.
  Budget-stopped checks use `EVIDENCE_BUDGET_EXHAUSTED`, not the generic skip
  fallback. A post-proof cap breach must be exit 4.
- [ ] Test stream truncation metadata, existing-run refusal, atomic rename,
  interrupted finalization, `.incomplete`, and manifest-last ordering. For the
  default root, swap a verified component before each result/manifest rename and prove
  pinned-handle I/O cannot be redirected, late identity loss exits 4, and an
  incomplete marker is attempted only through a still-verified handle.
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
- [ ] Test run IDs at 1 and 128 characters and reject 129 characters, trailing
  dot, ASCII controls, Windows-illegal characters, DOS device basenames with
  extensions, and an existing NFC-plus-casefold-equivalent sibling. Prove
  generated separator-free timestamp IDs satisfy the same grammar.
- [ ] Resolve a relative custom evidence root against the invocation working
  directory before capture. Test the implicit/explicit literal default
  exception, requiring normalized spelling of the literal default and real
  no-follow `.release-gate`/`runs` directories; custom roots equal to or below
  the source, `.git` entry, absolute per-worktree
  `git rev-parse --git-dir`, or absolute shared
  `git rev-parse --git-common-dir`; inside-to-outside and outside-to-inside
  symlink aliases; nonexistent suffix re-resolution; a safe outside root; an
  ancestor root with a disjoint run directory; and collision with either
  execution clone.
- [ ] Test implicit, relative, and redundant-segment spellings of the literal
  default with neither, one, or both directory components initially missing;
  verify existing component identities plus the literal missing suffix, then
  the full identity after creation. At each component reject tracked and
  untracked POSIX symlinks plus Windows junctions/reparse points targeting a
  source subtree, `.git` entry, per-worktree Git directory, shared Git common
  directory, either clone, an external directory, or the eventual real default
  itself. A symlink alias that reaches the default must not earn the exception.
- [ ] Inject substitutions immediately before and after capture, between
  component creations, after run-directory creation, after clone placement,
  immediately before and after the transition into candidate evaluation,
  before the first configured preparation/check command, and before/after
  finalization. Define that transition as immediately before invariant
  policy/launcher and configured-scope evaluation. Assert stable pinned
  identities, component-by-component no-follow creation, rollback of only
  invocation-created empty scaffolding, exit 3 before the transition, exit 4
  after it, and byte-for-byte unchanged source/index/status for every
  precreation rejection.
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
- [ ] Before the candidate-evaluation transition, test raw/effective config at
  1 MiB and one byte over, patch above 200 MiB, and
  `patch + config + 7,340,032` at/over every 16-200 MiB total boundary. Build
  maximum-output skeletons from actual policy sides/scalars/artifacts and
  reject structures that cannot fit result<=2 MiB, manifest<=4 MiB, or
  trace<=1 MiB. Every infeasible case is exit 3 with no promised result.
- [ ] For success and every early-stop path, semantically verify
  `result.checks` has exactly the effective-config check IDs/modes/severities in
  declaration order. Reject zero, missing, extra, duplicate, or reordered
  items; preparation IDs must not appear there. Verify manifest/result root
  reason arrays are identical.
- [ ] Semantically verify manifest execution cardinality and order against the
  resolved policy: preparation controls first and base/candidate as required,
  then candidate checks or base/candidate differential checks. At every slot
  require exact `control_id`, phase, side, argv, cwd, and environment names;
  retain the same slots as lifecycle-valid skipped executions after every
  scheduling stop.
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
- [ ] On every OS, exercise portable ID/artifact boundary cases and canonical
  evidence-root containment, including native case behavior and symlinks or
  junctions/reparse points where the platform permits them. Cover both default
  path components, linked-worktree `--git-dir` and `--git-common-dir`, redirect
  targets inside/outside protected trees, and checkpoint substitution races.
- [ ] Exercise each platform override and native timeout/process-tree cleanup;
  compare verdict and closed reason-code parity across operating systems. Also
  prove temporary object-directory capture leaves source/common object stores,
  the real index, refs, and status unchanged on linked worktrees.
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
