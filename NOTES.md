# Notes to discuss later

This file keeps the open questions and the findings that we must not forget.

It uses Simplified Technical English (ASD-STE100).

Each note has an identifier. Use the identifier when you speak about the note.

Move a note to the "Closed notes" section when you make a decision. Do not delete it.
The record of the decision has value.

---

## N-2 — Two different package names exist for the same system

**What we found.**

The A-series gives twelve Python packages. Their names start with `ai_engineering_`.
Examples are `ai_engineering_contracts` and `ai_engineering_release_gate`.

The B-series gives one Python package. Its name is `l1_automation`.

`prompt_truncate` also specifies `l1_automation`.

The `l1_automation` code does not import the `ai_engineering_` code at any point.

**Why this is important.**

You cannot install both schemes and get one system. You must select one name scheme
before you write new code. If you do not select one, the two halves stay separate.

**What to do.**

Select `l1_automation`. Two of the three sources agree on it, and `prompt_truncate`
is the plan for the demo.

---

## N-3 — Do not put the artifact identifier in a Python package name

**The question.**

Can we call the Python packages `A1`, `B4`, and so on?

**The answer.**

Use the identifier in the directory name. Do not use it in the Python package name.

**Why.**

1. A package name is part of the interface. Component A2 does
   `from ai_engineering_contracts import ...`. If the name becomes `A1_shared_contracts`,
   then every import contains an artifact identifier. B6 tells us to put all the code in
   one package. At that time, all of these imports become incorrect.

2. macOS does not usually see a difference between `A1` and `a1`. Linux does. This makes
   errors that you find only on the build machine.

3. PEP 8 asks for lowercase package names. Also, `A10` sorts before `A2`.

**Status.**

This is the rule that the repository uses now. Directory names keep the identifier.
Package names stay descriptive.

---

## N-4 — `prompt_truncate` is the plan for the demo

**What we found.**

`prompt_truncate` specifies a smaller repository. The repository stops at
`GateDecision`. It does not deploy code. It does not measure code after release.

It also specifies a connector to an LLM through an API. The configuration uses these
environment variables:

    L1_LLM_BASE_URL
    L1_LLM_API_KEY
    L1_LLM_MODEL

The interface is compatible with OpenAI.

**Why this is important.**

Azure OpenAI supplies an interface that is compatible with OpenAI. Thus your GPT-4.1
and GPT-5.1 access fits this design. You do not need a different connector.

The prompt also asks for a `DeterministicModelClient` for the tests. Thus the tests run
without an API key.

**What to do.**

Use this prompt as the specification for the demo. Do not design a new one.

---

## N-5 — The same provenance failure occurs again and again

**What we found.**

Three times, a governing document arrived in more than one version. No version had a
date, a version number, or a record of changes.

1. `A10 (version x)` and `A10 (version y)`. The two files are the same, except for one
   empty line at the end. Copilot made both. Nobody knew which one was newer.
2. A third copy of the Component 10 document arrived with the label `A12`. This label
   was incorrect.
3. `prompt_AB.txt` and `prompt_AB_.txt`. These two files are **not** the same. One of
   them adds `EvidenceBundle` to the list of shared contracts. The other one does not.

**Why this is important.**

Components 4 and 11 exist to prevent this problem. Component 4 keeps the evidence.
Component 11 gives each specification a version and a hash.

The third example is the strongest one. The two files give different instructions. If
you use the older file, the reconstructed repository loses a shared contract.

This is a true example, from this project, with a date. It is better than an example
that you invent.

**What to do.**

Use this in the presentation. It shows the problem before it shows the solution.

---

## N-6 — Where you measure decides what you can measure

**What a manager told us.**

One task arrives. The system handles it. You accumulate approximately 10 tasks, and
then you measure. The flow of tasks is the unit, not the time. Continuous monitoring is
not part of this flow. A gate threshold such as 80% or 70% is an arbitrary number. It
becomes meaningful only when you compare it with the true performance.

**This is correct.** It agrees with the design. B2 records the threshold problem as
NI-09, with the status OPEN.

Two points need more detail.

**First. The quantity of tasks controls what you can say.**

B5 contains the calculation. If no task fails, the result is:

    10 tasks    ->  the true failure rate can still be 27.8%
    30 tasks    ->  the true failure rate can still be 11.4%
    100 tasks   ->  the true failure rate can still be 3.7%
    1000 tasks  ->  the true failure rate can still be 0.4%

Thus 10 tasks with no failure agree with a system that fails one time in four. Select
the quantity of tasks from the accuracy that the decision needs.

**Second. Production cannot measure both types of error.**

- The gate says PASS and the code fails in use. You learn this. It is a false release.
- The gate says PASS and the code operates correctly. You learn very little. The gate
  can be correct, or the gate can be lucky.
- The gate says FAIL and the gate was incorrect. **You never learn this.** The code did
  not go to production. Thus nothing occurred.

The offline benchmark knows the correct answer for each case, in both directions,
because it holds the hidden answers.

Thus the two measurements do different work:

    offline benchmark  ->  sets the threshold. Sees both types of error.
                           Quick and repeatable. But the tasks are artificial.

    production         ->  shows if the benchmark was realistic. Real data.
                           But slow, infrequent, one direction only, and mixed
                           with other causes.

Calibrate with the benchmark. Confirm with production. If production is much worse than
the benchmark, then the benchmark was not representative. That is a fault in the
benchmark, not a fault in the AI.

**What to do.**

Show both measurements in the presentation. Do not show only one.

---

## N-7 — The two services have different duties

**What a manager told us.**

`ChangeExecutionService` changes the code. `ReleaseGateService` is the live guardrail.

**Why this is important.**

This gives each service a different requirement:

- The guardrail operates on every change. Thus it must be quick and economical.
- The offline measurement operates sometimes. Thus it can be slow and expensive.

Do not give the guardrail the work of the offline measurement.

---

## N-8 — The tool must answer three questions, not two

- **Is this project healthy?** A check of the whole repository.
- **Is this change safe?** The gate, applied to one difference. Needs a base revision.
- **Is the gate any good?** Without this, the threshold is a number that a person
  selected. A team can see green on each change and learn nothing.
- **Where the answers come from:** a team does not need to build an artificial
  benchmark. Their history has the answers. Run the gate on the last 200 merged
  changes, then look at which changes were reverted or corrected soon after. This
  gives the false-release rate and the false-block rate on their own code.
- **The limits:** a revert is good evidence, a correction is weak evidence, an
  incident is rarely from one change only. Old changes may not build today. The
  quantity of incidents is small, thus the uncertainty is large. History shows the
  bad changes that went out, but it cannot show the good changes that the gate
  stopped.
- **Result:** the backtest gives a threshold that is better than arbitrary. It does
  not give a calibrated threshold.

---

## Closed notes

### N-9 — Reusable gate home (closed 2026-08-18)

**Decision.** The reusable implementation lives in
[`release-gate/`](release-gate/) as an independent Python CLI plus portable
skill. Each adopting repository owns a committed `.release-gate.yaml`.

**Coexistence.** `demo/gate/gate.sh` and its skill remain unchanged for the X1
walkthrough. `A3-release-gate-service` remains auditable historical source
material with known defects. The new product imports neither one, and no
plugin or host-specific adapter is part of v1.

### N-1 — The main branch already contains a release gate that runs

**What we found.**

The `main` branch was not empty. It contained `release-gate/demo/rate-limiter/`, a small library
with a full test and analysis chain: a spec with Gherkin scenarios, a gauntlet script
that ran tests, coverage, type checks, lint checks, and fail-closed forbidden-pattern
scans, scripted mutation analysis, property tests, and an evidence report. The clock
was an injected value, thus the tests did not wait.

This was the ReleaseGateService idea, but it ran. The A-series and the B-series give a
large architecture, and most of it does not run.

**The question.** Decide if the demo starts from this code or from the A/B artifacts.

**Decision (2026-08-16).** Start from the A/B/E scaffolding only. The demo is removed
from the repository. The gate for the new plan will be built as a fresh skill, not from
the demo's gauntlet. The demo stays available in the git history. To restore it:

    git checkout $(git log --diff-filter=D --format=%H -1 -- demo-rate-limiter)^ -- demo-rate-limiter
