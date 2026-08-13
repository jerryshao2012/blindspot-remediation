# Sliding-Window Rate Limiter — a worked example of a release gate

This is a small library with a large test and analysis chain around it.

The library is not the point. The chain around it is the point.

The chain asks one question: **is there enough evidence to release this code?**

This document uses Simplified Technical English (ASD-STE100).

---

## Quick start

You need Python 3.12 or later. The demo was last run on Python 3.14.3.

```bash
cd demo-rate-limiter
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
./tools/gauntlet.sh
```

The first command makes a virtual environment. The second command installs the
tools **and** the package. The third command runs every check.

If all checks pass, the last line is:

```
=== gauntlet: all layers green ===
```

If a check fails, the script stops at that check. It does not continue.

---

## What the gauntlet does

`tools/gauntlet.sh` runs each layer in order. Each layer can find a fault that
the other layers cannot find.

| Layer | Question it asks |
|---|---|
| tests + coverage | Does the code do what `spec.md` says? Did the tests touch every line? |
| types | Do the types agree? |
| lint + format | Is the code too complex to review? Is it formatted? |
| supply chain | Do the dependencies have known faults? |
| must-not scans | Is there a secret in the code? Does a test use the real clock? |
| mutation | If I break the code on purpose, do the tests complain? |
| real execution | Does it work with a real clock, not a test clock? |

The mutation layer is the most important one. Tests that pass only prove that the
tests pass. Mutation analysis puts faults into the code and asks if the tests
find them. If the tests do not complain, the tests are weak.

---

## The gauntlet fails closed

A check that breaks is a failure. It is never a pass.

Look at `must_not_match` in `tools/gauntlet.sh`:

- `grep` gives 1, thus it found nothing. This is the only pass.
- `grep` gives 0, thus it found a forbidden pattern. This is a failure.
- `grep` gives 2 or more, thus the check itself broke. This is also a failure.

This matters. A check that cannot fail gives you no information, but it looks
green. `evidence.md` records that this repository had exactly that fault:
`tools/mutants.py` counted any non-zero exit code as a kill, thus a usage error
looked like a success.

---

## Files

| File | Content |
|---|---|
| `spec.md` | what the code must do, with Gherkin scenarios |
| `src/ratelimiter/` | the code |
| `tests/test_ratelimiter.py` | one test for each scenario |
| `tests/test_properties.py` | two rules that must hold for random inputs |
| `tools/gauntlet.sh` | runs every layer |
| `tools/mutants.py` | mutation analysis |
| `tools/source_state.sh` | prints the commit and a hash of the source |
| `examples/demo.py` | runs the limiter with a real clock |
| `evidence.md` | the result of the last full run |

---

## What this demo does not do

- It does not call an AI.
- It does not write code.
- It does not decide to deploy.

It only collects evidence about code that already exists, and it reports what it
found. A person makes the release decision.

---

## Known limits

`evidence.md` records these. Read that file before you trust a result.

- The specification, the tests, the code, and the evidence have one author. No
  independent person reviewed them. This is the correlated-author problem, and
  it is the fault this type of gate exists to find.
- The library is not safe for use by more than one thread.
- The mutation analysis uses a written procedure in `tools/mutants.py`, not a
  general tool.
