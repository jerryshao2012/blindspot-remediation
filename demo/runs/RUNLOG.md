# Run log

One row per **gate run**. A single AI session can produce more than one row:
if the gate escalates (NEEDS_HUMAN), a human acts, and the gate is re-run,
that re-gate is its own row with a suffix (`run-01b`) and the `human step`
column says what the human did. Wall time and cost belong to the AI *session*,
so a re-gate row repeats them as "(same)" rather than counting them twice.

Columns: `card` is the task-card version the AI saw (`demo/tasks/X1_vN.md`);
rows with different cards measure slightly different things and should not be
averaged together. `human step` is `none` when the gate's first verdict stood
on the AI's work alone. `cost` is what the tool reported, in its own unit
(Copilot CLI shows "AIC used" in its footer, not tokens); `unknown` means it
did not report one — never a guess. `model` is what the executor actually used
(Copilot Free only offers Auto, so the model can differ between runs; recording
it is what keeps runs comparable). `box` is the confusion-matrix cell.

| run_id | task | card | gate verdict | truth (oracle) | box | human step | wall_s (copilot) | cost | model |
|---|---|---|---|---|---|---|---|---|---|
| control2-lazy | X1 | v1 | PASS | wrong | FALSE_RELEASE | (planted candidate, no AI) | 0 | unknown | — |
| run-01 | X1 | v1 | NEEDS_HUMAN | oracle_error | escalated | none — as delivered | 127 | 16.2 AIC | claude-haiku-4.5 (Auto) |
| run-01b | X1 | v1 | PASS | correct | good_pass | re-gate of run-01 after human `pip install Unidecode` | (same session as run-01) | (same) | (same) |
| run-02 | X1 | v2 | PASS | correct | good_pass | none | 103 | 16.6 AIC | claude-haiku-4.5 (Auto) |
| run-03 | X1 | v2 | PASS | correct | good_pass | none | 90 | 10.4 AIC | claude-haiku-4.5 (Auto) |
| run-04 | X1 | v2 | PASS | correct | good_pass | none | 92 | 11.4 AIC | claude-haiku-4.5 (Auto) |
| run-05 | X1 | v2 | PASS | correct | good_pass | none | 69 | 9.0 AIC | claude-haiku-4.5 (Auto) |

## Notes

### run-01 → run-01b (2026-08-16) — the first real trip through both lanes

Copilot CLI made every edit correctly (setup.py, the import, README, tox.ini)
but never installed the dependency it declared, and it ran the tests with the
system Python — where Unidecode happened to exist — so it reported "82 passed".
The gate re-ran the tests in the workbench venv, where Unidecode did not exist,
got a collection error (pytest exit 2 — the tests never ran), and said
NEEDS_HUMAN rather than FAIL or PASS. A human installed the missing package
(one `pip install`) and re-ran the gate as run-01b: PASS on all six checks;
the hidden oracle then confirmed the change correct on 15/15 (good_pass).

What it taught, and what changed because of it:
- **Executor and gate must share an environment.** The task card said
  `python -m pytest`; "python" meant different interpreters to Copilot and to
  the gate. `demo/tasks/X1.md` now names the venv interpreter explicitly and
  says to reinstall after touching setup.py.
- **run-01 and run-01b are two rows on purpose.** Overwriting run-01 would
  record "the AI's change passed" when the truth is "the AI's change passed
  after a human fixed its environment." Keeping both keeps the denominator
  honest.

### run-02 (2026-08-16) — task card v2, no human step needed

Same task, card v2 (`demo/tasks/X1_v2.md`), which names the venv interpreter
and says to reinstall after touching setup.py. Copilot made the same four
edits as run 1 and this time also reinstalled the package. Gate: PASS on all
six checks (coverage 89% → 90%, the try/except branch removed); oracle 15/15;
good_pass. 103 s, 16.6 AIC, Auto → claude-haiku-4.5.

Method note: the card was pasted on its own, without the two-line wrapper
RUN.md suggests around it. The card already contains "do not modify test.py"
and the exact test command, so nothing the AI needed was missing; the only
thing dropped was "then stop", and the diff shows it stopped anyway. Recorded
here for honesty, not because it changes the result.

What run 1 → run 2 shows, together: the *only* difference between an
escalation and a clean pass was two paragraphs on the task card telling the
AI which interpreter to use and to install what it declared. The AI's edits
were identical. That is a finding about task specification, not about the
model — and it is why the card is versioned.

### runs 03–05 (2026-08-16) — repetition on card v2; the first five-run summary

Runs 3, 4 and 5 repeated card v2 exactly (reset → paste `X1_v2.md` → gate →
grade). All three: PASS on six checks, oracle 15/15, good_pass, no human step,
Auto → claude-haiku-4.5 every time.

**The cost estimate (four v2 sessions, runs 02–05):**

| | wall (s) | cost (AIC) |
|---|---|---|
| runs 02, 03, 04, 05 | 103, 90, 92, 69 | 16.6, 10.4, 11.4, 9.0 |
| mean | **88 s** | **11.8 AIC** |
| range | 69–103 | 9.0–16.6 |

So one X1 run on Copilot Free costs about a minute and a half and ~12 AIC.
Twenty runs ≈ 30 min and ~240 AIC; a hundred ≈ 2.5 h and ~1,200 AIC. Those
are the numbers that decide whether the next campaign is affordable — and
they are the reason five runs were worth doing before twenty.

**What five clean runs do and do not say.** 4/4 good_pass on v2 (5/5
counting run-01b, which needed a human). By B5's own Wilson interval, zero
failures in n=4 still leaves the true failure rate possibly as high as
**49%**; n=5, 43%; n=20, 16%; n=30, 11%. Five runs size the bill. They do
not qualify the pipeline. (Computed with
`B5-evaluation-campaign/…/statistics.py` — the first time a scaffolding
module has done real work in this repo.)

**Where the variance showed up — and where nothing could see it.** The
*code* change (`setup.py` + `slugify/slugify.py`) was byte-identical across
runs 3, 4 and 5 (same diff fingerprints). The variance was all in the
"consistency" step: runs 2 and 3 updated `tox.ini`; **runs 4 and 5 left it
alone**, still naming `text_unidecode` in the test matrix. The card's step 3
asks for exactly that update. Neither the gate nor the oracle can see this,
because both judge the code and a stale `tox.ini` line breaks nothing that
runs. So runs 4 and 5 are correctly graded good_pass on the code — and
slightly incomplete on the task. README wording also differed run to run
("installs and uses" vs "uses"). This is the honest shape of LLM
non-determinism here: **stable where it is checked, variable where it is
not.**

That points at a real gap: the card's own "Done when" says
`grep -rn text_unidecode slugify/ setup.py` — a scope the gate could run
verbatim, and could widen to the whole repo (excluding CHANGELOG, which is
history). Cheap to add; would have flagged runs 4 and 5 as incomplete
rather than passing them silently. Recorded as a candidate gate check, not
added mid-campaign — changing the gate between runs 3 and 4 would have made
the five rows incomparable.

### Is this "continuous monitoring and improvement"? Half of it is.

**The improvement half — yes.** A run exposed a weakness (an ambiguous task
card), we fixed it, and the next run tests the fix. That loop — run, learn,
change the harness, run again — is exactly what this log is for. But note
*what* got improved: the task card and our own harness, not the AI and not the
gate's policy. That is fine and expected at this stage; it just should not be
described as the system tuning itself.

**The monitoring half — not yet, and by design.** Continuous monitoring means
watching a system in ongoing use and acting on what you see. Nothing here is in
ongoing use: these are offline, hand-triggered runs against a benchmark whose
answers we already know. That is the *offline lane* of the HLD (measure the
gate against known truth), not the *online lane* (watch it on real changes).
K's notes were explicit that continuous monitoring is *not* part of this first
flow, and NOTES.md N-6 explains why the two are different instruments: the
offline lane can see both kinds of gate mistake; production can only ever see
one. This log becomes monitoring only when the same gate runs on real
changes and its verdicts are checked against what happens to those changes
afterwards (the N-8 backtest is the cheapest version of that).

So the honest label for this log today: **an offline measurement record with
an improvement loop attached.** Keep the two words separate — it will matter
the first time someone asks "so is it monitored?"
