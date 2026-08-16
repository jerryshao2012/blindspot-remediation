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

Two very different things live here. Do not confuse them.

### 3a. The scaffolding — a design that was generated, unpacked, and audited

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

### 3b. The demo — a minimum working version of the two lanes

Directory `demo/`. Small, and it runs. Everything below is about this.

```
demo/
├── setup_workbench.sh    clone python-slugify at a pinned green commit; reset between runs
├── tasks/
│   ├── X1.md             the task card — what the AI is told (and nothing more); says which version is live
│   ├── X1_v1.md, X1_v2.md  frozen copies of each version — diff them to see the real change
│   └── X1-CHANGES.md     why each version changed, and which runs used it
├── gate/
│   ├── gate.sh           THE GATE  (~200 lines of shell, read top to bottom)
│   └── SKILL.md          wrapper so GitHub Copilot CLI can trigger the gate as a "skill"
├── oracle/
│   └── test_x1_oracle.py THE ANSWER KEY — hidden from the AI and from the gate
├── grade.sh              run the oracle, sort the run into a box, append to the run log
├── RUN.md                step-by-step: do a run yourself
├── DIAGRAMS.md           the flow and the HLD mapping, in Mermaid
├── CORPUS.md             which repos are on the bench and why
├── workbench/            (created by setup; not committed) the clone + venv the AI works in
└── runs/                 (created per run) evidence.json, patch, per-check logs, RUNLOG.md
```

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

**First time (2 minutes):**

```bash
bash demo/setup_workbench.sh
demo/workbench/venv/bin/pip install pytest-cov mypy ruff
```

**One run, driven by hand — follow [demo/RUN.md](demo/RUN.md).** In short:

```bash
bash demo/setup_workbench.sh reset                       # 1. baseline green
cd demo/workbench/python-slugify && copilot              # 2. give it demo/tasks/X1.md; time it
cd ../../..                                              #    (note wall seconds and tokens)
bash demo/gate/gate.sh "$PWD/demo/workbench/python-slugify" "$PWD/demo/workbench/venv" run-01
bash demo/grade.sh run-01 <wall_seconds> <tokens|unknown> # 4. oracle → box → RUNLOG.md
```

**To watch it refuse (30 seconds each):**

```bash
echo "# x" >> demo/workbench/python-slugify/test.py && bash demo/gate/gate.sh "$PWD/demo/workbench/python-slugify" "$PWD/demo/workbench/venv" try-tamper   # FAIL on scope
bash demo/setup_workbench.sh reset
```

---

## 7. What the numbers will and will not tell you

Run 1 proves the plumbing. Runs 2–5 give an average for minutes and tokens per
run — the cost estimate.

Five runs are **not** evidence the pipeline works. If every one of five runs
is clean, the true failure rate could still be as high as 43%. This is the
Wilson interval, computed by the scaffolding's own `statistics.py`:

| clean runs | true failure rate could still be up to |
|---|---|
| 5 | 43% |
| 10 | 28% |
| 20 | 16% |
| 30 | 11% |
| 100 | 4% |

So the honest sequence is: **5 runs to size the bill; the bill decides whether
30 or 100 are affordable; 30-plus starts to be evidence.** Present it that way
and the number survives a skeptic.

Also: report *counts with denominators*, never one score. "1 false release in
30 runs" is a statement. "97% quality" is not.

---

## 8. What comes next, in order

1. **Runs 1–5** on X1 (this document).
2. **A second and third repository** on the bench, each with a green baseline
   from a clean clone and its own X-task and oracle. `itsdangerous` (297
   tests, 0.6 s) and `cachetools` (312 tests, 4.4 s) are measured and admitted;
   see `demo/CORPUS.md` for the full candidate table.
3. **A stronger gate**, driven by what the runs reveal. Control 2 already
   says where: the visible suite cannot see backend divergence.
4. **The Evidence Diversity Mapper as a corpus audit** — "your three repos are
   all pure libraries; your bench cannot see service-shaped code" — which is
   cheap and tells you what the bench is blind to. Only after that, and only if
   the audit says the bench is too narrow, synthetic repository generation.
5. **The backtest** (NOTES N-8): replay the gate over ~200 real merged changes
   in one of our own repos, using reverts as labels. Real code, free answer
   key, one-sided (history cannot show false blocks) — but real.

---

## 9. Where to read more

- [ORIGINS.md](ORIGINS.md) — the scaffolding explained: every original
  artifact, which we use, what we still need.
- [INDEX.md](INDEX.md) — where every artifact went; test status; sixteen
  catalogued defects.
- [NOTES.md](NOTES.md) — open questions. N-6 (why you need the offline lane)
  and N-8 (the three questions a gate must answer) are the ones to read.
- `demo/gate/gate.sh` — the gate itself. It is the best documentation of what
  the gate does, because it *is* what the gate does.
