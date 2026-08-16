# X1 — change log for the task card

The task card is what the AI is measured against, so every change to it is a
change to the experiment. Record each one here: what changed, why, and which
runs used which version. This is the scaffolding's A11 idea (versioned task
specifications) done with git and a table instead of a registry.

| Version | Commit | Used by runs | What changed |
|---|---|---|---|
| v1 | `a47f02f` | run-01, run-01b | Original card. |
| v2 | `d1d7d5f` | run-02 onward | Added an **Environment** section; "Done when" now names the venv interpreter and requires a reinstall. |

## v1 → v2 — the change, and why

### What run 1 revealed

Run 1 (Copilot CLI, Auto → claude-haiku-4.5) made every *edit* correctly —
`setup.py`, the import in `slugify/slugify.py`, `README.md`, `tox.ini` — and
then reported "82 passed". The gate, re-running the tests in the workbench
venv, found the tests **could not run**: `ModuleNotFoundError: No module named
'unidecode'`. Verdict NEEDS_HUMAN.

Both statements were true. Copilot had run `python -m pytest`, and on this
machine `python` resolved to the system interpreter, where `unidecode`
happened to be installed. The gate used the workbench venv, where it was not.
The two were looking at different environments. And Copilot had never run
`pip install` — it changed the *declaration* in `setup.py` and stopped, as if
declaring a dependency installed it.

A human installed the package (one `pip install`), re-ran the gate as
run-01b: PASS on all six checks; hidden oracle 15/15; good_pass.

### The judgement call

Two things were ambiguous in the v1 card, and both are *the card's* fault, not
the AI's:

1. **`python` was underspecified.** "Run `python -m pytest`" meant one
   interpreter to Copilot and another to the gate. A task card that lets the
   executor and the gate disagree about which environment is under test is a
   broken experiment, not a hard task.
2. **The card never said "install what you declared".** Whether an AI does
   this unprompted is a genuinely interesting question — but it is a *different*
   question from "can it do the backend swap", and v1 mixed the two. v2
   separates them by stating the environment step explicitly.

### Exactly what changed

```diff
+## Environment
+
+Use the project's virtual environment for every command, not the system
+Python: `../venv/bin/python` (relative to this repository).
+
+Declaring a dependency in `setup.py` does not install it. After changing
+`setup.py`, reinstall the package so the environment matches what you
+declared: `../venv/bin/pip install -e .`
+
 ## Done when

-- The existing test suite passes: `python -m pytest test.py -q`
+- The package is reinstalled and the existing test suite passes **in the
+  project's virtual environment**: `../venv/bin/python -m pytest test.py -q`
 - `grep -rn text_unidecode slugify/ setup.py` returns nothing.
```

Nothing about the task itself changed. The trap (backend divergence on `₹500`,
`♥ love`, …) is unchanged and still unmentioned. The oracle is unchanged.

### What this means for comparing runs

Run 1's rows and run 2's rows measure slightly different things: v1 measured
"does the AI do the swap *and* think to provision it"; v2 measures "does the AI
do the swap when told the environment". Both are legitimate. They should not
be averaged together as if they were the same task — which is why the version
column exists in this file and why `RUNLOG.md` keeps run-01 and run-01b as
their own rows with a note.

### The rule going forward

Change the card only for one of two reasons: (a) it was ambiguous in a way that
made the executor and the gate disagree, or (b) the task itself is being
deliberately changed. Never change it to make a run pass. When it changes,
add a row above and bump the version, so every row in `RUNLOG.md` can be
traced to the exact card the AI saw.
