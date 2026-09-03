# Release Gate Presentations Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the Release Gate HTML presentations in sync with the 2026-09-01 automated verification and 2026-09-02 online X1 evidence without redesigning the decks.

**Architecture:** Treat the September run logs as the source of truth and update the existing presentation copy in place. The X1 deck leads with normal online adoption, while the executive and architecture views distinguish production evidence review from benchmark-only oracle qualification. Existing navigation, speaker view, responsive CSS, and slide counts remain unchanged.

**Tech Stack:** Self-contained HTML/CSS/JavaScript presentations, repository Markdown evidence logs, pytest presentation regression tests, browser-based viewport verification, Graphify.

---

### Task 1: Refresh the X1 walkthrough narrative and evidence

**Files:**
- Modify: `docs/x1-behind-the-scenes.html`
- Reference: `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-02-online-pass.md`
- Reference: `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-01-automated-verification.md`

- [ ] **Step 1: Capture the pre-edit content assertions**

Run:

```bash
rg -n "20260827T143722Z|42e5e792|python3 demo.py|Was the gate right|Production has no oracle" docs/x1-behind-the-scenes.html
```

Expected: the older run ID, baseline, command form, and oracle-first post-verdict story are present.

- [ ] **Step 2: Reframe the opening and proof pipeline**

Replace the primary evidence source with run `20260902T153230Z-0b1d3f349b56`. Keep the six visual nodes but make the sixth production node `Human review` with the message `Diff + evidence before merge`. Describe the oracle as a separate offline qualification lane, not a production stage.

- [ ] **Step 3: Update setup and candidate-production copy**

Use the exact current helper command:

```text
uv run --python 3.12 --no-project python demo.py setup
```

Show the pinned upstream baseline `7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4`. State that Copilot receives the complete frozen `assets/TASK.md` without hints or oracle access, and that the recorded September 2 proof reproduces the candidate with `controls/pass.patch`. Do not claim the recorded patch was authored by Copilot.

- [ ] **Step 4: Update the current result and receipts**

Use the recorded values:

```text
run: 20260902T153230Z-0b1d3f349b56
base commit: a5d82da63b0a40d0de639ec1293e8d1d3c3e0307
candidate tree: 24fa968d82e846d71573f686a2c74e5c342869a0
verdict: PASS
changed paths: README.md, setup.py, slugify/slugify.py, tox.ini
checks: tests-and-coverage PASS; task-consistency PASS; types PASS
warning: OBSERVABILITY_PATH_UNSAFE (non-gating)
```

Do not invent a `trace.json` event count when the September log does not record one.

- [ ] **Step 5: Make slide 13 the production stop and preserve offline qualification**

Replace the automatic `demo.py grade` storyline with the online conclusion:

```text
PASS means the reviewed policy accepted this candidate.
Inspect the evidence and diff before merge.
No hidden oracle ran; semantic correctness is not proven.
```

Retain the hidden oracle in the later controls/qualification material, citing the September 1 automated run with `16` oracle tests and the expected `good_pass`, `good_catch`, and `escalated` classifications.

- [ ] **Step 6: Keep slide metadata and notes consistent**

Update `data-title`, pipeline stage highlighting, source labels, speaker-note transitions, and any slide copy that still presents oracle grading as the normal next production step. Keep exactly 16 `.slide` sections.

- [ ] **Step 7: Verify X1 content assertions**

Run:

```bash
test "$(rg -c '<section class="slide"' docs/x1-behind-the-scenes.html)" -eq 16
rg -n "20260902T153230Z-0b1d3f349b56|7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4|OBSERVABILITY_PATH_UNSAFE|no hidden oracle|September 1" docs/x1-behind-the-scenes.html
```

Expected: 16 slides and all new evidence concepts are present.

### Task 2: Align the executive and architecture narratives

**Files:**
- Modify: `release-gate/demo/release-gate-demo.html`
- Modify: `docs/architecture.html`
- Reference: `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-02-online-pass.md`
- Reference: `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-01-automated-verification.md`

- [ ] **Step 1: Update the executive pipeline distinction**

Keep the 10-slide structure. On the proof-pipeline and X1 summary slides, state that production ends with evidence review and a human release decision; an external oracle is used only in offline known-answer qualification. Add the September 2 `PASS` and three-check evidence to the X1 summary without changing rate-limiter claims.

- [ ] **Step 2: Update executive sources and speaker notes**

Cite both source logs by date and ensure the notes do not imply a production oracle. Preserve the existing Release Gate `0.6.0` version claim.

- [ ] **Step 3: Update the architecture map**

Describe the online lane as assistant/control candidate → deterministic gate → evidence review → human release decision. Keep the offline lane as known-answer controls → gate → hidden oracle grading. Replace the old X1 run source with the September 1 automated verification and September 2 no-oracle run logs.

- [ ] **Step 4: Preserve implementation-status honesty**

Do not change the built/partial/designed status of the Evidence Diversity Mapper, evidence generation planner, or `MORE_EVIDENCE_REQUIRED` loop.

- [ ] **Step 5: Verify deck counts and key distinctions**

Run:

```bash
test "$(rg -c '<section class="slide"' release-gate/demo/release-gate-demo.html)" -eq 10
rg -n -i "no.oracle|without an oracle|offline.*oracle|human review|2026-09-0[12]" release-gate/demo/release-gate-demo.html docs/architecture.html
```

Expected: the executive deck remains 10 slides and both files explicitly distinguish the two modes.

### Task 3: Refresh the presentation hub and validate entry points

**Files:**
- Modify: `docs/presentations.html`
- Verify unchanged: `index.html`
- Verify unchanged: `docs/rate-limiter-behind-the-scenes.html`
- Verify unchanged: `docs/code-assistant-skill-plugin-development.html`

- [ ] **Step 1: Update hub card copy and X1 duration**

Keep the X1 card at 16 slides and change its duration from `20m` to `25m`,
because its speaker-note timings total `24:55`. Describe the deck as a
production-style online gate run plus offline calibration. Update the
executive card to mention the same production/qualification distinction without
changing its 10-slide count or rounded `20m` duration (`19:00` of notes).

- [ ] **Step 2: Validate every local link and asset reference**

Run a read-only Node check across `index.html`, `docs/*.html`, and
`release-gate/demo/release-gate-demo.html`. Extract relative `href`, `src`, and
CSS `url(...)` references, ignore fragments, `data:` URLs, and external URLs,
decode URL escapes, and confirm every local target resolves from the containing
file. Confirm `index.html` still redirects to `./docs/presentations.html`.

Also parse `docs/presentations.html` and confirm the displayed slide counts
match the number of elements whose class list contains `slide` in each linked
deck. Sum `data-duration="MM:SS"` values and confirm the displayed minutes equal
the total rounded up to the next five minutes. Expected hub metadata after the
refresh is `5 Slides · 30m`, `10 Slides · 20m`, `16 Slides · 25m`, and
`14 Slides · 20m`.

- [ ] **Step 3: Confirm unaffected decks retain their structure**

Run:

```bash
node -e 'const fs=require("fs");for(const [f,n] of [["docs/rate-limiter-behind-the-scenes.html",14],["docs/code-assistant-skill-plugin-development.html",5]]){const s=fs.readFileSync(f,"utf8");const count=[...s.matchAll(/<section\b[^>]*class="[^"]*\bslide\b[^"]*"/g)].length;if(count!==n)throw new Error(`${f}: expected ${n}, got ${count}`)}'
```

Expected: both commands succeed.

### Task 4: Run regression and visual verification

**Files:**
- Verify: `docs/x1-behind-the-scenes.html`
- Verify: `release-gate/demo/release-gate-demo.html`
- Verify: `docs/architecture.html`
- Verify: `docs/presentations.html`
- Test: `release-gate/tests/test_presentation_multi_screen_popup.py`

- [ ] **Step 1: Run the existing speaker-view regression suite**

Run:

```bash
uv run --project release-gate --group dev python -m pytest release-gate/tests/test_presentation_multi_screen_popup.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run whitespace and source-diff checks**

Run:

```bash
git diff --check
git diff -- docs/x1-behind-the-scenes.html release-gate/demo/release-gate-demo.html docs/architecture.html docs/presentations.html index.html
```

Expected: no whitespace errors; `index.html` has no diff.

- [ ] **Step 3: Inspect every page at 1280x720**

Start a local server from the repository root:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/docs/presentations.html` in the controlled browser
with a 1280x720 viewport. Follow the hub links to both modified decks and the
two unchanged decks, then open the architecture page directly at
`http://127.0.0.1:8765/docs/architecture.html`. For every `.slide`, verify
`scrollHeight <= clientHeight` and `scrollWidth <= clientWidth`; inspect
screenshots at full size for clipped headings, crowded cards, and unexpected
wrapping. Check the browser console for errors.

- [ ] **Step 4: Exercise navigation and notes entry points**

On both modified slide decks, use ArrowRight and ArrowLeft and confirm the active slide/counter changes. Activate `N` and confirm the existing permission/notes behavior still responds without a JavaScript error. Close any opened popup after the check.

Open both modified decks once through their absolute `file://` URLs and repeat
one ArrowRight/ArrowLeft cycle. Confirm direct-file navigation still works and
the console contains no load-blocking JavaScript errors.

- [ ] **Step 5: Fix and repeat until clean**

If any overflow, wrapping, broken link, console error, or regression appears, make the smallest content/layout correction and repeat Steps 1–4.

### Task 5: Refresh Graphify and report the finished update

**Files:**
- Update generated graph: `graphify-out/`

- [ ] **Step 1: Update the repository graph**

Run:

```bash
graphify update .
```

Expected: Graphify completes successfully and incorporates the changed HTML and design/plan documents.

- [ ] **Step 2: Review final repository state**

Run:

```bash
git status --short
git diff --stat
```

Expected: only the intended presentation files and expected Graphify-generated files are changed.

- [ ] **Step 3: Commit the presentation refresh**

```bash
git add docs/x1-behind-the-scenes.html release-gate/demo/release-gate-demo.html docs/architecture.html docs/presentations.html docs/superpowers/plans/2026-09-02-release-gate-presentations-refresh.md graphify-out
git commit -m "docs: refresh release gate presentations"
```

- [ ] **Step 4: Deliver the result**

Report the updated files, key narrative correction, verification commands and outcomes, and that `index.html`, the rate-limiter walkthrough, and the skill/plugin deck did not require content changes.
