# Demo 1 — Live demo speaker notes

Seven minutes for the demo itself, accompanying slide 3 of [the executive deck](demo1-release-gate-executive.html). These notes cover only the demo, not the full presentation. Start the clock when switching to Copilot.

**Demo scope:** The slides describe the newer Release Gate Assurance design; this walkthrough still uses the existing September 1–2 deterministic gate recordings. No updated assurance run logs are available for this demo. Follow the sequence below rather than slide 3’s newer `assure` sequence: show the gate policy, the recorded verdicts and the original evidence package. Do not present conceptual coverage, assurance dispositions or a second receipt as recorded results.

## Prepare the screens

All paths below are relative to the repository root on the demo machine. Pre-open the skill, active policy, both original `.log` files, both explanatory `.md` reports, and the September 2 evidence package. The `.log` files record execution; the `.md` files explain how to read and understand that execution.

The September 1 verification contains three independent scripted controls and separate oracle assessments. The September 2 online PASS is a known-good control patch replay without hidden oracle grading. Use the saved recordings as the default walkthrough. A fresh deterministic invocation is optional only if the demo environment is already prepared; identify it separately and do not depend on it for timing. Keep slow setup and patch generation outside the seven-minute walkthrough.

The assurance policy and conceptual mappings may be discussed as newer design context, but they are not required demo tabs. Do not look for `GATE_VERDICT`, `ASSURANCE_DISPOSITION`, conceptual assessment fields or `gate_result_path` in these historical receipts.

## 1. Introduce the skill — 0:00–1:15

**Open:** `release-gate/skills/release-gate/SKILL.md` in GitHub Copilot.

“The slides describe Release Gate Assurance: evaluators produce evidence, policy determines the outcome, and the release owner authorizes release.

This recorded python-slugify demo shows the execution foundation: explicit release rules, configured checks and traceable evidence. It predates the Conceptual Diversity Evaluator integration.”

“This skill tells the agent how to invoke that foundation.

It specifies an explicit baseline and exact result reporting. The agent coordinates execution; the gate produces the verdict under the configured policy.

Graphify can provide supporting context about dependencies and change effects. It was not a formal gate check in the recorded run.”

## 2. Show the contract — 1:15–2:30

**Open:** `release-gate/demo/python-slugify/workbench/python-slugify/.release-gate.yaml`.

Show the active generated workbench policy. `release-gate/demo/python-slugify/assets/.release-gate.yaml` is its source template.

“This is the repository’s release contract. It defines allowed changes, forbidden changes, and changes requiring human review.

The dependency migration has an explicit scope. Modifying test.py is forbidden because the candidate must not change the tests used to judge its own work.

Changing the policy itself requires human review because that changes the acceptance rules.”

## 3. Explain invocation and show three verdicts — 2:30–4:30

**First show:** The skill’s deterministic `run --base release-gate-demo-base` invocation. Explain it without starting a new run by default. This demo uses `run`, not the newer `assure` workflow shown on the slide.

“The gate evaluates a candidate against an explicit trusted baseline. These saved controls show its response to three independent candidates. We are reviewing recorded execution.”

**Optional prepared live invocation:** In `release-gate/demo/python-slugify/workbench/python-slugify`, invoke the skill with `run --base release-gate-demo-base` using the host’s skill syntax. Say explicitly that it is a separate, fresh deterministic run; continue with the saved controls while it executes.

**Open:** `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-01-automated-verification.log`.

- **2:50–3:15:** Find `VERDICT: PASS`. “The approved change passes the configured checks and receives PASS.”
- **3:15–3:50:** Find `VERDICT: FAIL`. “The configured checks are green, but this candidate also modifies protected test.py. The gate rejects it. Green checks alone are insufficient.”
- **3:50–4:20:** Find `VERDICT: NEEDS_HUMAN`. “This candidate changes the policy itself. The gate escalates before executing the checks, which are explicitly marked SKIPPED.”

**Then open, 4:20–4:30:** `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-01-automated-verification.md`, at **Control Summary**.

“This report explains the raw output. The oracle assessment is an independent evaluation of these controls, separate from the gate verdict.”

If you started the optional live run, identify its output as a separate new run. Otherwise, keep the entire walkthrough labelled as saved execution. Never describe a saved result as live.

## 4. Walk through the online execution — 4:30–6:00

**Open:** `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-02-online-pass.log`.

“We’ve seen the three control outcomes. This is the original terminal transcript from a separate September 2 online run. It replayed a known-good control patch.”

Point to readiness, baseline setup, policy validation, `VERDICT: PASS`, and `RESULT:`. Use search bookmarks rather than reading every line.

“Here are the actual commands and their output. The gate reports PASS and prints the location of the evidence generated by this run.”

**Then open:** `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-02-online-pass.md`, at **Outcome** and **Online Interpretation**.

“The original log records execution. This companion report explains it. The three checks—tests-and-coverage, task-consistency and types—passed. No hidden oracle grading was performed in this online run. PASS means the configured policy was satisfied; behavior outside those checks remains unverified.”

**Bridge to the updated slides:** “The newer Conceptual Diversity Evaluator asks whether evidence covers the reviewed concepts and where shared lineage or gaps limit support. It produces findings before the final assurance decision; policy owns that decision. This September recording does not contain that assessment.”

Do not infer conceptual coverage from the number of passing checks, or describe the historical PASS as an assurance disposition.

## 5. Inspect the evidence and close — 6:00–7:00

**Open:** the exact `result.json` printed by the September 2 log's `RESULT:` line. On the original Windows demo machine:

```text
C:\projects\blindspot-remediation\release-gate\demo\python-slugify\workbench\python-slugify\.release-gate\runs\20260902T153230Z-0b1d3f349b56\result.json
```

**Then open:** `manifest.json` in that same run directory. Keep `trace.json` available for questions about execution detail.

“Start with the verdict and reason codes, then inspect the changed paths and each configured check’s status. Anything skipped or errored remains unverified.

The manifest and hashes connect the evidence to the candidate and configuration evaluated in this run. Together, they provide a traceable, tamper-evident record.

A PASS covers the configured policy. It does not automatically authorize a merge or deployment.

We’ve followed the chain from agent instructions and release contract to execution, verdict, and inspectable evidence. The newer assurance design builds on this foundation by adding conceptual evaluation and a policy-owned assurance disposition. Those additional results are not part of the recording shown today.”

**Evidence preparation:** Have this exact September 2 package available on the demo machine, or copy the complete package beforehand. Other local control-run evidence is from separate runs and must be labeled accordingly. If the package is unavailable, show the recorded `demo.py inspect` output in the original log and explicitly describe it as recorded output, not a direct inspection of the JSON package.

## If asked about the newer assurance flow

Keep this explanation brief; it is design context, not another demo step.

“The newer `assure` workflow runs the deterministic gate once, verifies its evidence, and assesses conceptual coverage only after an eligible PASS. The Conceptual Diversity Evaluator reports support, shared lineage, uncertainty and gaps; it is not a standalone release gate.

Advisory mode records findings without downgrading PASS. Enforce mode changes PASS to NEEDS_HUMAN when assurance is insufficient or unavailable. An assurance-policy edit also escalates PASS in either mode. Existing FAIL and NEEDS_HUMAN verdicts are preserved.

That workflow emits a separate assurance receipt linked to the deterministic result. Our September recordings demonstrate the deterministic result only. Adaptive evidence acquisition remains a proposed extension.”
