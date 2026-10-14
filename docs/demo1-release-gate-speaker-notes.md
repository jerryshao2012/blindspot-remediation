# Demo 1 — Live demo speaker notes

Six minutes for the demo itself, accompanying slide 3 of [the executive deck](demo1-release-gate-executive.html). Start the clock when switching to GitHub Copilot.

## 1. Introduce the skill — 0:00–0:50

**Open:** `release-gate/skills/release-gate/SKILL.md`.

“Let me show how Release Gate works using a simple Python dependency migration.

In this example, we’re updating a package called python-slugify.

But the dependency update itself isn’t the interesting part.

What’s interesting is how we evaluate AI-generated code changes using policy and evidence.

I sometimes describe Release Gate as insurance for AI-native software delivery.

That’s exactly the role Release Gate plays.

We still want the AI moving fast and generating code, but before we trust the output, we want governance, policy checks and evidence.

Release Gate is delivered as a skill, so it can work with code assistants like BMO GitHub Copilot or be invoked from the command line in any BMO CI/CD pipeline.

Let’s look at the Release Gate skill running inside VS Code.”

The agent helps coordinate the work, but the agent does not make the release decision. Release Gate independently evaluates the change and produces the verdict.

Elevate your voice slightly:

“The key idea is that we’re not trusting the AI. We’re trusting policy and evidence.”

**Transition:** “Let’s look at the policy that governs those decisions.” Close GitHub Copilot.

## 2. Show the contract — 0:50–1:40

**Open:** `release-gate/demo/python-slugify/workbench/python-slugify/.release-gate.yaml`.

“This file is the release contract for the repository.

It defines what is allowed, what is prohibited, and what requires human review.

For this demo, the approved scope is intentionally narrow. The candidate can update the dependency, but it must stay within those boundaries.

One example is test.py. That file is protected.

We don’t want an AI changing the tests that are used to evaluate its own work.

That’s a little like letting students write their own exam and grade it themselves.

Surprisingly, everybody gets 100%.

You’ll also see that changes to the release policy itself require human review.

Otherwise a candidate could simply rewrite the rules and approve itself.

Everything Release Gate does is evaluated against this contract.”

**Transition:** “Now let’s see how the gate responds to different types of changes.”

## 3. Invoke the skill and show three verdicts — 1:40–3:20

**First show:** Terminal invocation using the prepared workbench repository.

“I’m starting a Release Gate evaluation here.

While that runs, I’ll show three examples.”

**Open:** `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-01-automated-verification.log`.

### PASS

“In the first example, the candidate stays within the approved scope.

Required checks pass, policy requirements are satisfied, and the gate returns PASS.

This is the expected path for a compliant change.”

### FAIL

“In the second example, all technical checks pass.

But the candidate modified the protected test.py file.

Even though the tests are green, the policy was violated.

Release Gate returns FAIL.

This demonstrates that passing tests alone is not enough.

If that were enough, every engineer would only show the green checkmark and hide the rest of the story.”

### NEEDS_HUMAN

“In the third example, the candidate attempts to modify the release policy.

Instead of automatically accepting or rejecting the change, Release Gate escalates it for human review.

That’s our human-in-the-loop control.

When somebody tries to change the rules themselves, that’s usually a good time to involve a human.”

**Transition:** “Now let’s look at a complete end-to-end execution.”

## 4. Walk through the actual online run — 3:20–5:10

**Open:** `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-02-online-pass.log`. Use bookmarks instead of scrolling.

“The previous examples were prepared scenarios.

This is an actual execution transcript.

Rather than reading the entire log, I want to focus on four stages.

First, readiness checks validate the environment.

Second, Release Gate establishes a trusted baseline.

Third, the policy is validated.

Finally, the candidate is evaluated against the configured rules.”

Raise energy here:

“This is where Release Gate becomes more than a traditional CI/CD pipeline.

Traditional pipelines are very good at answering: ‘Did the checks pass?’

Release Gate is designed to answer a harder question: ‘Should I trust this change?’”

At `VERDICT: PASS` and `RESULT:`:

“Here we see the final verdict: PASS.

The run also produces an evidence package that can be reviewed later for audit and traceability.”

**Then open:** `release-gate/demo/python-slugify/logs/RUN-LOG-2026-09-02-online-pass.md`, focusing on **Outcome** and **Online Interpretation**.

“This report provides the interpretation.

PASS does not mean the code is perfect.

It means the change satisfied the policy and technical requirements defined for this repository.”

**Transition:** “Let’s finish by looking at the evidence that supports that decision.”

## 5. Inspect the evidence and close — 5:10–6:00

**Open:** the `result.json` printed by the September 2 log’s `RESULT:` line.

“This is the machine-readable decision record.

It contains the verdict, reasons, changed files and validation results.

In other words, it explains why the gate reached its conclusion.”

**Then open:** `manifest.json` from the same run directory.

“The manifest provides traceability.

It connects the evaluated change, policy, artifacts and supporting hashes.

That creates a tamper-evident record of what was actually evaluated.”

Raise your voice and slow down:

“To wrap up, we followed the chain from policy to evaluation to evidence.

My simple takeaway is this:

Release Gate is like insurance for an AI-native SDLC.

Hopefully you never need it.

But you’re very happy it’s there when something unexpected happens.

And this is where Assurance Intelligence comes in.

Traditional automation tells us whether checks passed.

Assurance Intelligence helps determine whether we have enough evidence to trust the decision.

The next question is: How do we measure whether those governance controls are actually working?

That’s what Tibor will cover through metrics and engineering scorecards.

Tibor, over to you.”
