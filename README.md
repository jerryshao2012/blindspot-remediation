# Blindspot Remediation — can an AI make simple code changes, and how would we know each one is safe?

This README assumes you have never heard of any of this. It explains the
problem, the idea, what is in this repository, and how the demo works, in
that order. It is written to be read top to bottom in about fifteen minutes.

---

## 1. The problem, in plain words

AI coding assistants (GitHub Copilot and others) can now make code changes on
their own: bump a library version, rename a variable, replace a deprecated
function. Cheap, fast, and — sometimes — wrong.

If a person makes such a change, a colleague reviews it before it ships. If an
AI makes a hundred such changes a day, having a person review every one
defeats the purpose. So you want an **automatic checker** that looks at each
AI-made change and says one of three things:

- **PASS** — safe, ship it.
- **FAIL** — something is wrong, do not ship.
- **NEEDS_HUMAN** — I could not tell; a person must look.

We call that checker **the gate**. Building the gate is the project.

But there is a catch that most teams miss, and it is the whole reason this
repository exists:

> **A gate's verdicts mean nothing until you have measured the gate itself.**

If the gate says PASS, was it right? If it says FAIL, was the change actually
bad — or did the gate just block good work? You cannot know unless you already
know the correct answer for that change and compare. So alongside the gate,
you need a **test bench**: a small set of tasks where the right answer is
known in advance, so the gate can be graded.

That is the entire idea. Two lanes:

```
 ONLINE (every change)     task ──► AI makes change ──► GATE ──► PASS / FAIL / NEEDS_HUMAN

 OFFLINE (now and then)    known tasks ──► same AI, same gate ──► compare against
                                                                   the known answer
                                                                   ──► "how often is
                                                                        the gate right?"
```

Why can't you just watch what happens in production instead? Because
production is one-sided. If the gate passes a bad change, you eventually find
out — something breaks. If the gate *blocks a good change*, you never find
out: the change didn't ship, nothing happened, no trace. Only the offline
lane, where you hold the answers, can see both kinds of mistake. (This is
`NOTES.md` note N-6, and it is the sharpest thinking in this repository.)

---

## 2. Vocabulary you will hear

| Word | Meaning here |
|---|---|
| **Candidate** | A code change an AI has proposed but nobody has accepted yet. |
| **Gate** | The automatic checker. Returns PASS / FAIL / NEEDS_HUMAN. |
| **Evidence** | What the gate looked at to decide: test results, coverage, type checks, lint, a secret scan, a scope check. Several *kinds*, on purpose — one kind of evidence can be fooled; several independent kinds are harder to fool. |
| **Fail closed** | If a check *cannot run* (tool missing, timeout, crash), that is not a pass. It is not even a fail — we learned nothing — so the gate says NEEDS_HUMAN. A gate that quietly skips broken checks is theatre. |
| **Oracle** (hidden) | The answer key: extra tests we keep secret from the AI and from the gate, used only to grade the gate afterwards. |
| **False release** | Gate said PASS, change was actually wrong. The dangerous mistake. |
| **False block** | Gate said FAIL, change was actually fine. The costly mistake — and the one production can never show you. |
| **Layer 1 task** | The simplest kind of engineering task: mechanical, no design judgment. "Change package x to y." "Rename this variable." We start here on purpose. |
| **X1** | Our first Layer 1 task. |
| **Run** | One trip through the pipeline: reset → AI makes change → gate decides → oracle grades. One row in the run log. |
| **Baseline** | The repository *before* the change, with all its tests passing. Must be green, or no verdict means anything. |

---

## 3. What is in this repository

Four distinct areas live here. Do not confuse them.

### 3a. The reusable product — `release-gate/` (v0.6.0)

[`release-gate/`](release-gate/) is the standalone, production-ready implementation
for reuse across repositories. It is an independent Python 3.11+ CLI with a
repository-owned `.release-gate.yaml`, versioned JSON schemas (`schemas/`),
clean candidate isolation using a private Git object database, base-trusted policy
enforcement, three-way verdicts (`PASS`, `FAIL`, `NEEDS_HUMAN`), and thin
portable assistant skills for GitHub Copilot, OpenAI Codex, Claude Code, and
Google Antigravity. It has no runtime dependency on the demo or on the A/B
scaffolding.

Key capabilities in v0.6.0:
- **Bounded Repair Workflow:** An automated, human-in-the-loop repair state
  machine ($C0 \to C1 \to C2$) with an explicit 2-attempt budget, candidate
  lineage tracking, disposable workspace isolation, and transactional apply
  verified against SHA-256 digests.
- **Assurance-Aware & Graphify Diagnosis:** Optional, read-only Graphify
  diagnosis bounded to failed checks; reports unverified layers inside aggregate
  suites without falsely claiming coverage.
- **Decision Observability Dashboards:** Self-contained, non-gating rolling 10
  and rolling 100 HTML/JSON dashboards (`_observability/`) and tamper-evident
  per-run snapshots.
- **Dual Benchmark Demos ([`release-gate/demo/`](release-gate/demo/)):**
  1. `python-slugify` (Task X1): Packaging migration, ambient environment
     confusion, uninstalled dependencies, and tampering defenses.
  2. `rate-limiter`: In-process sliding-window rate limiter with 100% branch
     coverage, an 8-mutant mutation gauntlet, brute-force differential oracle,
     and the full bounded repair cycle ($C0 \to C1 \to C2$).

Start with [`release-gate/README.md`](release-gate/README.md). This is the
product to install for a new repository.

### 3b. The scaffolding — a design that was generated, unpacked, and audited

Directories `A1-…` through `A12-…`, `B1-…` through `B8-…`, `E1-E2-…`, and
`prompts/`.

Before any code existed, about twenty design documents were generated with an
AI assistant, describing a full-blown version of the two-lane system above:
twelve components (A1–A12), a reconciliation pass (B1–B8), and a side
component called the Evidence Diversity Mapper (E1/E2). Five prompt files then
instructed an AI to turn those documents into repositories.

This repository is the unpacked result plus an **audit**: every document
became a real directory with real Python (~35,000 lines), and each was
installed and tested. The findings are in [INDEX.md](INDEX.md) (where every
artifact went, its test status, sixteen catalogued defects) and
[NOTES.md](NOTES.md) (open questions).

The honest summary of the scaffolding: **its thinking is good and its code
does not run as a system.** No part of it calls an AI. Eight of the twelve
components import nothing and are imported by nothing. Two of the four planned
build stages never happened. The measurement harness was never connected to
the gate. Read [ORIGINS.md](ORIGINS.md) for the full story — what each
artifact was, which parts we use, and what we still need.

What we *keep* from it: five ideas (generator and verifier are separate; a
three-way verdict where "cannot judge" is not "bad"; measure the gate offline
against known answers; report counts with denominators, never one score;
version and hash every governing artifact), and one small module worth
reusing (`B5-evaluation-campaign/…/statistics.py`, confidence intervals done
correctly).

**Ironically, the scaffolding demonstrates on itself the very failure it was
designed to catch:** two versions of the same prompt with no way to tell
which was current, three copies of one component under two labels, the same
concept ("gate outcome") defined nine incompatible ways. Keep that in mind
when someone asks why any of this is necessary.

### 3c. The demo & evaluation campaign — minimum working versions of the two lanes

Directory `demo/`. Small, and it runs.

The Bash interface at `demo/gate/gate.sh` remains supported unchanged for the
X1 teaching walkthrough. `A3-release-gate-service` is audited legacy source material;
neither is the reusable product.

```
demo/
├── setup_workbench.sh    clone python-slugify at a pinned green commit; reset between runs
├── tasks/
│   ├── X1.md             the task card — what the AI is told; points to active version
│   ├── X1_v1.md, X1_v2.md  frozen copies of each version — diff them to see the real change
│   └── X1-CHANGES.md     why each version changed, and which runs used it
├── gate/
│   ├── gate.sh           THE GATE  (~200 lines of shell, read top to bottom)
│   └── SKILL.md          wrapper so GitHub Copilot CLI can trigger the gate as a "skill"
├── oracle/
│   └── test_x1_oracle.py THE ANSWER KEY — hidden from the AI and from the gate
├── grade.sh              run the oracle, sort the run into a box, append to the run log
├── campaign.sh           live campaign runner — N fresh Anthropic sessions through the gate
├── RUN.md                step-by-step: do a run yourself
├── DIAGRAMS.md           the flow and the HLD mapping, in Mermaid
├── CORPUS.md             which repos are on the bench and why
├── workbench/            (created by setup; not committed) the clone + venv the AI works in
└── runs/                 (created per run) evidence.json, patch, per-check logs, RUNLOG.md,
                          campaign.csv, campaign-ledger.xlsx
```

### 3d. Presentation suite and visual hub — `docs/`

Directory `docs/`, launched locally via [`serve-presentations.sh`](serve-presentations.sh)
(macOS/Linux) or [`serve-presentations.ps1`](serve-presentations.ps1) (Windows PowerShell):
- **Presentation Hub (`docs/presentations.html`):** Interactive presentation
  portal hosted on GitHub Pages and localhost.
- **Deep-Dive Decks:** Includes *Code Assistant Skill & Plugin Development*,
  *X1 — Behind the Scenes* (packaging and divergence walkthrough),
  *Rate Limiter — Behind the Scenes* (bounded repair and mutation gauntlet),
  and *Architecture Reference*.


---

## 4. How the demo works, box by box

Compare with the HLD diagram: the top lane is `Task request → ChangeExecutionService
→ Candidate → ReleaseGateService → decision`; the bottom lane is
`benchmark → run the same pipeline → compare against hidden oracle → analysis`.

### The workbench — `python-slugify`, pinned

`python-slugify` is a small open-source library (444 lines, 82 tests, one
dependency, MIT) that turns text into URL-safe "slugs": `piñata` → `pinata`.
We pinned it at commit `7b6d5d9`, where all 82 tests pass in under a second.

Why a stranger's repository and not our own? Not because the gate only works
there — it would run on any repo. Because *here we secretly know the right
answer* (see the oracle), so the gate's verdict can be graded. On our own repo
we would get a verdict and no way to know if it was correct.

Admission rule for any repo on the bench: **the baseline must be green from a
clean clone.** Otherwise "the AI broke it" and "it was already broken" are
indistinguishable, and every verdict is noise.

### The task — X1: "switch package x for y"

`python-slugify` transliterates non-ASCII characters using a backend library.
Today the default is `text-unidecode`; a different library, `Unidecode`, is
offered as an optional extra. Task X1: make `Unidecode` the required backend
and drop `text-unidecode`. Two lines in `setup.py`, one import in the source.
Mechanical. Layer 1. It is the textbook "change package x to y".

**Why this task, specifically.** The two backends agree on almost every input
— all 82 existing tests pass under both. So the swap *looks* clean and *tests*
clean. But they genuinely disagree on some inputs, verified through
`slugify()` itself:

```
input      before (text-unidecode)   after (Unidecode)
'₹500'     '500'                     'rs500'
'♥ love'   'love'                    'hearts-love'
'♠ ace'    'ace'                     'spades-ace'
```

A slug is usually a URL. `rs500` versus `500` is a changed permalink. That is
the consequence a mechanical swap hides — and it is not something a
find-and-replace can reason about, which is why the task needs an AI and why
the change needs a gate. If `sed` could do a task perfectly, the gate would
have nothing to catch and the demo would prove nothing.

### The AI — GitHub Copilot CLI

Copilot CLI is the `ChangeExecutionService` box. It reads `X1.md`, edits the
workbench, runs the visible tests, and stops. We did not build it and do not
need to; the scaffolding's own executor (A2) applied human-written patches
and had no AI in it, and Copilot replaces that whole component.

The `SKILL.md` next to the gate is a small wrapper that lets Copilot *trigger
the gate itself* by name after making a change, and tells it to report the
verdict verbatim rather than judging its own work. For run 1 you run the gate
by hand, so you see every step.

### The gate — `demo/gate/gate.sh`

Read it; it is written to be read. It gathers six kinds of evidence and
returns one verdict:

| check | what it asks | why it is here |
|---|---|---|
| **tests** | do the 82 existing tests still pass? | the basic behavioural check |
| **coverage** | is the test suite still exercising the code? *differential*: candidate may not lower coverage more than 1 point below baseline; hard floor 85% | catches "changed the code, left the old path behind as dead code" |
| **types** | mypy on the package | static evidence, independent of tests |
| **lint** | ruff — *differential*: did the candidate ADD findings vs the baseline's 58? | judges the *change*, not the repo's history |
| **secrets** | credential-shaped strings in the change | must-not check |
| **scope** | was `test.py` modified? | a candidate that rewrites its own tests can make anything "pass" |

Then: **any check errored → NEEDS_HUMAN; else any check failed → FAIL; else PASS.**
Error outranks fail on purpose: if a check could not run, we do not fully know
what the candidate is, and "FAIL" would claim knowledge we lack.

Every run writes `demo/runs/<run_id>/evidence.json` — what the gate saw, the
policy numbers it used, the verdict, a hash of the patch — plus the patch
itself and one log per check. That is the evidence trail.

Two of the checks are **differential** (compare candidate to baseline) rather
than absolute. This came out of building it: the upstream repo already has 58
lint findings. A gate that lints the whole tree would fail every candidate for
sins it did not commit, and the check would carry no information. The gate
must judge the change, not the history.

### The oracle — `demo/oracle/test_x1_oracle.py`

The answer key. Fifteen tests: the six divergent inputs above (must now give
the *new* answers), six inputs the backends agree on (must be unchanged), and
three structural checks (the fallback import must be gone; `setup.py` must
declare the new backend; the new backend must actually be installed).

**Copilot never sees this file. The gate never runs it.** It lives outside the
workbench and is only run by `grade.sh`, after the gate has spoken.

### Grading — `demo/grade.sh`

Runs the oracle, combines its answer with the gate's verdict, and sorts the run
into one of four boxes:

|                     | change was correct | change was wrong |
|---------------------|--------------------|------------------|
| **gate said PASS**  | good_pass          | **FALSE_RELEASE** — dangerous |
| **gate said FAIL**  | **FALSE_BLOCK** — costly | good_catch |
| **gate NEEDS_HUMAN**| escalated          | escalated |

Then appends one row to `demo/runs/RUNLOG.md`: run id, verdict, truth, box,
wall time, tokens. Tokens are recorded as `unknown` if the tool did not report
a number — never estimated.

---

## 5. The gate has already been shown to fail — on purpose

A gate that has only ever been seen passing is worth nothing; you have to
prove it *can* say no. Before anyone ran the real thing, four control runs
were done (their evidence is in `demo/runs/control*/`):

| control | what was planted | gate said | oracle said | box |
|---|---|---|---|---|
| 1 — untouched baseline | nothing | PASS | — | (sanity: the gate passes a green repo) |
| 2 — the **lazy candidate**: edited `setup.py`, kept the `try/except` fallback import | a plausible half-job | **PASS** | **wrong** | **FALSE_RELEASE** |
| 3 — a tool removed from the venv (`mypy`) | broken infrastructure | **NEEDS_HUMAN** | — | escalated |
| 4 — `test.py` modified | tampering with evidence | **FAIL** (scope) | — | good_catch |

Control 2 is the one to understand. The lazy candidate passes every
visible check — the 82 tests are green under both backends, so the gate has
no evidence against it — and the hidden oracle catches it. **That is a false
release, measured.** It is exactly the box the whole design exists to count,
and the gate as built *cannot* catch it on its own; only a stronger check
(for example, running the hidden divergent inputs, or a dead-code detector)
would. Which is the honest lesson: the visible test suite is weaker evidence
than it looks, and knowing *how much* weaker is what the offline lane is for.

Control 3 is the other one to understand: with a tool missing, the gate said
NEEDS_HUMAN, not PASS. That is fail-closed working. (Its first attempt on
this machine actually failed closed on a *real* fault — the `timeout` command
does not exist on macOS — before any control was planted. Good.)

---

## 6. Running it

### The Interactive Teaching Demo (`demo/`)

**First time (2 minutes):**

```bash
bash demo/setup_workbench.sh
```

**One run, driven by hand — follow [demo/RUN.md](demo/RUN.md).** In short:

```bash
bash demo/setup_workbench.sh reset                       # 1. baseline green
cd demo/workbench/python-slugify && copilot              # 2. give it demo/tasks/X1.md; time it
cd ../../..                                              #    (note wall seconds and tokens)
bash demo/gate/gate.sh "$PWD/demo/workbench/python-slugify" "$PWD/demo/workbench/venv" run-01
bash demo/grade.sh run-01 <wall_seconds> <tokens|unknown> # 4. oracle → box → RUNLOG.md
```

**Automated Campaign Runs (`demo/campaign.sh`):**
To execute automated multi-session evaluations against the gate (e.g. using Anthropic Claude models) and record them into `demo/runs/campaign-ledger.xlsx`:

```bash
bash demo/campaign.sh 5   # runs 5 automated sessions through the gate
```

**To watch the gate refuse (30 seconds each):**

```bash
echo "# x" >> demo/workbench/python-slugify/test.py && bash demo/gate/gate.sh "$PWD/demo/workbench/python-slugify" "$PWD/demo/workbench/venv" try-tamper   # FAIL on scope
bash demo/setup_workbench.sh reset
```

### The Standalone Product Demos (`release-gate/demo/`)

See [`release-gate/demo/README.md`](release-gate/demo/README.md) for full instructions:
- **`python-slugify`:** `uv run --python 3.12 --no-project python demo.py verify`
- **`rate-limiter`:** `bash run.sh demo` (POSIX) or `.\run.ps1 demo` (PowerShell)

---

## 7. What the numbers tell us (Runs 1–5 and Beyond)

Runs 1–5 on Task X1 (card v2) are **completed** and logged in [`demo/runs/RUNLOG.md`](demo/runs/RUNLOG.md):

| run_id | task | card | gate verdict | truth (oracle) | box | wall_s | cost | model |
|---|---|---|---|---|---|---|---|---|
| run-01 | X1 | v1 | NEEDS_HUMAN | oracle_error | escalated | 127 | 16.2 AIC | claude-haiku-4.5 |
| run-01b | X1 | v1 | PASS | correct | good_pass | (re-gate after `pip install Unidecode`) | — | (same) |
| run-02 | X1 | v2 | PASS | correct | good_pass | 103 | 16.6 AIC | claude-haiku-4.5 |
| run-03 | X1 | v2 | PASS | correct | good_pass | 90 | 10.4 AIC | claude-haiku-4.5 |
| run-04 | X1 | v2 | PASS | correct | good_pass | 92 | 11.4 AIC | claude-haiku-4.5 |
| run-05 | X1 | v2 | PASS | correct | good_pass | 69 | 9.0 AIC | claude-haiku-4.5 |

**Findings from the first five runs:**
- **Cost & Latency:** Four clean v2 sessions averaged **88 seconds** and **~11.8 AIC** per run.
- **Fail-Closed Working:** Run 1 proved that environment confusion (the model declaring a package in `setup.py` but failing to install it into the venv) safely results in `NEEDS_HUMAN` rather than a broken pass.
- **What five clean runs do and do not say:** 4/4 good passes on v2 (5/5 with run-01b). By B5's Wilson interval, zero failures in $n=4$ still leaves the true failure rate possibly as high as **49%** ($n=5$ is $43\%$, $n=20$ is $16\%$, $n=30$ is $11\%$). Five runs sized the bill; automated campaigns (`campaign.sh`) expand the denominator.

Always report *counts with denominators*, never one composite score. "1 false release in 30 runs" is an actionable statement. "97% quality" is not.

---

## 8. Roadmap & Current Implementation Status

1. **Runs 1–5 on X1:** **Done.** Completed, costs sized (~88s, ~12 AIC), logged in `RUNLOG.md`.
2. **Second benchmark repository:** **Done.** `rate-limiter` implemented in `release-gate/demo/rate-limiter/` with 100% branch coverage, 8-mutant mutation gauntlet, brute-force differential oracle, and bounded repair.
3. **Standalone Product (v0.6.0):** **Done.** `release-gate/` CLI, bounded repair state machine ($C0 \to C1 \to C2$) with 2-attempt budget, read-only Graphify diagnosis, rolling 10/100 decision dashboards, and assistant skills.
4. **Live Evaluation Campaigns:** **Done.** `campaign.sh` automated runner added, separating executor infrastructure failures (`EXEC_ERROR`) from gate verdicts in `campaign-ledger.xlsx`.
5. **Presentation Hub & Decks:** **Done.** Interactive decks in `docs/` served via `serve-presentations.sh` / `.ps1`.
6. **Next steps:**
   - Add third benchmark repository (`itsdangerous` or `cachetools`; see `demo/CORPUS.md`).
   - Run the Evidence Diversity Mapper as a corpus audit ("these repos are pure libraries; what service-shaped patterns are missing?").
   - The backtest (NOTES N-8): Replay the gate over historical commits and reverts in target repositories.

---

## 9. Where to read more

- [**`release-gate/README.md`**](release-gate/README.md) — The standalone product, bounded repair, CLI usage, and skill integration.
- [**`release-gate/demo/README.md`**](release-gate/demo/README.md) — The standalone dual demos (`python-slugify` and `rate-limiter`).
- [**`ORIGINS.md`**](ORIGINS.md) — The scaffolding explained: original artifacts, what was kept, and evolution.
- [**`INDEX.md`**](INDEX.md) — Where every artifact went, test status, and sixteen catalogued defects.
- [**`NOTES.md`**](NOTES.md) — Architecture decisions and open questions (`N-6` on offline measurement, `N-10` on rate limiter).
- [**`docs/presentations.html`**](docs/presentations.html) — Interactive presentation hub for deep-dive slide decks.
- `demo/gate/gate.sh` — The original bash teaching gate.

