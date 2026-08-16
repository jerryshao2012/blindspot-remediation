---
name: release-gate
description: Independently verify a candidate code change and return PASS, FAIL, or NEEDS_HUMAN. Use after making any code change and before declaring the task done. Runs the repository's tests, a coverage floor, type checks, lint, a secret scan, and a scope check, all fail-closed. Do not use it to decide what to change; use it only to judge a change already made.
---

# release-gate

You have just made a candidate change to a repository. Do NOT judge it yourself.
Run the independent gate and report its verdict verbatim.

## Steps

1. Run the gate against the working tree:

       bash <blindspot-repo>/demo/gate/gate.sh <repo_dir> <venv_dir>

   `<repo_dir>` is the repository you changed; `<venv_dir>` is the virtual
   environment whose `python` can import the package under test.

2. Read the last lines. The gate prints one line per check and then
   `VERDICT: PASS`, `VERDICT: FAIL`, or `VERDICT: NEEDS_HUMAN`.

3. Report the verdict and the check table to the user exactly as printed.
   Do not soften, summarise away, or re-interpret a FAIL or NEEDS_HUMAN.

## Rules

- The gate's verdict is final for this task. If it says FAIL, the task is not
  done; say so. If it says NEEDS_HUMAN, a check could not run — say which one
  and stop; do not attempt to "fix" the gate so it passes.
- Never modify `test.py`, the gate script, or the evidence files to change
  the outcome. Changing the evidence is not the same as fixing the change.
- Never claim a check passed that the gate did not run.
