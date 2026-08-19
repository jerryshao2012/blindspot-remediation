---
name: release-gate
description: Use when evaluating a repository release candidate, checking release readiness, or reporting PASS, FAIL, or NEEDS_HUMAN from a committed .release-gate.yaml policy.
---

# Release Gate

Use the installed `release-gate` CLI as the only decision engine. This skill
invokes and reports the gate; it does not create policy.

## Run

1. Confirm `release-gate` is installed and the target is a Git worktree.
2. Require the user or surrounding workflow to identify the base revision.
3. Confirm `.release-gate.yaml` exists in that base revision. If the CLI or
   committed policy is missing, stop and report the missing prerequisite.
4. Run from any directory with explicit paths:

   ```text
   release-gate run --repo <repo> --base <ref>
   ```

5. Read the `RESULT:` path printed by the command, then parse `result.json`.
   Treat exit codes 0, 1, and 2 as completed gate outcomes, not tool failures.
6. Report `verdict`, `reason_codes`, and every configured check in declaration
   order with columns `id`, `mode`, `severity`, `status`, and `reason_codes`.
   Preserve the exact verdict: `PASS`, `FAIL`, or `NEEDS_HUMAN`.
7. Link the evidence directory and say that local evidence is tamper-evident,
   not immutable. State that `PASS` means only that the recorded configured
   policy was satisfied; it does not merge or deploy.

## Integrity rules

- Do not edit `.release-gate.yaml`, launchers, source, or evidence to obtain a
  different outcome.
- Do not retry automatically after any completed verdict.
- Do not reinterpret, suppress, upgrade, or downgrade `result.json`.
- Do not convert `NEEDS_HUMAN` into `FAIL` or `PASS`.
- Do not claim sandboxing, security review, merge approval, or deployment
  authorization beyond the configured checks.
- For exit 3, report invalid input/configuration and no verdict. For exit 4,
  report an internal engine failure and no verdict. Do not fabricate a result.
