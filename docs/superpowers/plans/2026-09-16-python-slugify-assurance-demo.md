# Python Slugify Conceptual Diversity Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `python-slugify` demo install, run, inspect, and verify Release Gate 0.7.0 conceptual-diversity assurance in advisory mode.

**Architecture:** A reviewed assurance-policy asset is committed into the generated trusted base beside the deterministic gate policy. The demo invokes `release-gate assure` once per candidate, parses its separate result package, and follows the result's `gate_result_path` when reusing deterministic inspection and oracle grading.

**Tech Stack:** Python 3.12, pytest, Pydantic assurance contracts, YAML policy assets, Git, Release Gate 0.7.0 CLI.

---

## File map

- Create `release-gate/demo/python-slugify/assets/.release-gate-assurance.yaml`: reviewed advisory concept schema, mappings, source hashes, support requirements, uncertainty limit, and assessment limits.
- Modify `release-gate/demo/python-slugify/demo.py`: assurance result parsing, inspection, trusted-policy setup/verification, and assurance-aware automated controls.
- Modify `release-gate/demo/python-slugify/README.md`: executable walkthrough and interpretation guidance.
- Modify `release-gate/tests/test_demo_python_slugify.py`: focused policy, parser, setup-integrity, inspection, orchestration, and documentation tests.
- Modify `release-gate/tests/test_release_metadata.py` only if its public-surface assertions need the demo assurance phrases.
- Update `graphify-out/*` only through `graphify update .` if the repository tracks refreshed graph output.

### Task 1: Add the reviewed assurance policy asset

**Files:**
- Create: `release-gate/demo/python-slugify/assets/.release-gate-assurance.yaml`
- Modify: `release-gate/tests/test_demo_python_slugify.py`

- [ ] **Step 1: Write a failing policy-contract test**

Import `load_policy` from `release_gate.assurance.policy`, add an `ASSURANCE_POLICY` path constant, and assert:

```python
policy = load_policy(ASSURANCE_POLICY.read_bytes())
assert policy.mode == "advisory"
assert policy.concept_schema.schema_id == "python-slugify-behavior"
assert [d.dimension_id for d in policy.concept_schema.dimensions] == [
    "behavior_region"
]
assert {requirement.value for requirement in policy.required_regions} == {
    "transliteration",
    "unicode",
    "boundary",
    "customization",
    "cli_contract",
}
assert all(item.minimum_independent_support == 1 for item in policy.required_regions)
assert policy.maximum_mapping_uncertainty_rate == 0.95
assert len(policy.mappings) == 5
assert {mapping.independence_group for mapping in policy.mappings} == {
    "upstream-test.py"
}
assert {
    next(iter(mapping.sources.values())) for mapping in policy.mappings
} == {"5262916dbabb42b0d63b7c3eaa200aa435e8bb6d888287a048ed649eb29d91b1"}
```

Also assert the five exact `(suite, classname, name, concept)` tuples from the design spec and that every selector uses check `tests-and-coverage` and report `junit`.

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
cd release-gate
.venv/bin/python -m pytest -q tests/test_demo_python_slugify.py::test_demo_assurance_policy_is_reviewed_and_valid
```

Expected: FAIL because `assets/.release-gate-assurance.yaml` does not exist.

- [ ] **Step 3: Add the minimal policy asset**

Create a version-1 YAML policy with:

```yaml
version: 1
mode: advisory
concept_schema:
  schema_id: python-slugify-behavior
  schema_version: "1.0.0"
  dimensions:
    - dimension_id: behavior_region
      name: Behavior region
      definition: Reviewed behavior represented by a passing candidate-side case.
      values: [transliteration, unicode, boundary, customization, cli_contract]
```

Add the five exact selectors from the spec. Each mapping sets one
`behavior_region`, uses `sources.test.py` with the reviewed digest, and sets
`independence_group: upstream-test.py`. Add one requirement per value with
`minimum_independent_support: 1`, set
`maximum_mapping_uncertainty_rate: 0.95`, and use explicit bounded limits no
larger than the schema defaults.

- [ ] **Step 4: Run the focused policy test and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit the policy slice**

```bash
git add release-gate/demo/python-slugify/assets/.release-gate-assurance.yaml release-gate/tests/test_demo_python_slugify.py
git commit -m "feat(demo): add python-slugify assurance policy"
```

### Task 2: Parse and inspect assurance results

**Files:**
- Modify: `release-gate/demo/python-slugify/demo.py`
- Modify: `release-gate/tests/test_demo_python_slugify.py`

- [ ] **Step 1: Write failing parser and malformed-result tests**

Add a complete assurance fixture with version 1, mode, gate verdict,
disposition, assessment status, evidence-sufficiency flag, reason codes,
coverage, unmet requirements, and absolute `gate_result_path`.
Assert `read_assurance_summary()` returns typed fields. Parameterize malformed
values for unsupported version/mode/verdict/disposition/status, missing linked
result, non-boolean sufficiency, non-object coverage, and non-array unmet
requirements. Assert a relative `gate_result_path` is rejected.

- [ ] **Step 2: Run parser tests and verify RED**

```bash
cd release-gate
.venv/bin/python -m pytest -q \
  tests/test_demo_python_slugify.py::test_assurance_summary_reads_demo_fields \
  tests/test_demo_python_slugify.py::test_assurance_summary_rejects_invalid_results
```

Expected: FAIL because the assurance parser does not exist.

- [ ] **Step 3: Implement the minimal `AssuranceSummary` contract**

Add a frozen/slotted dataclass and `read_assurance_summary(path)` beside the
existing deterministic parser. Reuse small JSON validation helpers where their
error text remains clear. Accept only:

```python
mode in {"advisory", "enforce"}
gate_verdict in {"PASS", "FAIL", "NEEDS_HUMAN"}
disposition in {"PASS", "FAIL", "NEEDS_HUMAN"}
assessment_status in {"COMPLETE", "UNAVAILABLE", "NOT_EVALUATED"}
```

Keep `coverage` as `dict[str, Any] | None` and unmet requirements as a tuple of
mappings; the demo prints diagnostics but does not recreate the Release Gate
schema.

- [ ] **Step 4: Run parser tests and verify GREEN**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Write failing inspection and CLI parser tests**

Assert the command parser accepts:

```text
inspect-assurance --result assurance-result.json
```

Create a temporary assurance package containing `result.json` and
`manifest.json`, plus a linked deterministic package. Call
`inspect_assurance_result()` and assert output includes mode, gate verdict,
disposition, assessment status, evidence sufficiency, uncertainty, unmet
requirements, manifest, and linked gate result. Assert the returned summary
contains the exact linked path.

- [ ] **Step 6: Run inspection tests and verify RED**

```bash
cd release-gate
.venv/bin/python -m pytest -q \
  tests/test_demo_python_slugify.py::test_parser_exposes_simplified_demo_commands \
  tests/test_demo_python_slugify.py::test_inspect_assurance_prints_decision_and_link
```

Expected: FAIL because the command and inspector do not exist.

- [ ] **Step 7: Implement inspection and command dispatch**

Add `inspect-assurance` with required `--result`. Resolve the path strictly,
reject `.incomplete` or a missing fixed sibling
`resolved.parent / "manifest.json"`, print the fields above, and print
`mapping uncertainty: unavailable` when coverage is `None`. Assurance results
do not contain a `manifest_path` field. Add the command to `main()` without
changing `inspect` or `grade`.

- [ ] **Step 8: Run inspection tests and verify GREEN**

Run the Step 6 command. Expected: PASS.

- [ ] **Step 9: Commit result inspection**

```bash
git add release-gate/demo/python-slugify/demo.py release-gate/tests/test_demo_python_slugify.py
git commit -m "feat(demo): inspect conceptual assurance results"
```

### Task 3: Install and validate both trusted policies

**Files:**
- Modify: `release-gate/demo/python-slugify/demo.py`
- Modify: `release-gate/tests/test_demo_python_slugify.py`

- [ ] **Step 1: Write failing trusted-base tests**

Extend the asset inventory test to require `.release-gate-assurance.yaml`.
Extend `test_trusted_base_validation_checks_origin_parent_and_policy` so its
base commit includes both policy assets. After the valid assertion, alter the
committed assurance policy independently and assert `_verify_repository()`
raises `DemoError` mentioning the assurance policy.

Add a setup orchestration test with monkeypatched `_run`, `_git`, environment
creation, and upstream verification. Record Git calls and assert setup stages
both `.release-gate.yaml` and `.release-gate-assurance.yaml` before the trusted
base tag is created.

- [ ] **Step 2: Run trusted-base tests and verify RED**

```bash
cd release-gate
.venv/bin/python -m pytest -q \
  tests/test_demo_python_slugify.py::test_committed_demo_assets_and_windows_guidance_are_self_contained \
  tests/test_demo_python_slugify.py::test_trusted_base_validation_checks_origin_parent_and_policy \
  tests/test_demo_python_slugify.py::test_setup_commits_both_reviewed_policies
```

Expected: FAIL because setup and validation know only the deterministic policy.

- [ ] **Step 3: Implement assurance-policy installation**

During setup, copy the assurance asset to
`REPOSITORY / ".release-gate-assurance.yaml"` without using candidate-generated
content. Stage it in the same reviewed-policy commit as `.release-gate.yaml`
and `.gitignore`. Update `_verify_repository()` to read
`BASE_REF:.release-gate-assurance.yaml` and compare it byte-for-byte with the
asset. Keep the existing base-parent and origin checks unchanged.

- [ ] **Step 4: Run trusted-base tests and verify GREEN**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit trusted-policy setup**

```bash
git add release-gate/demo/python-slugify/demo.py release-gate/tests/test_demo_python_slugify.py
git commit -m "feat(demo): install trusted assurance policy"
```

### Task 4: Run assurance in all automated control scenarios

**Files:**
- Modify: `release-gate/demo/python-slugify/demo.py`
- Modify: `release-gate/tests/test_demo_python_slugify.py`

- [ ] **Step 1: Write a failing three-scenario orchestration test**

Monkeypatch setup/control/reset/oracle-facing functions and `_run`. Return
synthetic assurance CLI stdout containing exactly:

```text
GATE_VERDICT: <verdict>
ASSURANCE_DISPOSITION: <disposition>
ASSURANCE_MODE: advisory
ASSESSMENT_STATUS: <status>
RESULT: <absolute assurance result path>
```

Record argv and assert each scenario invokes `assure`, `--base BASE_REF`, the
configured output directory, and a unique run ID. Assert the PASS fixture is
`COMPLETE`, sufficient, has no unmet requirements, and has uncertainty at most
`0.95`. Assert FAIL and NEEDS_HUMAN fixtures are `NOT_EVALUATED` and preserve
verdict precedence. Assert grading receives each assurance result's exact
`gate_result_path`.

- [ ] **Step 2: Run orchestration test and verify RED**

```bash
cd release-gate
.venv/bin/python -m pytest -q tests/test_demo_python_slugify.py::test_verify_runs_assurance_for_all_controls
```

Expected: FAIL because `verify()` still invokes `run` and treats `RESULT` as a
deterministic result.

- [ ] **Step 3: Implement assurance-aware verification**

Replace only the gate invocation in `verify()` with `assure`. Parse the
`RESULT:` path as an assurance result, call `inspect_assurance_result()`, check
the scenario table from the spec, and call `grade()` with
`Path(summary.gate_result_path)`. For PASS, require complete/sufficient/no
unmet regions and numeric `coverage["mapping_uncertainty_rate"] <= 0.95`. For
non-passing verdicts, require `NOT_EVALUATED` and do not claim coverage.

Change the completion line to mention deterministic and assurance outcomes,
for example:

```text
verify: gate verdicts and assurance dispositions matched expectations
```

- [ ] **Step 4: Run orchestration test and verify GREEN**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Run the complete focused demo test module**

```bash
cd release-gate
.venv/bin/python -m pytest -q tests/test_demo_python_slugify.py
```

Expected: all tests pass.

- [ ] **Step 6: Commit assurance orchestration**

```bash
git add release-gate/demo/python-slugify/demo.py release-gate/tests/test_demo_python_slugify.py
git commit -m "feat(demo): verify conceptual assurance controls"
```

### Task 5: Update the executable walkthrough

**Files:**
- Modify: `release-gate/demo/python-slugify/README.md`
- Modify: `release-gate/tests/test_demo_python_slugify.py`
- Modify: `release-gate/tests/test_release_metadata.py` if required by existing metadata checks

- [ ] **Step 1: Add failing documentation assertions**

Require the README to include:

```text
.release-gate-assurance.yaml
release-gate assure
GATE_VERDICT
ASSURANCE_DISPOSITION
ASSESSMENT_STATUS
inspect-assurance
mapping uncertainty
independence group
advisory
enforce
```

Also assert direct Windows and macOS commands use `assure --base
release-gate-demo-base`, and that the README says CI enforcement consumes the
`assure` exit code after a reviewed base-policy change.

- [ ] **Step 2: Run documentation tests and verify RED**

```bash
cd release-gate
.venv/bin/python -m pytest -q \
  tests/test_demo_python_slugify.py::test_committed_demo_assets_and_windows_guidance_are_self_contained \
  tests/test_release_metadata.py::test_assurance_behavior_is_documented_across_public_surfaces
```

Expected: FAIL on missing demo walkthrough phrases or commands.

- [ ] **Step 3: Update the README**

Change interactive and direct CLI paths from `run` to `assure`. Explain that
the single invocation executes the deterministic gate first and assesses only
a passing gate. Direct users to the assurance `RESULT` and the new
`inspect-assurance` command. Add a table for the three scenario outcomes.

Document the five reviewed regions, exact-case/source-hash trust boundary,
shared conservative independence group, `0.95` uncertainty ceiling, and the
unmapped majority. State that advisory findings do not alter a PASS and that
enforcement requires a reviewed change to the base policy plus CI adoption of
the `assure` exit code. Preserve the hidden-oracle limitations.

- [ ] **Step 4: Run documentation tests and verify GREEN**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit documentation**

```bash
git add release-gate/demo/python-slugify/README.md release-gate/tests/test_demo_python_slugify.py release-gate/tests/test_release_metadata.py
git commit -m "docs(demo): add conceptual diversity walkthrough"
```

### Task 6: Validate, refresh repository metadata, and integrate

**Files:**
- Modify only files required by formatting or `graphify update .`.

- [ ] **Step 1: Run focused functional tests**

```bash
cd release-gate
.venv/bin/python -m pytest -q \
  tests/test_demo_python_slugify.py \
  tests/test_assurance.py \
  tests/test_release_metadata.py \
  tests/test_sync_release_version.py
```

Expected: all tests pass.

- [ ] **Step 2: Run formatting, lint, and typing checks**

```bash
cd release-gate
.venv/bin/ruff format --check demo/python-slugify/demo.py tests/test_demo_python_slugify.py
.venv/bin/ruff check --no-cache demo/python-slugify/demo.py tests/test_demo_python_slugify.py
.venv/bin/mypy src demo/python-slugify/demo.py
```

Expected: all commands exit 0. If formatting is needed, run Ruff format, review
the diff, and rerun these checks.

- [ ] **Step 3: Run version synchronization and whitespace checks**

```bash
cd release-gate
.venv/bin/python scripts/sync_release_version.py --check
cd ..
git diff --check -- release-gate docs/superpowers
```

Expected: Release Gate remains synchronized at 0.7.0 and the scoped patch has
no whitespace errors.

- [ ] **Step 4: Run the live executable verification when network access is available**

```bash
cd release-gate/demo/python-slugify
# Run setup when workbench/ does not exist:
uv run --python 3.12 --no-project python demo.py setup
# If workbench/ already exists, run reset instead of setup:
# uv run --python 3.12 --no-project python demo.py reset
uv run --python 3.12 --no-project python demo.py verify
```

Expected final line:

```text
verify: gate verdicts and assurance dispositions matched expectations
```

If cloning/package installation is unavailable, record this check as skipped
with the failing network operation; do not report it as passed.

- [ ] **Step 5: Refresh Graphify after code changes**

```bash
cd /Users/jerryshao/Documents/projects/IBM/ai/blindspot-remediation
graphify update .
```

Expected: graph outputs rebuild without an extraction failure.

- [ ] **Step 6: Review the final diff and commit any verification-driven edits**

```bash
git status --short
git diff --stat
git diff -- release-gate/demo/python-slugify release-gate/tests/test_demo_python_slugify.py release-gate/tests/test_release_metadata.py
```

Exclude the pre-existing staged `A5-pipeline-evaluation/Enhanced-A3*.txt`
files from every commit.

- [ ] **Step 7: Fast-forward local main after all checks pass**

From the feature branch, commit any remaining in-scope changes. Then:

```bash
git switch main
git merge --ff-only codex/python-slugify-assurance-demo
```

Confirm `main` points at the implementation commit and the Enhanced-A3 files
remain uncommitted.
