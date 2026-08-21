# Release Gate Demo Private Campaign Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `python-slugify` demo persist hidden-oracle grades and generate a local private campaign report that can identify false releases with explicit denominators and Wilson bounds.

**Architecture:** Keep the reusable `release-gate` CLI, portable skill, result schema, and public observability unchanged. Add a focused demo-local `campaign_report.py` module for validated records, aggregation, HTML rendering, and safe publication; keep candidate reconstruction and oracle orchestration in `demo.py`, which will grade the exact recorded patch rather than the mutable workbench.

**Tech Stack:** Python 3.11 standard library, Git subprocesses, pytest, Ruff, existing `uv` development environment.

---

## Scope and File Map

- Create `release-gate/demo/python-slugify/campaign_report.py`
  - Owns campaign metadata/record validation, Wilson intervals, cohort aggregation,
    deterministic JSON, escaped HTML, idempotent records, and atomic publication.
- Modify `release-gate/demo/python-slugify/demo.py`
  - Owns CLI parsing, complete Release Gate result identity parsing, recorded-candidate
    reconstruction, hidden-oracle execution, automatic campaign recording, and
    `campaign-report` dispatch.
- Create `release-gate/tests/test_demo_campaign_report.py`
  - Unit-tests the pure reporting and filesystem behaviors without cloning the
    external demo repository or installing packages.
- Modify `release-gate/tests/test_demo_python_slugify.py`
  - Tests CLI integration, candidate binding, grading orchestration, and control
    exclusion.
- Modify `release-gate/demo/python-slugify/.gitignore`
  - Ignores the generated private campaign directory.
- Modify `release-gate/demo/python-slugify/README.md`
  - Documents private grading/reporting, denominators, controls/re-gates, privacy,
    and Windows/macOS commands.
- Do not modify `release-gate/src/release_gate/`, schemas, public observability,
  `release-gate/skills/release-gate/`, or skill archives.

## Fixed v1 Shapes

Use these shapes consistently in tests and implementation so later tasks do not
invent incompatible field names.

One record:

```json
{
  "version": 1,
  "run_id": "x1-run-01",
  "run_kind": "trial",
  "gate": {
    "verdict": "PASS",
    "finished_at": "2026-08-20T12:00:00Z",
    "duration_ms": 1200,
    "base_commit": "<40-hex>",
    "candidate_tree": "<40-hex>",
    "patch_sha256": "<64-hex>",
    "config_sha256": "<64-hex>",
    "result_sha256": "<64-hex>"
  },
  "oracle": {
    "truth": true,
    "classification": "good_pass",
    "source_sha256": "<64-hex>",
    "graded_at": "2026-08-20T12:05:00Z"
  },
  "ai": {
    "wall_seconds": 103.0,
    "usage_value": 16.6,
    "usage_unit": "AIC",
    "model": "claude-haiku-4.5",
    "human_step": "none"
  }
}
```

The aggregate JSON top level:

```json
{
  "version": 1,
  "generation_id": "<64-hex>",
  "generated_at": "<latest-record-graded-at-or-null>",
  "record_count": 1,
  "run_kind_counts": {"trial": 1, "re-gate": 0, "control": 0},
  "primary": {
    "attempts": 1,
    "oracle_valid": 1,
    "oracle_errors": 0,
    "classification_counts": {
      "good_pass": 1,
      "FALSE_RELEASE": 0,
      "FALSE_BLOCK": 0,
      "good_catch": 0,
      "escalated": 0
    },
    "metrics": {},
    "wall_time": {},
    "usage_by_unit": {},
    "model_counts": {},
    "human_step_counts": {}
  },
  "records": []
}
```

Every metric object uses:

```json
{
  "numerator": 0,
  "denominator": 1,
  "estimate": 0.0,
  "lower_bound": 0.0,
  "upper_bound": 0.7934506856227626,
  "confidence_level": 0.95,
  "method": "wilson"
}
```

---

### Task 1: Campaign module and Wilson interval

**Files:**
- Create: `release-gate/demo/python-slugify/campaign_report.py`
- Create: `release-gate/tests/test_demo_campaign_report.py`

- [ ] **Step 1: Write a module loader and failing Wilson tests**

Add this loader and tests to `release-gate/tests/test_demo_campaign_report.py`:

```python
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODULE = ROOT / "demo" / "python-slugify" / "campaign_report.py"


def load_campaign():
    spec = importlib.util.spec_from_file_location("python_slugify_campaign", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("trials", "rounded_upper"),
    [(5, 43), (10, 28), (20, 16), (30, 11), (100, 4)],
)
def test_zero_event_wilson_bounds_match_documented_table(
    trials: int, rounded_upper: int
) -> None:
    campaign = load_campaign()
    metric = campaign.wilson_interval(events=0, trials=trials)
    assert metric["numerator"] == 0
    assert metric["denominator"] == trials
    assert round(metric["upper_bound"] * 100) == rounded_upper
    assert metric["confidence_level"] == 0.95
    assert metric["method"] == "wilson"


def test_wilson_zero_denominator_is_unknown_and_invalid_counts_are_rejected() -> None:
    campaign = load_campaign()
    assert campaign.wilson_interval(events=0, trials=0) == {
        "numerator": 0,
        "denominator": 0,
        "estimate": None,
        "lower_bound": None,
        "upper_bound": None,
        "confidence_level": 0.95,
        "method": "wilson",
    }
    with pytest.raises(ValueError, match="events"):
        campaign.wilson_interval(events=2, trials=1)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
cd release-gate
uv run pytest tests/test_demo_campaign_report.py -q
```

Expected: FAIL because `demo/python-slugify/campaign_report.py` does not exist.

- [ ] **Step 3: Implement the minimal Wilson API**

Create `campaign_report.py` with:

```python
from __future__ import annotations

from math import sqrt
from statistics import NormalDist
from typing import Any

CONFIDENCE_LEVEL = 0.95
RUN_KINDS = ("trial", "re-gate", "control")
CLASSIFICATIONS = (
    "good_pass",
    "FALSE_RELEASE",
    "FALSE_BLOCK",
    "good_catch",
    "escalated",
    "oracle_error",
)


class CampaignError(RuntimeError):
    """An expected private-campaign validation or publication error."""


def wilson_interval(
    *, events: int, trials: int, confidence_level: float = CONFIDENCE_LEVEL
) -> dict[str, Any]:
    if trials < 0:
        raise ValueError("trials cannot be negative")
    if events < 0 or events > trials:
        raise ValueError("events must be between zero and trials")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence level must be between zero and one")
    result: dict[str, Any] = {
        "numerator": events,
        "denominator": trials,
        "estimate": None,
        "lower_bound": None,
        "upper_bound": None,
        "confidence_level": confidence_level,
        "method": "wilson",
    }
    if trials == 0:
        return result
    proportion = events / trials
    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence_level) / 2.0)
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    center = (proportion + z_squared / (2.0 * trials)) / denominator
    margin = (
        z
        * sqrt(
            proportion * (1.0 - proportion) / trials
            + z_squared / (4.0 * trials * trials)
        )
        / denominator
    )
    result.update(
        estimate=proportion,
        lower_bound=max(0.0, center - margin),
        upper_bound=min(1.0, center + margin),
    )
    return result
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the same pytest command. Expected: `6 passed`.

- [ ] **Step 5: Run Ruff on the new files**

```bash
cd release-gate
uv run ruff check demo/python-slugify/campaign_report.py tests/test_demo_campaign_report.py
```

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add release-gate/demo/python-slugify/campaign_report.py \
  release-gate/tests/test_demo_campaign_report.py
git commit -m "feat(release-gate): add demo campaign statistics"
```

---

### Task 2: Record validation and primary-cohort aggregation

**Files:**
- Modify: `release-gate/demo/python-slugify/campaign_report.py`
- Modify: `release-gate/tests/test_demo_campaign_report.py`

- [ ] **Step 1: Write failing tests for record semantics and denominators**

Add a `record()` test helper that returns the fixed v1 shape and a test with:

- one `trial/good_pass`;
- one `trial/FALSE_RELEASE`;
- one `trial/oracle_error`;
- one `re-gate/good_pass`;
- one `control/good_catch`.

Assert the aggregate has five total records, three primary attempts, two
oracle-valid primary trials, one primary oracle error, `1/2` false releases per
total, and `1/2` false releases given `PASS`. Also assert re-gate and control
records remain visible but do not affect primary metrics.

Use this core assertion block:

```python
data = campaign.build_campaign_data(records)
assert data["record_count"] == 5
assert data["run_kind_counts"] == {"trial": 3, "re-gate": 1, "control": 1}
primary = data["primary"]
assert primary["attempts"] == 3
assert primary["oracle_valid"] == 2
assert primary["oracle_errors"] == 1
assert primary["classification_counts"]["FALSE_RELEASE"] == 1
assert primary["metrics"]["false_release_per_total"]["numerator"] == 1
assert primary["metrics"]["false_release_per_total"]["denominator"] == 2
assert primary["metrics"]["false_release_given_pass"]["denominator"] == 2
```

Add separate tests that reject:

- unsupported `version`, `run_kind`, verdict, or classification;
- inconsistent truth/classification, such as `PASS + false + good_pass`;
- non-hex digests or invalid numeric metadata.

Assert separately that changing free-form `human_step` never changes the
structured `run_kind` or primary-cohort membership. Same-run metadata mutation
is a storage conflict covered in Task 4; a single record cannot infer an
operator's intent from descriptive text.

- [ ] **Step 2: Run the focused test and verify RED**

```bash
cd release-gate
uv run pytest tests/test_demo_campaign_report.py -q
```

Expected: FAIL because `build_campaign_data` and record validation are absent.

- [ ] **Step 3: Implement exact validation and aggregation**

Add these public functions:

```python
def validate_record(value: object) -> dict[str, Any]: ...
def build_campaign_data(records: list[dict[str, Any]]) -> dict[str, Any]: ...
```

Implementation requirements:

- Require exactly the documented top-level and nested keys; reject booleans as
  numeric values because `bool` subclasses `int`.
- Require portable run IDs, RFC-3339-shaped timestamps already emitted by the
  gate/demo, 40- or 64-character lowercase Git IDs, and 64-character lowercase
  SHA-256 values.
- Enforce the classification matrix:

```python
EXPECTED = {
    ("PASS", True): "good_pass",
    ("PASS", False): "FALSE_RELEASE",
    ("FAIL", True): "FALSE_BLOCK",
    ("FAIL", False): "good_catch",
    ("NEEDS_HUMAN", True): "escalated",
    ("NEEDS_HUMAN", False): "escalated",
}
```

- Permit `oracle_error` only with `truth is None`; other classifications require
  Boolean truth.
- Sort validated records by `(gate.finished_at, run_id)`.
- Define primary records strictly as `run_kind == "trial"`.
- Exclude `oracle_error` from correctness denominators.
- Compute `automation_coverage`, `false_release_per_total`,
  `false_release_given_pass`, `false_block_per_total`, and `escalation_rate`
  with explicit Wilson metric objects.
- Use only known wall times/usages for numeric summaries and always include
  `known_count` and `unknown_count`; group usage by exact unit.
- Build categorical model/human-step counts from non-null primary values.
- Compute `generation_id` as SHA-256 of compact, sorted-key UTF-8 JSON for the
  ordered validated records. Set deterministic `generated_at` to the latest
  `oracle.graded_at`, or `None` for no records.

- [ ] **Step 4: Verify GREEN and run the entire campaign module test file**

```bash
cd release-gate
uv run pytest tests/test_demo_campaign_report.py -q
uv run ruff check demo/python-slugify/campaign_report.py tests/test_demo_campaign_report.py
```

Expected: all tests pass and Ruff exits 0.

- [ ] **Step 5: Commit**

```bash
git add release-gate/demo/python-slugify/campaign_report.py \
  release-gate/tests/test_demo_campaign_report.py
git commit -m "feat(release-gate): aggregate private demo campaign outcomes"
```

---

### Task 3: Deterministic escaped HTML report

**Files:**
- Modify: `release-gate/demo/python-slugify/campaign_report.py`
- Modify: `release-gate/tests/test_demo_campaign_report.py`

- [ ] **Step 1: Write failing HTML tests**

Add a record whose model is `<script>alert(1)</script>` and human step is
`review & fix`. Assert:

```python
html = campaign.render_campaign_html(campaign.build_campaign_data([value]))
assert "<script>alert(1)</script>" not in html
assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
assert "review &amp; fix" in html
assert data["generation_id"] in html
assert "False releases given PASS" in html
assert "Repeated X1 trials measure X1 repeatability" in html
assert "https://" not in html and "http://" not in html
```

Also render the same document twice and assert byte-for-byte equality.

- [ ] **Step 2: Run the focused tests and verify RED**

Expected: FAIL because `render_campaign_html` does not exist.

- [ ] **Step 3: Implement a self-contained renderer**

Add:

```python
def render_campaign_html(data: dict[str, Any]) -> str: ...
```

Requirements:

- Use `html.escape(..., quote=True)` for every dynamic value.
- Embed only static CSS; no scripts, external fonts, images, or network URLs.
- Show generation ID, total/run-kind counts, classification count/denominator,
  every Wilson numerator/denominator/estimate/bounds, known/unknown timing and
  usage denominators, and an ordered record table.
- Put `FALSE_RELEASE` in a visually prominent but accessible row.
- Include the five limitations from the design verbatim in a visible section.
- Do not display oracle test names, output, source paths, or error detail.

- [ ] **Step 4: Run tests and Ruff**

```bash
cd release-gate
uv run pytest tests/test_demo_campaign_report.py -q
uv run ruff check demo/python-slugify/campaign_report.py tests/test_demo_campaign_report.py
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add release-gate/demo/python-slugify/campaign_report.py \
  release-gate/tests/test_demo_campaign_report.py
git commit -m "feat(release-gate): render private demo campaign report"
```

---

### Task 4: Private record store and atomic report publication

**Files:**
- Modify: `release-gate/demo/python-slugify/campaign_report.py`
- Modify: `release-gate/tests/test_demo_campaign_report.py`

- [ ] **Step 1: Write failing storage tests**

Cover these behaviors with temporary directories:

1. First `record_and_refresh(root, record)` creates:
   `records/<run-id>.json`, `campaign-v1.json`, and `index.html`.
2. Repeating the identical record preserves the original record bytes and does
   not increment `record_count`.
3. Reusing a run ID with different metadata raises `CampaignError` and preserves
   all three published files byte-for-byte.
4. `refresh(root)` fails closed on malformed/unsupported JSON and leaves prior
   aggregates untouched.
5. Existing symlinks for root, records, a record, JSON, or HTML are refused; the
   symlink target remains unchanged.
6. Injected aggregate publication failure leaves the durable record in place
   and permits a later `refresh(root)` to recover.
7. A held global campaign lock makes a concurrent `record_and_refresh` or
   `refresh` fail without modifying records or aggregates. A two-thread barrier
   test proves conflicting same-run writers cannot both publish.

Use monkeypatchable `_atomic_write(path, payload)` for the failure-injection
test. On Windows, skip symlink cases when the test account cannot create one.

- [ ] **Step 2: Run the storage tests and verify RED**

Expected: FAIL because the storage API is absent.

- [ ] **Step 3: Implement the storage API**

Add:

```python
@dataclass(frozen=True, slots=True)
class CampaignPaths:
    record: Path | None
    data: Path
    report: Path


def record_and_refresh(root: Path, record: dict[str, Any]) -> CampaignPaths: ...
def refresh(root: Path) -> CampaignPaths: ...
```

Implementation requirements:

- Create `root` and `root/records` with mode `0o700` where supported.
- Serialize every record/report mutation with a root-local `.campaign.lock`
  acquired by `os.open(..., O_CREAT | O_EXCL | O_WRONLY, 0o600)`. Hold it from
  the first collision scan through final aggregate publication; release it in
  `finally`. An existing lock fails closed as "campaign update already in
  progress" and is never auto-broken, so a crashed writer cannot be mistaken
  for safe concurrency.
- Reject symlink/reparse entries before reading or writing. Recheck the selected
  entry immediately before replacement; do not follow an existing link.
- Encode JSON with sorted keys, indentation two, UTF-8, and a final newline.
- Write unique sibling temporary files using `os.open` with create-exclusive
  flags and `0o600`, flush and `os.fsync`, then publish with `os.replace`.
- Publish a new record before refreshing aggregates.
- Publish or compare a same-run record only while holding the global lock. The
  final `os.replace` is therefore atomic and mutually exclusive; never use an
  unlocked check-then-replace sequence.
- Compare an existing record to the complete canonical candidate record except
  that idempotency uses the already stored `oracle.graded_at`; identical stable
  content and metadata returns the stored record rather than generating a new
  timestamp.
- Load every ordinary `*.json` record, validate all of them, and reject rather
  than skip malformed, unsupported, duplicate/casefold-colliding, or symlinked
  records.
- Build both aggregate payloads before replacing either. Publish JSON first and
  HTML second; both carry the same generation ID. If HTML publication fails,
  surface `CampaignError` and allow the next `refresh` to replace both. Never
  alter a durable record during aggregate recovery.
- Return absolute paths without opening the browser.

- [ ] **Step 4: Verify GREEN and inspect permissions on POSIX**

```bash
cd release-gate
uv run pytest tests/test_demo_campaign_report.py -q
uv run ruff check demo/python-slugify/campaign_report.py tests/test_demo_campaign_report.py
```

Expected: all tests pass. The permissions test should assert no group/other bits
for newly created private directories/files on POSIX.

- [ ] **Step 5: Commit**

```bash
git add release-gate/demo/python-slugify/campaign_report.py \
  release-gate/tests/test_demo_campaign_report.py
git commit -m "feat(release-gate): persist private demo campaign records"
```

---

### Task 5: Grade CLI metadata and complete result identity

**Files:**
- Modify: `release-gate/demo/python-slugify/demo.py`
- Modify: `release-gate/tests/test_demo_python_slugify.py`

- [ ] **Step 1: Write failing parser and result-identity tests**

Extend `test_parser_exposes_documented_commands` to assert:

```python
parsed = parser.parse_args(
    [
        "grade", "--result", "result.json", "--run-kind", "re-gate",
        "--wall-seconds", "103", "--usage-value", "16.6",
        "--usage-unit", "AIC", "--model", "model-x",
        "--human-step", "dependency install",
    ]
)
assert parsed.run_kind == "re-gate"
assert parsed.wall_seconds == 103.0
assert parser.parse_args(["campaign-report"]).command == "campaign-report"
```

Extend the result fixture with `finished_at`, `duration_ms`, `base_commit`,
`candidate_tree`, `patch_sha256`, and `config_sha256`; assert all are present on
`ResultSummary`. Add negative cases for absent/invalid fields.

Add metadata validation tests for:

- usage value without unit and unit without value;
- negative, NaN, or infinite numbers;
- empty/overlong/control-character model, unit, or human-step values.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
cd release-gate
uv run pytest tests/test_demo_python_slugify.py -q
```

Expected: FAIL because the arguments and complete result fields are absent.

- [ ] **Step 3: Implement parser and model changes**

In `demo.py`:

- Add constants `PRIVATE_CAMPAIGN = DEMO_ROOT / "private-campaign"` and bounded
  metadata limits.
- Extend `ResultSummary` with the fixed gate identity fields.
- Split `inspect_result` into a side-effect-free `load_result(path)` returning
  `(resolved_path, result_bytes, summary)` plus the existing printing wrapper,
  so result hashing uses the exact bytes already parsed.
- Add grade arguments from the spec, with `choices=("trial", "re-gate",
  "control")` and default `trial`.
- Add a `campaign-report` subparser with no mutation/oracle options.
- Add `CampaignMetadata` construction/validation before any oracle execution.
- Dynamically load the adjacent `campaign_report.py` in the existing
  `load_driver` test pattern, or add the demo directory to `sys.path` only while
  executing the test module. Do not move reporting code into the installable
  `release_gate` package.

- [ ] **Step 4: Run tests and Ruff**

```bash
cd release-gate
uv run pytest tests/test_demo_python_slugify.py -q
uv run ruff check demo/python-slugify/demo.py tests/test_demo_python_slugify.py
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add release-gate/demo/python-slugify/demo.py \
  release-gate/tests/test_demo_python_slugify.py
git commit -m "feat(release-gate): accept demo campaign metadata"
```

---

### Task 6: Reconstruct and grade the exact recorded candidate

**Files:**
- Modify: `release-gate/demo/python-slugify/demo.py`
- Modify: `release-gate/tests/test_demo_python_slugify.py`

- [ ] **Step 1: Write failing reconstruction tests**

Create a temporary local Git repository with a base commit and candidate changes.
Generate the evidence patch exactly as the gate does:

```bash
git diff-tree --no-commit-id --binary --full-index --no-color \
  --no-ext-diff --find-renames -r -p <base-tree> <candidate-tree>
```

Write a matching `result.json`, `manifest.json`, and `candidate.patch`. Reset or
mutate the source worktree after evidence creation, then call the wished-for
`reconstruct_oracle_candidate(result_path, summary)` context manager. Assert the
fresh candidate contains the recorded change and its `git write-tree` equals
`summary.candidate_tree`.

Add tests that reject before oracle execution when:

- candidate patch is missing or its hash mismatches;
- base commit is absent from the trusted workbench repository;
- patch application fails;
- reconstructed candidate tree differs;
- result or evidence directory is symlink/reparse redirected;
- manifest is missing or `.incomplete` exists.

Add a tamper-evidence test that first creates a valid package with the existing
`release_gate.evidence.EvidenceRun` test helper/pattern, then changes an
inventoried artifact byte. Assert grading calls `release_gate.evidence.verify_run`
and rejects the package before reading the patch or invoking the oracle.

- [ ] **Step 2: Run the focused reconstruction tests and verify RED**

Expected: FAIL because recorded-candidate reconstruction does not exist.

- [ ] **Step 3: Implement a disposable reconstruction context manager**

Add an `@contextmanager` that:

1. Checks `_verify_repository()` and refuses a symlink/reparse evidence root.
2. Calls `release_gate.evidence.verify_run(result_path.parent)` before trusting
   any result, manifest, patch, inventory, size, timestamp, or digest. Translate
   `EvidenceError` to a `DemoError`; do not implement a weaker second verifier.
3. Reads the now-verified `candidate.patch` once and additionally requires its
   SHA-256 to equal the parsed `result.json.patch_sha256`.
4. Creates a unique owner-only direct child under `WORKBENCH`.
5. Runs local Git clone with `-c protocol.file.allow=always`, `--no-hardlinks`,
   `--no-checkout`, and `--quiet`; no network URL is used.
6. Checks out `summary.base_commit` detached and forced.
7. Applies bytes through stdin with `git apply --binary --index
   --whitespace=nowarn -`.
8. Runs `git write-tree` and requires exact `summary.candidate_tree`.
9. Yields the reconstructed repository path.
10. Removes the owned temporary root in `finally`, using the existing owned-path
   guard generalized to unique direct children of `WORKBENCH`.

Do not use or modify the mutable main candidate after reconstruction begins.

- [ ] **Step 4: Refactor oracle execution to accept the reconstructed repository**

Replace `_oracle_truth()` with:

```python
@dataclass(frozen=True, slots=True)
class OracleAssessment:
    truth: bool | None
    error: bool


def _oracle_assessment(repository: Path, environment: Path) -> OracleAssessment:
    ...
```

Compute `oracle_source_sha256` before setup from the complete oracle source set:
recursively enumerate ordinary non-symlink files under `ORACLE`, sort by relative
POSIX path, and hash an unambiguous length-prefixed sequence of each UTF-8 path
and raw file bytes. Reject an empty, unreadable, or redirected source set rather
than producing a record without a trustworthy oracle identity.

Return `truth=True` for pytest exit
0, `truth=False` for exit 1, and `truth=None, error=True` for setup/execution
failures after reconstruction. Do not store stdout/stderr or error text in the
campaign record. A missing/unreadable oracle source prevents recording because
the oracle identity cannot be established.

- [ ] **Step 5: Run focused tests and existing demo tests**

```bash
cd release-gate
uv run pytest tests/test_demo_python_slugify.py -q
uv run ruff check demo/python-slugify/demo.py tests/test_demo_python_slugify.py
```

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add release-gate/demo/python-slugify/demo.py \
  release-gate/tests/test_demo_python_slugify.py
git commit -m "feat(release-gate): bind demo oracle to recorded candidate"
```

---

### Task 7: Automatic grade recording and report regeneration

**Files:**
- Modify: `release-gate/demo/python-slugify/demo.py`
- Modify: `release-gate/tests/test_demo_python_slugify.py`
- Modify: `release-gate/tests/test_demo_campaign_report.py`

- [ ] **Step 1: Write failing end-to-end orchestration tests**

Use temporary evidence and monkeypatched oracle/reconstruction boundaries to
assert:

1. `PASS + oracle false` writes `FALSE_RELEASE` and aggregate numerator `1`.
2. `PASS + oracle true` writes `good_pass`.
3. Oracle error writes `oracle_error`, prints all three campaign paths, refreshes
   the report, and makes `main()` return non-zero.
4. Calling grade twice with identical identity/metadata leaves one record.
5. Calling grade with the same run ID but changed metadata returns non-zero and
   preserves existing outputs.
6. `campaign-report` rebuilds deleted aggregate outputs without calling the gate
   or oracle.
7. `verify()` calls the grading helper with `record=False` and creates no private
   record.

Assert stdout ordering keeps the existing truth/classification lines before the
three `CAMPAIGN_*` paths.

- [ ] **Step 2: Run both demo test files and verify RED**

```bash
cd release-gate
uv run pytest tests/test_demo_python_slugify.py \
  tests/test_demo_campaign_report.py -q
```

Expected: FAIL because grade is not wired to the store.

- [ ] **Step 3: Implement the orchestration**

Refactor the public function to an explicit signature equivalent to:

```python
def grade(
    path: Path,
    *,
    metadata: CampaignMetadata,
    record: bool = True,
) -> str:
    ...
```

Within grading:

- Load exact result bytes and inspect/print the result.
- Reconstruct the candidate from recorded evidence.
- Run the oracle in that reconstructed candidate.
- Derive the existing classification matrix, or `oracle_error` for unknown
  truth.
- Build the fixed v1 record, including SHA-256 of exact result bytes and oracle
  source, current UTC RFC-3339 `graded_at`, structured run kind, and optional
  metadata.
- If `record=True`, call `record_and_refresh`, then print absolute
  `CAMPAIGN_RECORD`, `CAMPAIGN_REPORT`, and `CAMPAIGN_DATA` paths.
- After a durable oracle-error record/report, raise a dedicated `DemoError` so
  `main()` returns 1 without reclassifying the candidate as wrong.
- In `verify`, pass `record=False` and control metadata; preserve its existing
  expected verdict/classification assertions.
- Dispatch `campaign-report` directly to `refresh(PRIVATE_CAMPAIGN)` and print
  only `CAMPAIGN_REPORT` and `CAMPAIGN_DATA`; never call `_require_gate_version`,
  `_verify_repository`, the gate, reconstruction, or oracle.

- [ ] **Step 4: Run demo tests, then the complete Release Gate test suite**

```bash
cd release-gate
uv run pytest tests/test_demo_python_slugify.py \
  tests/test_demo_campaign_report.py -q
uv run pytest -q
```

Expected: all focused tests and the complete suite pass.

- [ ] **Step 5: Run Ruff**

```bash
cd release-gate
uv run ruff check demo/python-slugify/campaign_report.py \
  demo/python-slugify/demo.py tests/test_demo_campaign_report.py \
  tests/test_demo_python_slugify.py
```

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add release-gate/demo/python-slugify/campaign_report.py \
  release-gate/demo/python-slugify/demo.py \
  release-gate/tests/test_demo_campaign_report.py \
  release-gate/tests/test_demo_python_slugify.py
git commit -m "feat(release-gate): record private demo campaign grades"
```

---

### Task 8: Documentation, privacy contract, and final verification

**Files:**
- Modify: `release-gate/demo/python-slugify/.gitignore`
- Modify: `release-gate/demo/python-slugify/README.md`
- Modify: `release-gate/tests/test_demo_python_slugify.py`
- Verify unchanged: `release-gate/skills/release-gate/SKILL.md`
- Verify unchanged: `release-gate/src/release_gate/observability.py`

- [ ] **Step 1: Write failing documentation-contract tests**

Extend `test_committed_demo_assets_are_self_contained` or add a focused test
requiring:

```python
ignore = (DEMO / ".gitignore").read_text(encoding="utf-8")
readme = (DEMO / "README.md").read_text(encoding="utf-8")
assert "private-campaign/" in ignore
for phrase in (
    "campaign-report",
    "CAMPAIGN_RECORD",
    "FALSE_RELEASE",
    "false releases given PASS",
    "Wilson",
    "--run-kind re-gate",
    "--run-kind control",
    "not encrypted",
    "X1 repeatability",
):
    assert phrase in readme
```

Also snapshot the portable skill and public observability files before the docs
task and assert this task's diff does not touch them.

- [ ] **Step 2: Run the documentation test and verify RED**

Expected: FAIL because the private campaign workflow is undocumented and
unignored.

- [ ] **Step 3: Update `.gitignore` and README**

Append `private-campaign/` to the demo `.gitignore`.

In the README, add:

- Windows and macOS examples for `grade` with all optional metadata;
- output tree (`records/`, `campaign-v1.json`, `index.html`);
- `campaign-report` regeneration command;
- classification matrix and separate `false_release_per_total` versus
  `false_release_given_pass` denominators;
- structured `trial`, `re-gate`, and `control` cohort rules;
- Wilson 0/N interpretation and sample-size limitations;
- explicit statement that the report is local/gitignored but not encrypted;
- explicit statement that the normal gate dashboard still contains only gate
  decisions and that the portable skill remains unchanged.

- [ ] **Step 4: Run all automated verification**

```bash
cd release-gate
uv run pytest --cov=release_gate --cov-report=term-missing -q
uv run mypy src/release_gate
uv run ruff check src tests scripts demo/python-slugify
python tests/validate_skill.py
```

Expected:

- pytest exits 0 and package coverage remains at least 80%;
- mypy exits 0;
- Ruff exits 0;
- skill validator prints `VALID:`.

The demo-only modules are outside the package mypy target, so their behavior is
covered by pytest and Ruff. Do not broaden package boundaries merely to type-check
the demo.

- [ ] **Step 5: Run a local no-network functional campaign smoke test**

Use the deterministic control machinery only if the workbench and dependencies
already exist. Otherwise use the integration fixture from Task 7; do not require
network access merely for this smoke test.

Confirm a synthetic `PASS + wrong` grade produces:

```text
classification: FALSE_RELEASE
CAMPAIGN_RECORD: ...
CAMPAIGN_REPORT: ...
CAMPAIGN_DATA: ...
```

Open `campaign-v1.json` programmatically and assert the primary false-release
numerator and denominator. Confirm the normal `_observability` data remains
unchanged by grading.

- [ ] **Step 6: Refresh the repository knowledge graph**

From the repository root:

```bash
graphify update .
```

Expected: incremental update completes. Dirty `graphify-out/` files are expected
and must not be used as a reason to skip the update. Do not stage ignored graph
outputs unless they are already tracked and the update changed them.

- [ ] **Step 7: Inspect the final diff and confirm scope**

```bash
git status --short
git diff --check
git diff --stat
git diff -- release-gate/skills/release-gate/SKILL.md \
  release-gate/src/release_gate/observability.py
```

Expected: no whitespace errors; no diff in the portable skill or public
observability; unrelated existing untracked files remain untouched.

- [ ] **Step 8: Commit documentation and final integration**

```bash
git add release-gate/demo/python-slugify/.gitignore \
  release-gate/demo/python-slugify/README.md \
  release-gate/tests/test_demo_python_slugify.py
git commit -m "docs(release-gate): document private demo campaign report"
```

- [ ] **Step 9: Final post-commit verification**

Run the four commands from Step 4 again and record the exact pass counts and
coverage in the implementation handoff. Do not claim completion from an earlier
test run.

---

## Implementation Guardrails

- The gate verdict is immutable input to grading; never rewrite or reinterpret
  `result.json`.
- Hidden oracle data never enters gate evidence, public observability, or the
  portable skill.
- `campaign-report` is report regeneration only; it cannot run the gate or
  oracle.
- Missing or malformed stored records fail closed and are never silently skipped.
- A record is the durable unit; aggregate files are regenerable views.
- Primary denominators contain only structured `run_kind == "trial"` records.
- `oracle_error` is visible but excluded from correctness denominators.
- Missing cost/time/model data stays unknown and keeps its own denominator.
- No automatic retry, merge, deployment, browser opening, or network publishing.
- Preserve the user's unrelated untracked `../../../release-gate/demo/rate-limiter/` and
  `demo/runs/setup-verification-20260817/` directories.
