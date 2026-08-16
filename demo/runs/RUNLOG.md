# Run log

One row per run. `cost` is what the tool reported, in the tool's own unit
(Copilot CLI shows "AIC used" in its footer, not tokens); `unknown` means it
did not report one — never a guess. `model` is what the executor actually used
(Copilot Free only offers Auto, so the model can differ between runs; recording
it is what keeps runs comparable). `box` is the confusion-matrix cell.

| run_id | task | gate verdict | truth (oracle) | box | wall_s (copilot) | cost | model |
|---|---|---|---|---|---|---|---|
| control2-lazy | X1 | PASS | wrong | FALSE_RELEASE | 0 | unknown | (planted by hand) |
| run-01 | X1 | NEEDS_HUMAN | oracle_error | escalated | 127 | 16.2 AIC | claude-haiku-4.5 (Auto) |
| run-01b | X1 | PASS | correct | good_pass | 127 | 16.2 AIC | claude-haiku-4.5 (Auto) |

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
