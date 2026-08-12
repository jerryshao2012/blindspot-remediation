# DESIGN-RATIONALE.md

## B3 — Design Rationale, Architectural Decisions, Assurance Philosophy, and Open Questions

**Document status:** POC architecture rationale  
**Intended audience:** Platform engineers, AI engineers, data scientists, evaluation scientists, software engineers, reviewers, and future maintainers  
**Relationship to other B-series artifacts:**

- **B1** defines the canonical shared contracts.
- **B2** identifies capabilities that are deliberately unimplemented, abstracted, or dependent on enterprise input.
- **B3**, this document, explains **why the architecture has the shape it does**.
- Later B-series work will wire the components together, exercise an end-to-end X1 capability, reconcile configuration, and produce the final repository README.

---

# 1. Purpose of This Document

This repository is not intended merely to demonstrate that a large language model can generate code.

That capability already exists.

The more difficult engineering question is whether a narrowly scoped class of routine engineering work can be automated in a way that is:

- measurable;
- independently evaluated;
- reproducible;
- evidence-producing;
- bounded by policy;
- capable of abstaining or escalating;
- statistically qualified at the platform level;
- observable after deployment;
- economically measurable;
- understandable by humans.

The first proof of concept therefore deliberately separates:

```text
GENERATING A CHANGE

from

DECIDING WHETHER THAT CHANGE IS ACCEPTABLE

from

MEASURING WHETHER THE AUTOMATION CAPABILITY ITSELF IS RELIABLE.
```

Those are three different questions.

They correspond primarily to:

```text
Component 2
ChangeExecutionService

Component 3
ReleaseGateService

Component 5
EvaluationCampaignRunner
```

The architecture also separates execution, evidence, orchestration, specifications, workflow integration, operational measurement, and business/economic measurement because each has a different responsibility and trust boundary.

This document records the reasoning behind those decisions.

---

# 2. The Problem We Are Actually Trying to Solve

The motivating use case is automation of a limited class of routine L1 engineering work.

The long-term conceptual flow is approximately:

```text
engineering task
      │
      ▼
AI-assisted / AI-driven implementation
      │
      ▼
independent verification
      │
      ├── PASS
      ├── FAIL
      └── HUMAN_REVIEW_REQUIRED
      │
      ▼
normal engineering/release workflow
```

However, it would be a mistake to begin by asking:

> Can AI replace L1 developers?

That question is too broad to evaluate rigorously.

The POC should instead define one task capability, called **X1**, tightly enough that we can ask:

> Given an approved X1 task specification, can the platform generate a candidate change and determine with useful reliability whether that exact candidate should pass, fail, or be escalated?

The second question is:

> Across a sufficiently representative hidden benchmark, how often does the complete automation pipeline make the correct decision?

Those two questions lead naturally to the distinction between **online release gating** and **offline capability qualification**.

---

# 3. Fundamental Architectural Separation

The central architecture is:

```text
ONLINE — one actual or benchmark engineering change
────────────────────────────────────────────────────

Task Request
     │
     ▼
TaskSpecification / Skill / Policy
     │
     ▼
ChangeExecutionService
     │
     ▼
CandidateArtifact
     │
     ▼
ReleaseGateService
     │
     ├── evidence planning
     ├── independent test synthesis
     ├── static / structural analysis
     ├── deterministic tests
     ├── mutation / adversarial analysis
     ├── uncertainty analysis
     └── gate policy
     │
     ▼
GateDecision
     │
     ├── PASS
     ├── FAIL
     └── HUMAN_REVIEW_REQUIRED
     │
     ▼
external engineering workflow


OFFLINE — development and qualification
───────────────────────────────────────

BenchmarkFactory / validated benchmark corpus
     │
     ▼
hidden benchmark cases
     │
     ▼
EvaluationCampaignRunner
     │
     ├── invokes ChangeExecutionService
     ├── invokes ReleaseGateService
     ├── compares outcome against hidden oracle
     ├── measures false release
     ├── measures false rejection
     ├── measures escalation
     ├── measures task success
     ├── measures token / compute consumption
     └── computes uncertainty
     │
     ▼
Capability Qualification Evidence
```

This separation is one of the most important architectural decisions in the repository.

---

# 4. Why Change Execution and Release Gating Are Separate

`ChangeExecutionService` answers:

```text
Given this authorized task,
what candidate change should be made?
```

`ReleaseGateService` answers:

```text
Given this exact candidate,
is there sufficient independent evidence
to permit it to proceed?
```

Combining these responsibilities would create a major assurance weakness.

For example:

```python
# BAD ARCHITECTURAL PATTERN
#
# The same reasoning process creates the change and then effectively
# declares its own work acceptable.

candidate = model.generate_change(task)

if model.review(candidate) == "looks good":
    release(candidate)
```

This is problematic even if the model is capable.

The generator possesses the assumptions, reasoning patterns, and potential blind spots that produced the candidate.

A second call to the same model is not automatically independent evidence.

The architecture therefore treats independence as something that must be **designed**, rather than assumed.

---

# 5. Independence Does Not Necessarily Mean "Use Another Model"

An important conclusion from the design discussion is that independence is multidimensional.

Possible dimensions include:

```text
MODEL DIVERSITY
different model families or versions

PROMPT DIVERSITY
different roles, instructions, decomposition strategies

EVIDENCE DIVERSITY
tests, static analysis, compiler artifacts, mutation,
property checks, runtime observations

GENERATION DIVERSITY
multiple independently generated tests or hypotheses

REPRESENTATION DIVERSITY
source text, AST, CFG, call graph, type information,
compiler diagnostics

TOOL DIVERSITY
compiler, linter, test framework, mutation engine,
security scanner

TEMPORAL / RUN DIVERSITY
repeated stochastic generations

ORACLE DIVERSITY
different mechanisms for deciding expected behavior
```

Therefore:

```text
different model
```

is useful, but it is not sufficient by itself.

Likewise:

```text
same model + different prompt
```

is some diversity, but should not automatically be treated as strong independence.

The release gate should accumulate heterogeneous evidence rather than depend on a single LLM reviewer.

---

# 6. The Evidence Diversity Mapper

One of the more novel elements of this architecture is the **Evidence Diversity Mapper**.

Its purpose is not simply to generate more tests.

Its purpose is to examine the evidence already planned or generated and ask:

```text
Which important evidence dimensions are represented?

Which are duplicated?

Which are weak?

Which are absent?

Which failure modes are still insufficiently challenged?
```

Conceptually:

```text
CandidateArtifact
       │
       ▼
Evidence Planner
       │
       ▼
Initial Evidence Plan
       │
       ▼
Evidence Diversity Mapper
       │
       ├── behavioral evidence?
       ├── boundary evidence?
       ├── structural evidence?
       ├── mutation evidence?
       ├── negative evidence?
       ├── property evidence?
       ├── security evidence?
       ├── regression evidence?
       └── representation diversity?
       │
       ▼
Coverage / Diversity Gaps
       │
       ▼
Evidence Plan Amendment
       │
       ▼
Evidence Executors
```

The mapper should be viewed as a **coordination layer**, not as an oracle.

It does not decide whether the code is correct.

It helps decide whether the evidence being gathered is sufficiently diverse to support a decision.

---

# 7. Why the Evidence Diversity Mapper Should Not Own the Gate Decision

It may be tempting to give the mapper a final output such as:

```text
Evidence quality score = 92/100
Therefore PASS.
```

That should be avoided.

Evidence diversity and evidence outcome are different concepts.

A candidate could have:

```text
excellent evidence diversity
+
several decisive failing tests
```

and should fail.

Conversely, a candidate could have:

```text
all tests passing
+
very poor evidence diversity
```

and the appropriate result may be:

```text
HUMAN_REVIEW_REQUIRED
```

rather than PASS.

Therefore the architecture should preserve:

```text
EVIDENCE COVERAGE / DIVERSITY

separately from

EVIDENCE RESULTS

separately from

GATE POLICY.
```

---

# 8. Evidence Planner Versus Evidence Diversity Mapper

The planner and mapper have related but different responsibilities.

The **Evidence Planner** asks:

> What evidence should we collect for this task and candidate?

The **Evidence Diversity Mapper** asks:

> Does that proposed evidence portfolio contain enough genuinely different ways of discovering relevant failures?

A reasonable interaction is:

```text
TaskSpecification
       │
CandidateArtifact
       │
       ▼
EvidencePlanner
       │
       ▼
EvidencePlan v1
       │
       ▼
EvidenceDiversityMapper
       │
       ▼
DiversityAssessment
       │
       ├── adequate
       │
       └── gaps
              │
              ▼
        EvidencePlanner
              │
              ▼
        EvidencePlan v2
```

This feedback is bounded.

It must not become an unbounded AI loop attempting to generate evidence forever.

The orchestration policy should enforce explicit budgets.

---

# 9. Deterministic and Non-Deterministic Responsibilities

The release gate contains both deterministic and non-deterministic elements.

That is intentional.

A simplified classification is:

| Function | Typical Character |
|---|---|
| Parse task specification | Deterministic |
| Validate candidate identity | Deterministic |
| Compile/build | Deterministic or environment-controlled |
| Existing unit tests | Deterministic where tests themselves are deterministic |
| Static analysis | Mostly deterministic |
| Type checking | Deterministic |
| AST extraction | Deterministic |
| Test synthesis | Often non-deterministic / AI-assisted |
| Failure-mode hypothesis generation | Often non-deterministic / AI-assisted |
| Evidence diversity analysis | May be hybrid |
| Mutation generation | Often deterministic or seeded |
| Mutation execution | Deterministic |
| Property-test generation | Hybrid |
| Gate threshold application | Deterministic |
| Gate state transition | Deterministic |
| Human-review signal | Deterministically produced from policy/evidence |
| Human review itself | Outside the gate |

The architectural principle is:

> Use AI where semantic reasoning, synthesis, or hypothesis generation adds value. Use deterministic mechanisms wherever the decision can be expressed reliably as code.

AI should expand the evidence search space.

It should not quietly replace deterministic policy.

---

# 10. Why Source Text Alone Is Insufficient Evidence

An LLM can review source code text directly.

That can be useful for:

- intent;
- semantics;
- naming;
- local reasoning;
- documentation;
- suspicious patterns;
- likely defects.

But source text is only one representation of a program.

The gate can obtain additional evidence from:

```text
Abstract Syntax Tree (AST)

type information

compiler diagnostics

control-flow graph

call graph

dependency graph

symbol table

lint findings

code complexity

data-flow information

test coverage

mutation survivors

runtime traces
```

These artifacts can expose facts that are difficult to infer reliably from raw source text.

Therefore the gate should conceptually operate on:

```text
SOURCE
+
STRUCTURAL ARTIFACTS
+
EXECUTION ARTIFACTS
+
GENERATED EVIDENCE
```

rather than:

```text
SOURCE
+
LLM OPINION.
```

---

# 11. Role of the LLM in the Release Gate

AI is particularly useful for generating hypotheses.

Examples:

```text
What could this change break?

Which edge cases are missing?

Which assumptions does this patch appear to make?

What adversarial inputs could invalidate those assumptions?

Which behavioral properties should remain invariant?

What tests would distinguish the intended implementation
from a superficially plausible incorrect implementation?
```

AI can also synthesize candidate tests from those hypotheses.

However, wherever possible, the truth of those tests should subsequently be determined by deterministic execution.

The pattern is:

```text
AI proposes a challenge
        │
        ▼
deterministic environment executes challenge
        │
        ▼
structured evidence
```

This is preferable to:

```text
AI reads code
        │
        ▼
AI says "probably correct"
        │
        ▼
PASS
```

---

# 12. AI-Generated Tests Are Not Ground Truth

A generated test is an artifact.

It is not automatically valid evidence.

AI-generated tests may:

- encode an incorrect interpretation of requirements;
- test implementation details rather than behavior;
- duplicate existing tests;
- fail to cover important boundaries;
- share the generator's blind spots;
- contain bugs;
- produce trivial assertions;
- pass regardless of implementation;
- assume behavior not specified by X1.

Therefore the release gate should evaluate test quality.

Useful test metadata may include:

```text
provenance

generation strategy

evidence category

requirement linkage

determinism

execution result

mutation sensitivity

duplicate/similarity information

structural coverage

behavioral coverage

validation status
```

The Evidence Diversity Mapper can use this information to avoid equating:

```text
100 tests
```

with:

```text
100 independent pieces of evidence.
```

---

# 13. Why Test Count Is a Weak Metric

Suppose an LLM generates 500 tests.

If 450 are slight paraphrases of the same behavioral assumption, the effective evidence diversity may be very low.

Therefore:

```text
N_TESTS
```

should not be interpreted as equivalent to:

```text
N_INDEPENDENT_OBSERVATIONS.
```

This is especially important when computing confidence intervals.

Traditional confidence intervals often assume observations are independent or satisfy particular statistical assumptions.

AI-generated tests can be strongly correlated.

A narrow interval calculated from hundreds of correlated tests can therefore create false precision.

For this reason, the architecture should not treat individual generated tests as the primary independent statistical unit when making platform-level reliability claims.

---

# 14. Where Confidence Intervals Belong

A key design clarification is that there are at least two different kinds of uncertainty.

## Candidate-Level Uncertainty

For one candidate:

```text
Do we have enough evidence to release this exact change?
```

Relevant evidence may include:

```text
test outcomes
mutation results
coverage
static findings
evidence diversity
model disagreement
requirement coverage
```

A confidence interval may occasionally be useful, but it should not become the universal mechanism for candidate gating.

## Platform-Level Uncertainty

Across many benchmark tasks:

```text
How reliable is this automation capability?
```

This is where statistical intervals become especially important.

Examples include uncertainty around:

```text
task success rate

false-release rate

false-rejection rate

human-review rate

pipeline completion rate

cost per successful task
```

The natural statistical unit is often:

```text
BENCHMARK TASK / RUN
```

rather than:

```text
INDIVIDUAL GENERATED TEST.
```

This distinction materially changes the expected token economics of the platform.

---

# 15. Token Consumption — Corrected Architectural View

Early in the design discussion, it might appear that `ReleaseGateService` should consume fewer tokens than `ChangeExecutionService`.

That is not necessarily true.

A sophisticated gate may use AI repeatedly for:

```text
failure-mode generation

independent test synthesis

test diversification

evidence-gap analysis

adversarial analysis

requirement mapping

structural-artifact interpretation
```

Therefore, for difficult candidates:

```text
gate_tokens > change_generation_tokens
```

is entirely plausible.

This is not inherently undesirable.

The relevant question is:

```text
How much assurance value is produced per unit of inference cost?
```

not:

```text
Which component has the smallest token count?
```

---

# 16. Token Budgets Must Be Explicit

Every AI-using component should report resource consumption.

At minimum:

```text
input tokens

output tokens

number of model calls

model identifier

latency

estimated monetary cost where available
```

Preferably also:

```text
reason for call

evidence category

retry count

cache use

generation seed where meaningful

termination reason
```

Token budgets should exist at multiple levels:

```text
per model call

per evidence category

per component

per task

per complete orchestration run

per evaluation campaign
```

This prevents an assurance loop from silently becoming economically unbounded.

---

# 17. Why the Release Gate Should Not Generate Evidence Forever

A theoretical gate could always ask:

```text
Can I generate one more test?
```

The answer is almost always yes.

Therefore completeness cannot be defined as:

```text
no additional test can be imagined.
```

Instead, the gate needs stopping criteria.

Possible stopping conditions include:

```text
required evidence classes satisfied

minimum mutation performance reached

critical requirements exercised

no unresolved high-severity findings

diversity target reached

maximum evidence-generation budget reached

maximum token budget reached

maximum execution budget reached
```

If required evidence cannot be achieved within the allowed budget, the safe outcome may be:

```text
HUMAN_REVIEW_REQUIRED
```

rather than unlimited generation.

---

# 18. Mutation Testing

Mutation testing deliberately modifies code to create plausible defects.

Examples include:

```text
< becomes <=

+ becomes -

True becomes False

boundary condition changes

conditional removed

return value changed
```

The test suite is then executed against these mutants.

If tests detect the introduced defect, the mutant is:

```text
KILLED
```

If the mutant survives, the test suite may have a weakness.

Mutation testing therefore evaluates the **fault-detection capability of the tests**, rather than merely whether tests pass.

---

# 19. Why Mutation Testing Is Valuable Here

This architecture has a special problem:

```text
AI generates candidate
+
AI generates tests
```

The same blind spots may affect both.

Mutation testing introduces deliberately incorrect implementations and asks whether the test portfolio notices.

This provides a different evidence dimension.

Conceptually:

```text
Candidate
   │
   ├── test suite passes candidate
   │
   ▼
Mutants
   │
   ▼
same test suite
   │
   ├── kills meaningful mutants
   └── fails to kill meaningful mutants
```

A test suite that passes the candidate but also passes many meaningful mutants is weak evidence.

---

# 20. Mutation Score Is Not a Complete Correctness Measure

A high mutation score does not prove the candidate is correct.

Mutation operators only represent certain defect classes.

There can also be equivalent mutants: syntactic changes that do not alter observable behavior.

Therefore:

```text
HIGH MUTATION SCORE
```

means approximately:

```text
the tests detect many of the injected defect classes
```

not:

```text
the program is correct.
```

Mutation evidence should therefore be one contributor to the evidence portfolio.

---

# 21. Synthetic Ground Truth and the BenchmarkFactory

For the POC, a benchmark corpus may need to be created partially with AI.

A useful benchmark case may contain:

```text
baseline codebase

known defect or requested change

task description

public task artifacts

hidden expected properties

hidden acceptance tests

known acceptable behavior

possibly a reference patch

expected scope
```

AI can help create these cases.

However:

> AI-generated benchmark cases are not ground truth merely because AI generated both the problem and the answer.

They become useful qualification evidence only after independent validation.

---

# 22. The Hidden Oracle

The automation pipeline must not receive the hidden oracle.

The separation is:

```text
PUBLIC SIDE

baseline repository
task request
approved skill
allowed context
public tests

        │
        ▼
automation pipeline


HIDDEN SIDE

reference expectations
hidden tests
known defect
acceptable behavior
oracle metadata

        │
        ▼
EvaluationCampaignRunner only
```

Otherwise the benchmark risks becoming an exercise in reproducing information that the pipeline was allowed to see.

The hidden oracle therefore belongs to Component 5's trust domain.

---

# 23. BenchmarkFactory Versus EvaluationCampaignRunner

These are different responsibilities.

`BenchmarkFactory` creates or helps curate candidate benchmark cases.

`EvaluationCampaignRunner` evaluates the automation system against validated benchmark cases.

The distinction matters because benchmark construction can involve:

```text
AI generation

human review

defect injection

mutation

case normalization

difficulty balancing

oracle construction
```

while campaign execution should operate against a frozen benchmark definition.

Conceptually:

```text
BenchmarkFactory
      │
      ▼
Candidate benchmark
      │
      ▼
Validation / curation
      │
      ▼
VALIDATED BENCHMARK
      │
      ▼
EvaluationCampaignRunner
```

Only the validated benchmark should support qualification claims.

---

# 24. Why Offline Evaluation Is Separate from Online Release Gating

Online release gating asks:

```text
Should candidate C proceed?
```

Offline evaluation asks:

```text
How trustworthy is the whole automation capability
over a representative population of tasks?
```

Those require different statistical structures.

A single candidate can have extensive tests but tells us little about the population-level false-release rate.

Conversely, a platform may perform well on average but still need to reject a particular candidate because its evidence is inadequate.

Therefore:

```text
candidate assurance
```

and:

```text
capability qualification
```

must not be collapsed into one score.

---

# 25. False Release Is a First-Class Metric

For this architecture, one of the most important platform metrics is:

```text
FALSE RELEASE
```

Conceptually:

```text
Gate says PASS

but

hidden oracle says candidate is unacceptable.
```

This is more important than simple aggregate accuracy because the costs are asymmetric.

A false rejection wastes engineering capacity.

A false release may introduce defective code.

Therefore qualification should report separately:

```text
false-release rate

false-rejection rate

correct-pass rate

correct-fail rate

human-review rate
```

rather than hiding them inside a single accuracy percentage.

---

# 26. Human Review Is an Outcome, Not a Gate Implementation Detail

The release gate should not contain the actual human-review workflow.

It should emit:

```text
HUMAN_REVIEW_REQUIRED
```

when policy determines that automated evidence is insufficient.

Then:

```text
ReleaseGateService
      │
      ▼
GateDecision:
HUMAN_REVIEW_REQUIRED
      │
      ▼
Orchestrator
      │
      ▼
Workflow Integration
      │
      ▼
external human-review system
```

This preserves a clean responsibility boundary.

Component 3 determines:

```text
automation cannot safely resolve this candidate.
```

It does not decide:

```text
which human should review it
where they review it
how approval is recorded organizationally.
```

---

# 27. FAIL Versus HUMAN_REVIEW_REQUIRED

These outcomes must remain distinct.

Use:

```text
FAIL
```

when evidence positively supports rejection.

Examples:

```text
compiler failure

required deterministic test failure

critical static-analysis finding

known regression

decisive security violation

policy prohibition
```

Use:

```text
HUMAN_REVIEW_REQUIRED
```

when evidence is insufficient or ambiguous.

Examples:

```text
conflicting evidence

insufficient evidence diversity

unsupported task characteristic

budget exhausted before assurance target

novel dependency pattern

weak oracle

unresolved model disagreement
```

This distinction allows the system to abstain rather than manufacture certainty.

---

# 28. Technical PASS Versus Release Approval

A further distinction is necessary.

A gate may conclude:

```text
PASS
```

meaning:

```text
the candidate satisfies the technical release-gate policy.
```

That does not necessarily mean:

```text
deploy to production immediately.
```

Enterprise workflow may require:

```text
release approval

change-management approval

scheduled deployment window

segregation of duties

environment approval
```

Therefore the orchestration model includes a state equivalent to:

```text
RELEASE_APPROVAL_REQUIRED
```

when organizational approval remains necessary after technical PASS.

---

# 29. Gate Decisions Must Be Candidate-Bound

A gate does not approve:

```text
PR #123
```

in the abstract.

It approves or rejects an exact candidate.

The assurance identity should therefore include something equivalent to:

```text
task specification hash

baseline commit

candidate commit

candidate artifact hash

gate policy version

evidence references

gate decision hash
```

If the candidate changes, the previous gate decision must not silently carry forward.

Conceptually:

```text
Candidate A
    │
    ▼
PASS

developer pushes Candidate B
    │
    ▼
old PASS invalid for B
    │
    ▼
RE-GATE
```

---

# 30. Evidence Must Be Content-Addressed

Important artifacts should carry a cryptographic content digest such as SHA-256.

Examples:

```text
TaskSpecification

CandidateArtifact

EvidenceArtifact

ExecutionReceipt

GateDecision

Benchmark definition
```

This allows the platform to state:

```text
this decision refers to THESE exact bytes
```

rather than:

```text
this decision refers to something called candidate.py.
```

Content addressing supports:

```text
reproducibility

integrity checking

deduplication

candidate binding

auditability
```

It does not by itself establish semantic correctness or producer trust.

---

# 31. Why Evidence Persistence Is a Separate Component

The release gate should produce evidence.

It should not own the entire persistence architecture.

Separating Component 4 allows:

```text
Component 2
Component 3
Component 5
Component 9
Component 10
```

to all preserve artifacts through a common evidence mechanism.

This also prevents the release gate from becoming an oversized class containing:

```text
test generation
execution
policy
storage
Azure authentication
serialization
retention
query APIs
```

The architecture prefers explicit components with narrow responsibilities.

---

# 32. Execution Environment Is a Separate Component

Generated code should not execute directly inside the process hosting:

```text
ChangeExecutionService
```

or:

```text
ReleaseGateService.
```

Instead:

```text
domain service
      │
      ▼
ExecutionEnvironmentService
      │
      ▼
controlled sandbox
```

This separates:

```text
WHAT should execute
```

from:

```text
WHERE and under what security/resource constraints it executes.
```

The POC Azure implementation can use finite containerized jobs.

The abstraction remains provider-neutral so that a stronger isolation technology can later replace the POC execution mechanism without rewriting domain services.

---

# 33. Change and Gate Execution Should Use Separate Sandboxes

Where practical, the candidate-generation environment and verification environment should be separate.

Recommended pattern:

```text
JOB A
Change execution
     │
     ▼
immutable CandidateArtifact
     │
     ▼
Artifact Store
     │
     ▼
JOB B
Independent gate execution
```

This reduces accidental state leakage.

The gate should not unknowingly inherit:

```text
temporary files

cached state

generated tests

credentials

environment modifications

hidden reasoning artifacts
```

from the change-generation environment.

---

# 34. The Orchestrator Must Be Deterministic

Component 9 coordinates the lifecycle.

Its job is approximately:

```text
receive task

resolve approved capability

invoke change execution

persist candidate

invoke release gate

persist decision

route PASS / FAIL / REVIEW

publish workflow status
```

It should not ask an LLM:

```text
What should I do next?
```

Workflow state transitions should be explicit code.

For example:

```python
# Illustrative design only.
#
# The orchestrator applies a deterministic state machine.
# An LLM is not permitted to invent new workflow states or bypass
# required gate transitions.

if gate_decision.outcome == GateOutcome.PASS:
    next_state = (
        RunState.RELEASE_APPROVAL_REQUIRED
        if release_approval_required
        else RunState.READY_FOR_RELEASE
    )

elif gate_decision.outcome == GateOutcome.FAIL:
    next_state = RunState.FAILED_GATE

elif (
    gate_decision.outcome
    == GateOutcome.HUMAN_REVIEW_REQUIRED
):
    next_state = RunState.HUMAN_REVIEW_REQUIRED

else:
    # Fail explicitly if a future GateOutcome is introduced without
    # updating orchestration policy.
    #
    # Silent fallbacks are dangerous in an assurance-oriented system.
    raise RuntimeError(
        "Unsupported GateOutcome. "
        "Update the deterministic orchestration policy."
    )
```

This is intentionally boring.

That is a feature.

---

# 35. Task Specifications Are Executable Governance Artifacts

Each task type X1 ... Xn should come with a versioned package of governing artifacts.

Conceptually:

```text
X1/
├── task-specification.yaml
├── SKILL.md
├── gate-policy.yaml
├── eval-specification.yaml
└── supporting artifacts
```

The exact repository layout may evolve.

The important concept is that the platform should not rely on a large hard-coded Python statement such as:

```python
if task_type == "X1":
    # 700 lines of special behavior
```

Instead, capability-specific behavior should be driven as much as reasonably possible by versioned specifications interpreted by generic services.

---

# 36. Why the Change Agent Must Not Control Its Own Specification

The task specification defines the agent's authority.

It may determine:

```text
allowed repositories

allowed paths

allowed operation classes

forbidden actions

required evidence

token budgets

gate policy

execution profile
```

Therefore the change-generating agent must not be permitted to silently modify its governing specification.

Otherwise:

```text
agent cannot satisfy gate
       │
       ▼
agent modifies gate requirement
       │
       ▼
agent passes
```

would become possible.

Specifications therefore belong outside the change-agent trust boundary.

---

# 37. Why Skills and Policies Should Be Versioned

An X1 capability may improve over time.

For example:

```text
X1 v1.0
X1 v1.1
X1 v2.0
```

Qualification evidence for v1.0 should not automatically qualify v2.0.

Important changes may include:

```text
new model

new prompt

new skill

new gate threshold

new evidence planner

new mutation strategy

new allowed task scope
```

The platform should therefore preserve version and content identity throughout the evidence chain.

---

# 38. Capability Qualification Must Be Bound to Configuration

A statement such as:

```text
X1 has a 98% success rate
```

is incomplete.

A more meaningful statement is closer to:

```text
X1 capability version C

using ChangeExecution configuration A

ReleaseGate configuration B

model configuration M

task specification S

on benchmark version V

achieved measured result R
with uncertainty U.
```

Changing a material part of that configuration may require requalification.

This is one reason Component 5 must preserve experiment metadata carefully.

---

# 39. Three Layers After Release

The post-release measurement model developed in the design discussion is:

```text
EVALUATION
      │
      ▼
OPERATIONAL METRICS
      │
      ▼
PROCESS / BUSINESS OUTCOMES
```

This is directionally useful.

However, a stronger framework inserts an intermediate layer.

Recommended model:

```text
LAYER 1
Engineering / AI Evaluation

        │

LAYER 2
Operational Technical Metrics

        │

LAYER 3
Process Outcome Metrics

        │

LAYER 4
Business KPI
```

Why?

Because:

```text
service executed successfully
```

does not automatically mean:

```text
mortgage was processed successfully
```

and:

```text
mortgage was processed successfully
```

does not automatically mean:

```text
business value increased.
```

The causal distance grows at each layer.

---

# 40. Layer 1 — Engineering / AI Evaluation

Examples:

```text
candidate correctness

gate result

benchmark task success

false-release rate

false-rejection rate

mutation performance

evidence diversity

token consumption

latency

human-review rate
```

These are the measures most directly attributable to the automation platform.

This is where the strongest causal claims are likely to be possible.

---

# 41. Layer 2 — Operational Technical Metrics

Once released, the changed code operates inside a real environment.

Examples:

```text
execution success rate

runtime exceptions

latency

availability

resource consumption

rollback frequency

incident count

error rate
```

These metrics answer:

```text
Does the released software operate correctly and reliably?
```

They should not automatically be labelled business value.

---

# 42. Layer 3 — Process Outcome Metrics

Examples in a mortgage context might include:

```text
application completion rate

straight-through processing rate

manual intervention rate

rework rate

processing time

queue time

exception resolution time
```

These measures are closer to business activity.

They create an important bridge between technical behavior and business KPI.

---

# 43. Layer 4 — Business KPI

Possible examples include:

```text
cost per processed application

customer conversion

revenue

loss avoidance

employee capacity

customer satisfaction

time to decision
```

At this layer, attribution becomes substantially harder.

Many variables beyond the AI engineering platform affect these outcomes.

Therefore the platform should distinguish:

```text
OBSERVED ASSOCIATION
```

from:

```text
CAUSAL ATTRIBUTION.
```

---

# 44. Why Business Value Should Not Be Hard-Coded into the Release Gate

The release gate asks whether one candidate satisfies technical acceptance policy.

It should not contain logic such as:

```python
if expected_revenue_gain > 1_000_000:
    pass_candidate()
```

unless a future explicitly governed use case genuinely requires such a policy.

Technical assurance and business prioritization are separate concerns.

A technically correct change may have little business value.

A high-value change may still be technically unsafe.

Those dimensions should remain visible separately.

---

# 45. Economic Measurement

Component 8 exists because the automation initiative ultimately has an economic question:

```text
Does this automation produce enough useful engineering work
to justify its total cost and risk?
```

Costs may include:

```text
LLM inference

sandbox compute

storage

monitoring

platform engineering

human review

benchmark maintenance

failed attempts

rework
```

Benefits may include:

```text
reduced contractor effort

reduced cycle time

higher throughput

reduced rework

greater consistency
```

The architecture should initially measure costs before making aggressive savings claims.

---

# 46. Avoiding Naive "FTE Replacement" Arithmetic

A simplistic model might calculate:

```text
100 automated tasks
×
2 historical developer hours
×
hourly rate
=
savings
```

This can overstate value.

Real economic measurement should consider:

```text
human-review effort

platform operating cost

failed automation attempts

tasks that still require L1 work

rework

new supervisory work

benchmark/evaluation maintenance

capacity that is redeployed rather than removed
```

Therefore Component 8 should distinguish:

```text
GROSS AUTOMATION VALUE

from

NET REALIZED ECONOMIC VALUE.
```

Finance alignment is required before claiming realized enterprise savings.

---

# 47. Why Components Should Not Be One Giant Class

A tempting POC implementation would be:

```python
class L1AutomationPlatform:
    def do_everything(self):
        ...
```

That would be faster initially but damaging for this use case.

The platform contains responsibilities with different:

```text
trust levels

failure modes

scaling patterns

statistical roles

security boundaries

owners

test strategies
```

For example, changing gate policy should not require rewriting Azure DevOps integration.

Changing the sandbox technology should not require rewriting benchmark statistics.

Changing business KPI connectors should not affect candidate generation.

Separation therefore has practical value beyond software aesthetics.

---

# 48. But Avoid Excessive Microservice Fragmentation

Logical component separation does **not** imply that every component must immediately become:

```text
separate repository
+
separate deployment
+
separate database
+
separate Kubernetes service.
```

For the POC, several components may live in one repository and even one deployable application.

The important first separation is:

```text
CODE OWNERSHIP / MODULE BOUNDARY / INTERFACE
```

not necessarily:

```text
NETWORK BOUNDARY.
```

A sensible POC may use a modular monolith with explicit interfaces.

Later deployment decomposition can follow observed scaling, security, and ownership requirements.

---

# 49. Main Classes Versus Supporting Classes

It is useful to have recognizable service entry points such as:

```text
ChangeExecutionService

ReleaseGateService

EvaluationCampaignRunner
```

But each should not become a monolithic class.

For example:

```text
ReleaseGateService
      │
      ├── EvidencePlanner
      ├── EvidenceDiversityMapper
      ├── TestSynthesisPort
      ├── StaticAnalysisPort
      ├── MutationAnalysisPort
      ├── ExecutionEnvironmentPort
      ├── GatePolicyEvaluator
      └── EvidenceRepositoryPort
```

`ReleaseGateService` coordinates the release-gating use case.

Supporting classes perform specialized work.

This makes the code understandable to junior engineers while preserving testability.

---

# 50. Dependency Direction

Domain services should depend on interfaces.

Infrastructure adapters implement those interfaces.

Preferred:

```text
ReleaseGateService
       │
       ▼
SandboxRunnerPort
       ▲
       │
AzureContainerAppsJobRunner
```

Avoid:

```text
ReleaseGateService
       │
       ▼
Azure SDK
       │
       ▼
hard-coded Container Apps logic
```

This allows local deterministic testing without Azure infrastructure.

---

# 51. Composition Root

Later B-series work will construct a composition root.

Its responsibility is to answer:

```text
Which concrete implementation satisfies each port
in this environment?
```

For example:

```text
LOCAL TEST ENVIRONMENT

SandboxRunnerPort
    → LocalDeterministicSandbox

EvidenceRepositoryPort
    → LocalEvidenceRepository


AZURE POC

SandboxRunnerPort
    → AzureContainerAppsJobRunner

EvidenceRepositoryPort
    → AzureBlobEvidenceRepository
```

The domain code should not determine this itself.

---

# 52. Why Configuration Must Be External

Values such as:

```text
model deployment

token budget

Azure resource ID

repository ID

task capability

gate threshold
```

should not be scattered through Python source.

Configuration should be:

```text
explicit

validated

versioned where appropriate

environment-specific where appropriate
```

However, an important distinction exists:

```text
INFRASTRUCTURE CONFIGURATION
```

is not the same as:

```text
ASSURANCE POLICY.
```

Gate policy should itself be versioned evidence-bearing configuration, not merely an environment variable someone can casually change.

---

# 53. Release-Gate Policy Must Be Deterministic

Suppose evidence produces:

```text
compiler = PASS

required tests = PASS

mutation score = 0.87

critical static findings = 0

evidence diversity = ACCEPTABLE

unresolved high-severity hypotheses = 0
```

The conversion of those facts into:

```text
PASS
```

should normally be deterministic.

For example:

```python
# Simplified illustrative example.
#
# Real thresholds belong in a versioned GatePolicy and must be
# empirically calibrated before production qualification.

if evidence.compiler_failed:
    return GateOutcome.FAIL

if evidence.required_test_failures > 0:
    return GateOutcome.FAIL

if evidence.critical_static_findings > 0:
    return GateOutcome.FAIL

if evidence.unresolved_high_severity_findings > 0:
    return GateOutcome.HUMAN_REVIEW_REQUIRED

if evidence.diversity_status != "adequate":
    return GateOutcome.HUMAN_REVIEW_REQUIRED

if evidence.mutation_score < policy.minimum_mutation_score:
    return GateOutcome.HUMAN_REVIEW_REQUIRED

return GateOutcome.PASS
```

The LLM may contribute evidence.

It should not silently redefine the policy.

---

# 54. Why Gate Thresholds Cannot Yet Be Declared "Correct"

Values such as:

```text
mutation score >= 0.80

minimum 50 tests

95% confidence

maximum review rate 20%
```

may sound rigorous.

Without empirical calibration they are merely plausible numbers.

Thresholds should ultimately be informed by:

```text
benchmark distributions

failure severity

false-release tolerance

false-rejection cost

task complexity

evidence correlation

historical performance
```

Therefore B2 correctly leaves production threshold calibration explicitly unresolved.

---

# 55. Statistical Discipline

The system should resist a common failure mode in AI evaluation:

```text
large number of measurements
      │
      ▼
small-looking confidence interval
      │
      ▼
false sense of certainty
```

The relevant questions include:

```text
What is the sampling unit?

Are observations independent?

How were benchmark cases selected?

Are repeated runs correlated?

Were thresholds tuned on the same benchmark?

Is the benchmark representative?

Are confidence intervals conditional on benchmark construction?

How are abstentions treated?
```

Statistical code should document these assumptions.

---

# 56. Development Set Versus Qualification Set

Benchmark development should eventually distinguish:

```text
DEVELOPMENT SET

used to:
- debug
- tune prompts
- tune policies
- inspect failures
- choose thresholds
```

from:

```text
QUALIFICATION / HOLDOUT SET

used to:
- estimate final performance
- estimate false release
- estimate uncertainty
- support readiness decisions
```

Repeatedly tuning against the same benchmark contaminates the estimate.

The architecture should therefore preserve benchmark version and split identity.

---

# 57. Repeated Runs

Because AI generation is non-deterministic, a single benchmark execution may not characterize the capability.

For selected cases, Component 5 may run repeated trials.

Example:

```text
X1-001
    run 1
    run 2
    run 3

X1-002
    run 1
    run 2
    run 3
```

This allows estimation of:

```text
run-to-run variability

model instability

gate stability

cost variability

escalation variability
```

However, repeated runs on the same task are not equivalent to independent new benchmark tasks.

Statistical analysis must preserve this hierarchy.

---

# 58. Hierarchical Evaluation Structure

Conceptually:

```text
CAPABILITY
    │
    ├── Benchmark Case 1
    │       ├── Run 1
    │       ├── Run 2
    │       └── Run 3
    │
    ├── Benchmark Case 2
    │       ├── Run 1
    │       ├── Run 2
    │       └── Run 3
    │
    └── Benchmark Case N
```

This structure matters because:

```text
three runs of one task
```

do not provide the same evidence as:

```text
three different tasks.
```

The evaluation implementation should preserve `case_id` and `run_id` separately.

---

# 59. Gate Evaluation and Pipeline Evaluation Must Not Share the Hidden Oracle

A critical anti-leakage rule is:

```text
ReleaseGateService
```

must not see:

```text
hidden benchmark expected outcome.
```

Otherwise Component 5 would no longer be evaluating the real release gate.

The campaign runner should invoke the gate exactly as it would operate online.

Only after the gate decision is complete should Component 5 compare it against the hidden oracle.

Correct:

```text
Candidate
    │
    ▼
ReleaseGateService
    │
    ▼
GateDecision
    │
    ▼
EvaluationCampaignRunner
    │
    + hidden oracle
    │
    ▼
evaluation result
```

Incorrect:

```text
hidden oracle
    │
    ▼
ReleaseGateService
```

---

# 60. Test Synthesis Should Also Avoid Oracle Leakage

When benchmark tasks are executed, test synthesis inside the release gate must only receive information available during a real production task.

It should not receive:

```text
hidden reference patch

hidden acceptance tests

known defect label

expected gate outcome
```

This should be enforced through credentials and artifact boundaries, not merely prompt instructions.

---

# 61. The Gate Is a Safety Boundary, Not a Security Boundary by Itself

The release gate evaluates technical evidence.

It is not sufficient protection against malicious generated code.

Security also requires Component 10 controls such as:

```text
sandbox isolation

least privilege

network restrictions

resource limits

credential restrictions

ephemeral workspace

artifact verification
```

A candidate should be considered untrusted until execution and policy controls permit otherwise.

---

# 62. Generated Code Should Not Receive Broad Credentials

The safest POC rule is:

```text
generated code receives no production credentials.
```

If network access is unnecessary:

```text
deny network access.
```

If future tasks require external resources, introduce narrowly scoped access rather than broad inherited identity.

This is why B2 deliberately postpones a dynamic sandbox credential broker.

---

# 63. Evidence Is More Than Logs

A log might say:

```text
Tests passed.
```

Evidence should be richer.

For example:

```text
which candidate?

which test suite?

which test-suite hash?

which environment?

which runner image?

which policy?

which command?

what exit code?

what outputs?

when?

under which run?
```

Therefore the evidence model should preserve structured receipts and content-addressed artifacts rather than relying only on human-readable logs.

---

# 64. Operational Observability Is Different from Assurance Evidence

OpenTelemetry traces answer questions such as:

```text
Where is the platform slow?

Which service failed?

How many model calls occurred?

Which dependency timed out?
```

Assurance evidence answers:

```text
Why was Candidate C allowed to pass?

Which exact tests were used?

Which mutations survived?

Which policy version made the decision?
```

Both are necessary.

They should not be confused.

---

# 65. Evidence Provenance

Each evidence item should, where practical, record:

```text
producer

run ID

candidate identity

creation time

content hash

tool/model identity

configuration identity

parent evidence
```

This creates an evidence graph.

Example:

```text
CandidateArtifact C
      │
      ├── StaticReport S
      ├── GeneratedTests T
      │       │
      │       └── TestExecution E
      │
      ├── MutationSet M
      │       │
      │       └── MutationResults R
      │
      └── DiversityAssessment D
               │
               ▼
          GateDecision G
```

This structure is much more useful for later analysis than a single scalar gate score.

---

# 66. Why We Do Not Reduce the Gate to One Score

A scalar score is attractive:

```text
Gate Score = 91
```

But it hides failure structure.

Consider:

```text
Candidate A

compiler       PASS
tests          PASS
mutation       95%
security       CRITICAL FAILURE
```

A weighted average might still look high.

That would be unacceptable.

Therefore some evidence dimensions should behave as:

```text
HARD VETOES
```

while others may support:

```text
THRESHOLDS

ESCALATION

CONFIDENCE

PRIORITIZATION.
```

The gate policy must make those semantics explicit.

---

# 67. Evidence Severity

Findings should have severity where meaningful.

A simple conceptual taxonomy could be:

```text
INFO

LOW

MEDIUM

HIGH

CRITICAL
```

However, severity itself should not be blindly assigned by an LLM and treated as fact.

Where severity affects a hard gate, it should ideally be:

```text
derived from deterministic policy

or

mapped from an approved rule taxonomy

or

supported by structured evidence.
```

AI-generated severity can remain useful as advisory metadata.

---

# 68. Failure Dominance

A useful gate principle is:

> Strong positive evidence does not necessarily compensate for decisive negative evidence.

For example:

```text
1,000 passing generated tests
```

should not override:

```text
one deterministic required test showing a critical regression.
```

Therefore the gate should reason in terms of evidence classes and dominance rules, not merely vote counting.

---

# 69. Evidence Conflict

Example:

```text
existing regression suite        PASS

generated boundary tests         PASS

static analysis                  PASS

mutation analysis                WEAK

independent semantic reviewer    HIGH-RISK CONCERN
```

The system should not automatically average these into:

```text
82% PASS.
```

Instead the policy should ask:

```text
Is the concern testable?

Can additional evidence resolve it?

Is it high severity?

Is the evidence portfolio complete?

Has the evidence budget been exhausted?
```

Possible result:

```text
HUMAN_REVIEW_REQUIRED.
```

This is one reason a ternary gate is preferable to forced binary automation.

---

# 70. The Role of an AI Semantic Reviewer

An AI semantic reviewer can be useful.

It may detect:

```text
requirement misunderstanding

suspicious assumptions

unhandled business semantics

incorrect API usage

inconsistent logic

missing edge cases
```

But its result should generally be treated as:

```text
EVIDENCE / HYPOTHESIS
```

rather than:

```text
FINAL GATE DECISION.
```

Where possible, the system should transform semantic concerns into testable hypotheses.

Example:

```text
AI concern:
"Function may mishandle leap-year dates."

        │
        ▼

Test synthesis:
generate Feb 28 / Feb 29 / Mar 1 cases

        │
        ▼

deterministic execution
```

This is a powerful pattern because AI expands reasoning while execution establishes observable behavior.

---

# 71. AI Disagreement Can Be Useful Evidence

Suppose:

```text
Reviewer A: likely safe

Reviewer B: possible boundary defect

Reviewer C: uncertain
```

Disagreement should not necessarily be resolved by majority vote.

It can be interpreted as evidence of uncertainty.

The planner can ask:

```text
What concrete experiment distinguishes these hypotheses?
```

Then generate targeted deterministic tests.

Therefore disagreement can become an **evidence-generation trigger**.

---

# 72. Evidence Diversity Mapper as Coordination Layer

The mapper can coordinate this process.

Example:

```text
                 ┌─────────────────────┐
                 │ Task Specification  │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Candidate Artifact  │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Evidence Planner    │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Diversity Mapper    │
                 └──────────┬──────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
   behavioral gap     structural gap    adversarial gap
          │                 │                 │
          ▼                 ▼                 ▼
    test synthesis       AST/tooling       mutation /
                                            adversarial
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                            ▼
                   Evidence Portfolio
                            │
                            ▼
                    Policy Evaluation
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
            PASS           FAIL       HUMAN REVIEW
```

The mapper's primary job is coordination.

It should not become a hidden second gate.

---

# 73. A Possible Evidence Taxonomy

The exact taxonomy should remain configurable, but a useful starting point is:

```text
E1 — Requirement Evidence

E2 — Existing Regression Evidence

E3 — Generated Behavioral Evidence

E4 — Boundary / Edge Evidence

E5 — Negative / Invalid-Input Evidence

E6 — Structural / Static Evidence

E7 — Type / Compiler Evidence

E8 — Mutation Evidence

E9 — Property / Invariant Evidence

E10 — Security Evidence

E11 — Dependency / Integration Evidence

E12 — Semantic Review Evidence

E13 — Historical Failure-Mode Evidence
```

Not every X1 task needs every category.

The TaskSpecification and GatePolicy should determine which evidence categories are:

```text
REQUIRED

OPTIONAL

NOT APPLICABLE.
```

---

# 74. Why Evidence Requirements Should Be Task-Specific

A one-line configuration change and a mortgage-calculation algorithm should not require identical assurance evidence.

Likewise:

```text
documentation edit

dependency version update

business-rule change

API integration

database migration
```

have different failure modes.

Therefore:

```text
one universal gate
```

should mean:

```text
one universal gating framework
```

not:

```text
one identical evidence checklist for every task.
```

Task-specific policies should configure the framework.

---

# 75. Low-Hanging-Fruit POC Principle

The first X1 should be deliberately narrow.

Good characteristics include:

```text
clear input

clear expected behavior

bounded repository scope

strong deterministic testability

limited external dependencies

reproducible sandbox

meaningful but manageable failure modes
```

Poor first candidates include tasks that require:

```text
large architectural redesign

ambiguous business requirements

many external systems

production-only data

subjective UI judgment

broad repository changes
```

The goal of the first POC is to test the architecture, not to select the hardest possible engineering task.

---

# 76. Why the First POC Should Stop Before Autonomous Production Deployment

The central POC hypothesis can be tested without autonomous production deployment.

The platform can demonstrate:

```text
task accepted

candidate generated

candidate independently gated

evidence preserved

correct PR status published
```

That is enough to evaluate the core automation architecture.

Adding automatic production deployment introduces additional questions about:

```text
change management

production authorization

rollback

release windows

segregation of duties
```

without materially improving the first test of change-generation and gating reliability.

Therefore automatic deployment is intentionally postponed.

---

# 77. Workflow Integration

Component 12 bridges the domain platform to engineering systems such as Azure DevOps.

It should translate:

```text
external workflow event
```

into:

```text
canonical TaskRequest
```

and translate:

```text
GateDecision / RunOutcome
```

into:

```text
external workflow status.
```

It should not absorb domain logic.

For example, Component 12 should not independently decide:

```text
mutation score 0.74 means FAIL.
```

That belongs to Component 3.

---

# 78. Why Service Bus Is Useful but Not the Domain Model

Azure Service Bus can provide:

```text
durability

retry support

decoupling

delivery buffering
```

But a Service Bus message is an infrastructure envelope.

The domain should still operate on canonical contracts.

Preferred:

```text
Service Bus Message
      │
      ▼
Component 12 adapter
      │
      ▼
TaskRequest
      │
      ▼
Component 9
```

This allows a future workflow provider to replace Azure DevOps or Service Bus without rewriting the domain.

---

# 79. Idempotency Is Required Even with Durable Messaging

Messages may be delivered more than once.

Network responses may be lost.

Processes may crash.

Therefore:

```text
receive event
```

must not automatically mean:

```text
create new run.
```

The system needs a stable external event identity and atomic claim semantics.

Conceptually:

```text
(provider, event_id)
       │
       ▼
atomic claim
       │
       ├── new
       │      ▼
       │   create run
       │
       └── existing
              ▼
           do not duplicate
```

This is an engineering reliability requirement, not an AI-specific feature.

---

# 80. Why Correlation IDs Matter

A single engineering task may produce:

```text
TaskRequest

OrchestrationRun

CandidateArtifact

ExecutionReceipt

GateDecision

Pull Request

Release

Deployment

Operational observations

Process outcomes
```

Without correlation, later analysis becomes unreliable.

Therefore the architecture carries identifiers such as:

```text
task_request_id

task_id

run_id

candidate_id

trace_id

deployment_id
```

These form the spine connecting evaluation, operation, and business measurement.

---

# 81. Release Gating and Pipeline Evaluation Have Different Token Scaling

The two components can both become token intensive, but for different reasons.

`ReleaseGateService` token use may scale with:

```text
candidate complexity

evidence gaps

number of semantic hypotheses

number of generated tests

diversification rounds

adversarial generation
```

`EvaluationCampaignRunner` itself should ideally contain relatively little LLM reasoning.

Its total campaign cost is large because it repeatedly invokes:

```text
ChangeExecutionService
+
ReleaseGateService
```

across many cases and potentially repeated runs.

Therefore distinguish:

```text
TOKENS USED BY COMPONENT 5'S OWN LOGIC
```

from:

```text
TOKENS ATTRIBUTED TO AN EVALUATION CAMPAIGN.
```

The second can be very large even if the campaign runner itself is mostly deterministic orchestration and statistics.

---

# 82. Pipeline-Level Evaluation Should Be Mostly Deterministic

Once benchmark cases and hidden oracles exist, the campaign runner should primarily:

```text
schedule runs

collect outputs

compare outputs to oracle

classify outcomes

aggregate metrics

calculate uncertainty

report cost
```

These functions should generally be deterministic.

AI may help with benchmark construction or later failure analysis.

It should not be necessary for AI to decide whether:

```text
GateDecision = PASS
and
HiddenOracle = unacceptable
```

constitutes a false release.

That classification is deterministic.

---

# 83. Example Pipeline Confusion Matrix

For benchmark cases that admit a binary acceptability oracle, the conceptual structure is:

```text
                         HIDDEN ORACLE
                    ACCEPTABLE    UNACCEPTABLE

GATE PASS              correct       FALSE RELEASE

GATE FAIL              false         correct
                       rejection     rejection

GATE HUMAN REVIEW      abstention     abstention
```

Human-review outcomes should normally be reported separately rather than forced into PASS or FAIL.

Useful metrics include:

```text
coverage of automation

selective accuracy

false release among automated PASS decisions

review rate

failure rate

task completion rate
```

---

# 84. Selective Automation

The presence of:

```text
HUMAN_REVIEW_REQUIRED
```

creates a selective automation system.

The platform is effectively allowed to say:

```text
I will automate the cases for which my evidence is sufficient
and abstain on the rest.
```

This may be more realistic than demanding 100% autonomous coverage.

A useful enterprise question is therefore:

```text
At an acceptable false-release rate,
what fraction of X1 tasks can be completed without human review?
```

This is often more informative than simple overall accuracy.

---

# 85. Qualification Is a Trade-Off Surface

Suppose stricter gating produces:

```text
false release ↓

human review ↑
```

while looser gating produces:

```text
false release ↑

human review ↓
```

There is no universal mathematically correct operating point.

The appropriate threshold depends on:

```text
task risk

cost of defect

human capacity

business value

regulatory expectations

reversibility

monitoring and rollback capability
```

Component 5 should therefore expose the trade-off rather than hide it.

---

# 86. Statistical Metrics Should Include Denominators

Avoid reporting:

```text
False release = 2%
```

without context.

Prefer:

```text
False releases:
2 / 100 total benchmark tasks

or

2 / 61 automated PASS decisions
```

depending on the definition.

Confidence intervals should also state the underlying sample.

Small denominators should remain visibly small.

---

# 87. Confidence Intervals Must Not Manufacture Confidence

If the POC contains:

```text
12 benchmark tasks
```

the correct response is not to search for a statistical technique that makes the interval look narrow.

The correct conclusion may simply be:

```text
evidence is still too limited for a strong reliability claim.
```

Statistical uncertainty is information.

It is not a formatting problem.

---

# 88. Benchmark Diversity Matters More Than Raw Benchmark Count

A benchmark of:

```text
1,000 nearly identical cases
```

may be less useful than:

```text
100 carefully selected cases
```

covering materially different failure modes.

Benchmark dimensions might include:

```text
task complexity

repository structure

language features

dependency interactions

edge conditions

failure mode

requested change type

ambiguity

test coverage quality

code style

legacy patterns
```

This is another potential application of diversity-mapping ideas, although benchmark diversity should remain conceptually separate from release-gate evidence diversity.

---

# 89. Benchmark Construction Can Use AI, but Validation Must Be Independent

A practical POC may use AI to generate:

```text
baseline repositories

known bugs

change requests

reference solutions

hidden tests
```

This is efficient.

However, benchmark validation should include independent deterministic execution and, where appropriate, human inspection.

A benchmark case should demonstrate that:

```text
baseline exhibits intended problem

reference solution resolves intended problem

hidden tests distinguish important incorrect behavior

task is actually solvable from public information

oracle does not leak
```

Only then should the case be admitted to the validated benchmark.

---

# 90. Synthetic Ground Truth Should Be Labelled Honestly

The first benchmark may be:

```text
synthetic
```

That is not inherently a weakness.

Synthetic benchmarks are useful for controlled engineering experiments.

But claims should be phrased appropriately.

For example:

```text
Performance on validated synthetic X1 benchmark
```

is defensible.

Claiming:

```text
98% reliable on all real L1 engineering work
```

from the same benchmark would not be defensible.

Eventually, qualification should include carefully curated real or realistic historical tasks where governance permits.

---

# 91. Historical Tasks Can Become Valuable Evaluation Data

Later, actual completed L1 tasks may provide:

```text
original task request

baseline repository state

human-produced change

review comments

test results

incident history
```

These could support a stronger benchmark.

However, the human-produced patch should not automatically be treated as the only correct oracle.

There may be multiple acceptable implementations.

Therefore the hidden oracle should ideally focus on:

```text
required behavior

forbidden behavior

acceptance tests

constraints
```

rather than only exact code equality.

---

# 92. Exact Patch Matching Is Usually a Weak Oracle

For most engineering tasks:

```text
candidate_patch == reference_patch
```

is too strict.

Two different implementations can be correct.

Prefer:

```text
behavioral correctness

required properties

scope constraints

security constraints

regression behavior
```

Reference patches remain useful for:

```text
benchmark validation

difficulty analysis

comparison

human inspection
```

but should not necessarily define correctness by textual equality.

---

# 93. Release Gate Should Prefer Behavioral Evidence Over Stylistic Preference

An LLM may dislike a coding style while the code is functionally correct.

Style may matter if the repository has explicit standards.

But stylistic disagreement should not be conflated with a functional defect.

Evidence should therefore distinguish:

```text
FUNCTIONAL

STRUCTURAL

SECURITY

MAINTAINABILITY

STYLE

POLICY
```

findings.

Gate policy can then specify which are hard requirements.

---

# 94. Existing Tests Are Valuable but Not Sufficient

Existing repository tests provide historically grounded evidence.

They should normally be run.

However, they may fail to detect the very defect the requested change addresses.

Therefore the gate should combine:

```text
existing regression suite
+
task-specific generated evidence
+
structural/static evidence
+
mutation/adversarial evidence where appropriate
```

The existing suite is a strong baseline, not the complete oracle.

---

# 95. Generated Tests Should Be Preserved

Generated tests should not disappear after gating.

They can provide valuable evidence for:

```text
audit

failure analysis

reproduction

benchmark improvement

future regression testing
```

Whether they are automatically committed to the repository is a separate policy question.

For the POC, preserving them as immutable evidence artifacts is sufficient.

---

# 96. Generated Tests Should Not Automatically Become Product Tests

A release-gate test may be useful for evaluating one candidate but unsuitable for permanent repository inclusion.

Reasons include:

```text
redundancy

high execution cost

fragility

over-specificity

temporary adversarial purpose
```

Therefore distinguish:

```text
GATE EVIDENCE TEST
```

from:

```text
PERMANENT REPOSITORY TEST.
```

Promotion into the repository can be a separate future workflow.

---

# 97. Reproducibility

Where possible, evidence should preserve enough information to rerun the experiment.

Examples:

```text
repository revision

candidate hash

runner image digest

dependency lock file

test artifact hashes

command

environment fingerprint

model identifier

model parameters

policy version
```

Perfect reproducibility may not be possible for external non-deterministic models.

The platform should still preserve all controllable inputs.

---

# 98. Model Version Drift

A model endpoint may change behavior over time.

Therefore:

```text
model name
```

alone may not always be enough to reproduce results.

Where provider capabilities permit, preserve:

```text
deployment identifier

model version

API version

parameters

request timestamp

prompt/template version

system instruction version
```

If exact model immutability cannot be guaranteed, document that limitation rather than claiming perfect reproducibility.

---

# 99. Prompt and Skill Versioning

Prompt changes can materially alter behavior.

Therefore prompts and skills should be treated as versioned capability artifacts.

A useful evidence record includes:

```text
skill hash

prompt/template hash

task specification hash

model configuration
```

This allows evaluation results to be tied to the actual reasoning configuration used.

---

# 100. Caching

Caching can reduce cost.

But caching must not compromise experiment interpretation.

Examples:

```text
same deterministic static-analysis artifact
    → safe to reuse if inputs identical

same LLM response
    → potentially reusable if exact request/configuration identity is known
```

Evaluation reports should record cache behavior because cost measurements differ between:

```text
cold execution
```

and:

```text
cache-assisted execution.
```

---

# 101. Failure Handling

Every component should distinguish:

```text
DOMAIN FAILURE

from

INFRASTRUCTURE FAILURE.
```

Example:

```text
required test fails
    → candidate evidence / gate failure

Container Apps unavailable
    → infrastructure failure
```

The second should not be interpreted as evidence that the candidate itself is defective.

Likewise:

```text
LLM request timed out
```

is not equivalent to:

```text
candidate failed semantic review.
```

Typed outcomes should preserve these distinctions.

---

# 102. Fail Closed Versus Escalate

Not every uncertainty should become `FAIL`.

A useful conceptual policy is:

```text
POSITIVE EVIDENCE OF UNSAFE / INCORRECT
    → FAIL

INSUFFICIENT EVIDENCE
    → HUMAN_REVIEW_REQUIRED

INFRASTRUCTURE FAILURE
    → RETRY / TECHNICAL FAILURE / HUMAN HANDLING
       according to deterministic orchestration policy
```

This preserves semantics.

Otherwise the system could report a candidate as technically defective merely because Azure was temporarily unavailable.

---

# 103. Retry Policy

Retries should be bounded and reason-aware.

Appropriate retry candidates may include:

```text
transient network failure

rate limit

temporary Azure service interruption
```

Poor retry candidates include:

```text
compiler error

deterministic test failure

policy violation
```

Repeatedly asking an LLM to regenerate until something passes can also bias evaluation.

The number and reason for retries must therefore be evidence.

---

# 104. "Retry Until Pass" Is Dangerous

Suppose:

```text
attempt 1 FAIL
attempt 2 FAIL
attempt 3 FAIL
attempt 4 PASS
```

Reporting only:

```text
PASS
```

hides important information.

For evaluation, the platform should record:

```text
number of attempts

failure reasons

tokens consumed

elapsed time

final outcome
```

The TaskSpecification should define whether regeneration is allowed and under what budget.

---

# 105. Candidate Generation Policy

Possible strategies include:

```text
one-shot candidate

bounded repair loop

multiple candidate generation

candidate competition
```

The first POC should prefer a simple bounded strategy.

A possible policy is:

```text
generate candidate

run inexpensive deterministic checks

allow bounded repair for mechanical failures

freeze candidate

send frozen candidate to independent release gate
```

The exact repair policy should be visible and evaluated.

---

# 106. Do Not Let the Gate Secretly Become the Developer

The release gate may discover a defect.

It should generally not silently repair the candidate and then PASS the repaired code.

That would collapse:

```text
change execution
```

and:

```text
independent gating.
```

A better pattern is:

```text
gate finds defect
      │
      ▼
FAIL / structured feedback
      │
      ▼
orchestrator
      │
      ▼
bounded new ChangeExecution attempt
      │
      ▼
NEW CandidateArtifact
      │
      ▼
fresh gate
```

Each candidate retains its own identity and evidence.

---

# 107. Candidate Immutability

Once a candidate enters release gating, it should be treated as immutable.

If a repair is made:

```text
Candidate C1
```

becomes:

```text
Candidate C2.
```

The old evidence remains attached to C1.

This avoids ambiguous histories such as:

```text
candidate passed tests,
then changed,
but retained same ID.
```

---

# 108. Pipeline-Level Evidence Should Preserve Failed Candidates

Failed candidates are scientifically valuable.

They reveal:

```text
generator failure modes

gate detection ability

test weaknesses

mutation weaknesses

cost of failed attempts

common escalation reasons
```

Do not discard them simply because they were not released.

Component 5 should use them in failure analysis.

---

# 109. Evaluation Campaigns Should Be Immutable Experiments

A campaign should ideally define:

```text
campaign ID

benchmark version

capability version

configuration

model configuration

number of runs

statistical plan

start/end time
```

Once executed, its results should not be silently overwritten.

If configuration changes:

```text
create a new campaign.
```

This preserves scientific interpretability.

---

# 110. Evaluation Before Release Versus Monitoring After Release

Offline evaluation answers:

```text
Should we trust this capability enough to use it?
```

Operational monitoring answers:

```text
How is deployed output behaving now?
```

These are complementary.

Strong offline evaluation does not eliminate monitoring.

Good production monitoring does not justify weak pre-release qualification.

---

# 111. Feedback Is Deliberately Outside the Current POC

The architecture eventually could learn from:

```text
production incidents

human reviews

rollback events

business outcomes

new failure modes
```

However, automatic feedback creates additional questions:

```text
data quality

label validity

concept drift

feedback loops

self-reinforcing errors

governance of retraining/prompt changes
```

Therefore the first POC should measure and preserve signals without automatically feeding them back into capability modification.

That is a later architectural layer.

---

# 112. Component Summary

The repository's logical components can be summarized as follows.

## Component 1 — Shared Contracts

Defines canonical cross-component data structures and enumerations.

It should contain:

```text
contracts
identities
references
outcomes
```

not Azure-specific infrastructure logic.

---

## Component 2 — Change Execution

Produces candidate code changes for an approved task specification.

It owns:

```text
change reasoning
change generation
bounded repair behavior
candidate construction
```

It does not own final release approval.

---

## Component 3 — Release Gating

Builds and evaluates independent evidence for one exact candidate.

It owns:

```text
evidence planning
diversity coordination
verification
mutation/adversarial evidence
deterministic policy evaluation
PASS / FAIL / HUMAN_REVIEW_REQUIRED
```

It does not perform the actual human review.

---

## Component 4 — Evidence and Provenance

Persists evidence and preserves content identity/provenance.

It supports:

```text
reproduction
audit
analysis
candidate binding
```

It does not decide whether evidence means PASS.

---

## Component 5 — Pipeline-Level Evaluation

Runs offline qualification campaigns.

It owns:

```text
benchmark execution
hidden-oracle comparison
pipeline metrics
uncertainty
qualification evidence
```

It must remain separate from online gating.

---

## Component 6 — Operational Measurement

Measures behavior after released code begins operating.

It owns normalized technical operational metrics.

It does not automatically claim business value.

---

## Component 7 — Process / Business Measurement

Connects deployments to process outcomes and business KPIs.

It must distinguish correlation from causal attribution.

---

## Component 8 — Economics / FinOps

Measures resource consumption and economic implications.

It distinguishes:

```text
gross estimated value

from

realized net value.
```

---

## Component 9 — Orchestration

Coordinates the deterministic lifecycle.

It owns:

```text
state transitions
budgets
retries
routing
```

It should not use an LLM as the workflow controller.

---

## Component 10 — Execution Environment

Runs untrusted or semi-trusted code in controlled environments.

It owns:

```text
sandboxing
resource limits
execution receipts
environment identity
```

It does not decide whether code should release.

---

## Component 11 — Task Capability Registry / Specification

Defines approved X1 ... Xn capabilities.

It owns:

```text
task specifications
skills
gate policy references
eval specification references
capability versioning
```

It represents executable governance.

---

## Component 12 — Workflow Integration

Connects the platform to external engineering workflow systems.

It owns:

```text
event ingestion
normalization
idempotency
external status publication
correlation
```

It does not own gate semantics.

---

# 113. End-to-End Logical Architecture

```text
┌──────────────────────────────────────────────────────────────────┐
│                  EXTERNAL ENGINEERING WORKFLOW                   │
│                    e.g. Azure DevOps / Jira                      │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Component 12     │
                    │ Workflow Integration│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     Component 9     │
                    │    Orchestration    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Component 11     │
                    │ Capability Registry │
                    │ X1 ... Xn           │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     Component 2     │
                    │  Change Execution   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Component 10     │
                    │ Sandbox Execution A │
                    └──────────┬──────────┘
                               │
                               ▼
                       CandidateArtifact
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
      ┌─────────────────────┐       ┌─────────────────────┐
      │     Component 4     │       │     Component 3     │
      │ Evidence/Provenance │       │    Release Gate     │
      └─────────────────────┘       └──────────┬──────────┘
                                               │
                      ┌────────────────────────┼─────────────────────┐
                      │                        │                     │
                      ▼                        ▼                     ▼
               Evidence Planner        Diversity Mapper     Static/Structural
                      │                        │                     │
                      └────────────────────────┼─────────────────────┘
                                               │
                                               ▼
                                    Independent Test Synthesis
                                               │
                                               ▼
                                    Mutation / Adversarial
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │    Component 10     │
                                    │ Sandbox Execution B │
                                    └──────────┬──────────┘
                                               │
                                               ▼
                                        Evidence Portfolio
                                               │
                                               ▼
                                    Deterministic Gate Policy
                                               │
                            ┌──────────────────┼──────────────────┐
                            │                  │                  │
                            ▼                  ▼                  ▼
                           PASS               FAIL       HUMAN_REVIEW_REQUIRED
                            │                  │                  │
                            └──────────────────┼──────────────────┘
                                               │
                                               ▼
                                      Component 9 / 12
                                               │
                                               ▼
                                     External Workflow
```

---

# 114. Offline Qualification Architecture

```text
                     ┌─────────────────────────┐
                     │    BenchmarkFactory     │
                     │  AI-assisted if useful │
                     └────────────┬────────────┘
                                  │
                                  ▼
                     Candidate Benchmark Cases
                                  │
                                  ▼
                     Independent Validation
                                  │
                                  ▼
                     VALIDATED GOLDEN BENCHMARK
                                  │
              ┌───────────────────┴────────────────────┐
              │                                        │
              ▼                                        ▼
       Public Task Package                       Hidden Oracle
              │                                        │
              ▼                                        │
 ┌──────────────────────────┐                           │
 │       Component 5        │                           │
 │ EvaluationCampaignRunner │                           │
 └────────────┬─────────────┘                           │
              │                                         │
              ▼                                         │
      Component 2                                      │
              │                                         │
              ▼                                         │
      CandidateArtifact                                │
              │                                         │
              ▼                                         │
      Component 3                                      │
              │                                         │
              ▼                                         │
       GateDecision                                    │
              │                                         │
              └──────────────────────┬──────────────────┘
                                     │
                                     ▼
                              Oracle Comparison
                                     │
                                     ▼
                           Pipeline-Level Metrics
                                     │
                 ┌───────────────────┼────────────────────┐
                 │                   │                    │
                 ▼                   ▼                    ▼
          task success        false release         review rate
                 │                   │                    │
                 ├───────────────────┼────────────────────┤
                 │                   │                    │
                 ▼                   ▼                    ▼
              cost               latency            uncertainty
                                     │
                                     ▼
                           Qualification Evidence
```

---

# 115. Post-Release Measurement Architecture

```text
                   RELEASED CANDIDATE
                           │
                           ▼
                    Running Software
                           │
                           ▼
                  ┌─────────────────┐
                  │   Component 6   │
                  │ Operational     │
                  │ Measurement     │
                  └────────┬────────┘
                           │
                           ▼
                 Technical Outcomes
                           │
                           ▼
                  ┌─────────────────┐
                  │   Component 7   │
                  │ Process /       │
                  │ Business        │
                  └────────┬────────┘
                           │
                           ▼
                    Process Outcomes
                           │
                           ▼
                     Business KPIs


Parallel economic path:

Components 2 / 3 / 5 / 6 / 9 / 10
               │
               ▼
       Resource Consumption
               │
               ▼
        ┌─────────────────┐
        │   Component 8   │
        │ Economics       │
        └────────┬────────┘
                 │
                 ▼
        Unit Economics / Value
```

---

# 116. What Is Established Engineering Practice

Several elements of this architecture are established software-engineering or distributed-systems practices rather than novel AI ideas.

Examples include:

```text
CI/CD release gates

unit and integration testing

static analysis

compiler/type checks

mutation testing

sandboxed execution

content hashing

immutable artifacts

dependency inversion

deterministic state machines

idempotent event handling

transactional outbox

distributed tracing

versioned configuration

holdout evaluation

confidence intervals

least-privilege identity
```

These should be preferred over AI-based reinvention wherever they solve the problem adequately.

---

# 117. What Is Emerging Advanced AI Engineering Practice

The following areas have strong conceptual or emerging industry support but are less standardized:

```text
agentic coding workflows

LLM-generated tests

LLM-as-reviewer

multi-model review

AI-driven adversarial test generation

evaluation of coding agents on hidden software tasks

bounded autonomous repair loops

AI-generated benchmark construction

agent capability qualification
```

The implementation details vary considerably across labs and vendors.

Therefore this repository should avoid pretending that one universal industry architecture already exists.

---

# 118. What Is More Experimental in This Architecture

The most experimental ideas include:

```text
Evidence Diversity Mapper as an explicit coordination layer

formal use of evidence diversity to mitigate shared LLM blind spots

combining semantic hypotheses with deterministic challenge generation

candidate-level evidence portfolios feeding a deterministic ternary gate

connecting offline selective-automation qualification to
operational and economic measurement
```

These ideas are plausible and useful for the POC.

They should be treated as hypotheses to evaluate, not as established industry standards.

---

# 119. What Is Primarily an Architectural Recommendation

Some design choices are not claims that leading AI labs universally use exactly this structure.

They are engineering recommendations derived from the requirements of this POC.

Examples include:

```text
12 explicit logical components

the exact Component 1–12 boundaries

the Evidence Diversity Mapper interface

the exact evidence taxonomy

the exact B-series documentation structure

the proposed four-layer eval → operational → process → KPI model
```

These should remain open to revision if implementation evidence suggests a better boundary.

---

# 120. Known Architectural Uncertainties

The architecture intentionally retains several unresolved questions.

## 120.1 How Much Independence Is Enough?

We do not yet know how much marginal assurance comes from:

```text
different prompt

different model

different model family

different representation

different test-generation method

mutation testing

static tools
```

This must be measured.

---

## 120.2 How Should Evidence Diversity Be Quantified?

The mapper can identify categories and gaps.

A rigorous scalar measure of evidence independence is much harder.

Correlations among:

```text
tests

models

prompts

failure hypotheses
```

may not be directly observable.

The POC should therefore begin with transparent categorical diversity rather than claiming a mathematically precise independence score.

---

## 120.3 How Many Generated Tests Are Enough?

There is no universal answer.

The answer depends on:

```text
task complexity

test diversity

mutation performance

risk

cost

evidence quality
```

A fixed number such as 100 should not be treated as scientifically established.

---

## 120.4 How Representative Will Synthetic Benchmarks Be?

Synthetic benchmarks provide controlled ground truth.

They may not capture:

```text
messy requirements

legacy systems

poor documentation

organizational conventions

real dependency complexity

production data peculiarities
```

Realistic historical tasks will eventually be needed to strengthen external validity.

---

## 120.5 How Stable Are Gate Results Across Model Versions?

Model upgrades may change:

```text
candidate quality

test quality

review behavior

token consumption

abstention rate
```

Material model changes may therefore require requalification.

---

## 120.6 How Much Human Review Is Economically Acceptable?

A gate that escalates 80% of tasks might be very safe but economically unattractive.

A gate that escalates 5% may be efficient but unsafe.

The acceptable frontier must be determined empirically and organizationally.

---

## 120.7 What Is the Correct False-Release Tolerance?

This is not purely a data-science decision.

It depends on:

```text
task risk

reversibility

downstream controls

production blast radius

regulatory obligations

human review cost
```

The platform should measure the trade-off.

Risk owners should select the acceptable operating point.

---

## 120.8 How Should Multiple Correct Implementations Be Represented?

A reference patch alone is insufficient.

The benchmark needs behavioral or property-based oracles.

Designing strong hidden oracles may become one of the most expensive parts of benchmark construction.

---

## 120.9 How Much Gate Evidence Should Be Retained?

Full retention provides strong reproducibility but may create:

```text
storage cost

privacy concerns

source-code retention concerns

data-classification issues

model-input retention issues
```

Enterprise retention policy remains unresolved.

---

## 120.10 Which Azure Execution Boundary Is Sufficient?

Azure Container Apps Jobs are a practical POC option.

Whether they provide sufficient isolation for every future task depends on:

```text
threat model

code trust level

network requirements

credential requirements

enterprise security standards
```

The abstraction deliberately allows replacement.

---

# 121. Things We Should Explicitly Avoid Claiming During the POC

Until supported by evidence, do not claim:

```text
"AI replaces L1 developers."

"The gate proves code is correct."

"Mutation score proves safety."

"100 generated tests provide 100 independent observations."

"A 95% confidence interval means 95% certainty that this candidate is correct."

"An LLM reviewer is independent because it uses another prompt."

"Synthetic benchmark performance equals production performance."

"Technical PASS means production deployment is automatically authorized."

"Operational success proves business value."

"Estimated labour hours equal realized financial savings."
```

More defensible language is:

```text
The POC evaluates whether a narrowly defined class of L1 tasks
can be selectively automated under explicit technical controls.
```

---

# 122. Things the POC Can Realistically Demonstrate

A successful POC should be able to demonstrate:

```text
1. A versioned X1 task can be represented formally.

2. A change agent can produce an immutable candidate.

3. Candidate generation can occur in a bounded execution environment.

4. A separate release-gate process can build heterogeneous evidence.

5. AI-generated evidence can be converted into deterministic executable tests.

6. Static and structural program information can augment source-text review.

7. Mutation testing can measure part of the test portfolio's defect-detection ability.

8. Evidence diversity can be made explicit.

9. Gate policy can deterministically produce PASS, FAIL, or HUMAN_REVIEW_REQUIRED.

10. Gate decisions can be bound to exact candidate identities.

11. Evidence can be preserved and reproduced.

12. The complete pipeline can be run against hidden benchmark oracles.

13. False releases, false rejections, abstentions, cost, latency, and uncertainty can be measured.

14. Token consumption can be attributed to components.

15. External engineering workflow can receive candidate-bound status without granting the AI autonomous production deployment.
```

That would already constitute a meaningful POC.

---

# 123. Recommended X1 POC Scientific Questions

The first evaluation campaign should answer questions such as:

```text
Q1.
How often does ChangeExecutionService produce an acceptable candidate?

Q2.
Of unacceptable candidates, how often does ReleaseGateService prevent PASS?

Q3.
What is the false-release rate?

Q4.
What is the false-rejection rate?

Q5.
What fraction of tasks require human review?

Q6.
How often does mutation analysis expose weak generated tests?

Q7.
How often does evidence diversification discover a meaningful evidence gap?

Q8.
Does diversified evidence outperform a simpler gate using only generated tests?

Q9.
How stable are results across repeated runs?

Q10.
How many tokens and how much compute are consumed per successful automated task?

Q11.
Which gate activities consume the largest marginal cost?

Q12.
Which failure modes remain systematically undetected?
```

These questions make the POC an experiment rather than merely a demonstration.

---

# 124. Recommended Ablation Experiments

If time permits, Component 5 should support ablation studies.

For example:

```text
FULL GATE
    generated tests
    + static evidence
    + mutation
    + diversity mapping


ABLATION A
    generated tests only


ABLATION B
    generated tests
    + mutation


ABLATION C
    generated tests
    + static evidence


ABLATION D
    generated tests
    + diversity mapping
```

Then compare:

```text
false release

false rejection

review rate

cost

latency
```

This is particularly important for the Evidence Diversity Mapper.

Without an ablation, we may know that the mapper sounds reasonable but not whether it materially improves assurance.

---

# 125. Recommended Evidence-Diversity Experiment

One useful experiment is:

```text
CONTROL

One model generates 100 tests.


TREATMENT

Initial model generates 25 tests.

Evidence Diversity Mapper analyzes coverage.

Additional evidence generators target identified gaps.

Total budget remains approximately comparable.
```

Then compare:

```text
mutation kills

hidden-defect detection

false releases

semantic coverage

token cost
```

This tests the hypothesis:

> Structured diversity is more valuable than simply generating more tests.

That hypothesis should be measured rather than assumed.

---

# 126. Recommended Shared-Blind-Spot Experiment

Another useful experiment:

```text
Condition A

same model family:
candidate generation
+
test generation


Condition B

same model family:
candidate generation
+
diversity-aware test generation


Condition C

model family A:
candidate generation

model family B:
test generation


Condition D

model diversity
+
evidence diversity
+
deterministic tools
```

Measure hidden-defect detection.

This can provide empirical evidence about whether model diversity, evidence diversity, or their combination provides the largest marginal benefit.

---

# 127. Release-Gate Cost Experiment

Because release gating may consume more tokens than candidate generation, record:

```text
change_execution_tokens

evidence_planning_tokens

test_synthesis_tokens

diversification_tokens

semantic_review_tokens

total_gate_tokens

total_pipeline_tokens
```

Then calculate:

```text
gate tokens / total tokens

tokens per PASS

tokens per correct rejection

tokens per false release prevented

tokens per human-review escalation
```

The last measures are exploratory but may become useful for understanding assurance economics.

---

# 128. Why "Tokens per False Release Prevented" Must Be Interpreted Carefully

A prevented false release is counterfactual.

We only know it in a benchmark because the hidden oracle tells us the candidate was unacceptable.

In production, we usually cannot directly observe:

```text
what would have happened if the gate had released it.
```

Therefore such measures are most defensible during controlled benchmark evaluation.

Do not automatically translate them into production financial value.

---

# 129. Junior Engineer / Data Scientist Guidance

When modifying this repository, ask four questions before changing a component:

```text
1. Which component owns this responsibility?

2. Is this domain logic or infrastructure logic?

3. Does this change alter an assurance boundary?

4. Does this change invalidate previous qualification evidence?
```

If the answer to question 4 may be yes, preserve the previous version and create a new capability/configuration identity.

Do not silently mutate an already qualified configuration.

---

# 130. Guidance for Adding a New Task Type X2

Do not copy the entire platform.

Instead:

```text
1. Define X2 TaskSpecification.

2. Define X2 skill/instructions.

3. Define allowed scope.

4. Define X2 gate policy.

5. Define X2 evaluation specification.

6. Build validated benchmark cases.

7. Run qualification campaign.

8. Review false-release/review/cost behavior.

9. Approve the capability separately.

10. Register X2.
```

The generic services should remain reusable.

If adding X2 requires large changes throughout Components 2–12, that is evidence that task-specific concerns have leaked into generic platform code.

---

# 131. Guidance for Adding a New LLM

A model change should be treated as a configuration change, not a trivial implementation detail.

Before replacing:

```text
Model A
```

with:

```text
Model B
```

consider effects on:

```text
candidate generation

test generation

semantic review

token consumption

latency

evidence diversity

false-release behavior

human-review behavior
```

Run the relevant qualification campaign before treating the new configuration as equivalent.

---

# 132. Guidance for Adding a New Deterministic Tool

Suppose a developer adds:

```text
new security scanner
```

or:

```text
new static analyzer.
```

The preferred integration is:

```text
tool adapter
      │
      ▼
normalized EvidenceArtifact
      │
      ▼
ReleaseGateService
```

Do not place vendor-specific output parsing throughout gate policy.

Normalize infrastructure/tool output at the adapter boundary.

---

# 133. Guidance for Changing Gate Policy

Gate policy is assurance logic.

A change from:

```text
minimum mutation score = A
```

to:

```text
minimum mutation score = B
```

may alter:

```text
false-release rate

false-rejection rate

human-review rate
```

Therefore:

```text
version policy

rerun relevant evaluation

preserve previous evidence

compare results.
```

Do not treat threshold edits as cosmetic configuration.

---

# 134. Guidance for Changing the Evidence Diversity Mapper

Because the mapper is experimental, changes should be evaluated through ablations.

Record:

```text
mapper version

taxonomy version

input evidence

identified gaps

requested additions

token cost

resulting gate evidence
```

Then Component 5 can determine whether the new mapper actually improves outcomes.

---

# 135. Guidance for Debugging a False Release

A false release is one of the most important events in the POC.

Do not simply patch the prompt.

Perform structured analysis:

```text
1. Was the task specification ambiguous?

2. Did ChangeExecution misunderstand the task?

3. Did the gate generate the right failure hypothesis?

4. Did the Evidence Diversity Mapper identify the relevant category?

5. Were appropriate tests generated?

6. Were tests valid?

7. Did deterministic execution work correctly?

8. Did mutation testing expose weakness?

9. Did gate policy ignore a relevant signal?

10. Did oracle construction correctly label the candidate?

11. Was there benchmark leakage?

12. Was evidence lost or mis-associated?
```

The fix should target the actual failure layer.

---

# 136. Guidance for Debugging a False Rejection

Likewise:

```text
1. Was the candidate actually acceptable?

2. Was the oracle too narrow?

3. Did a generated test encode an invalid assumption?

4. Was a deterministic tool misconfigured?

5. Was an equivalent mutant counted incorrectly?

6. Was severity overstated?

7. Was gate policy too strict?

8. Should the result have been HUMAN_REVIEW_REQUIRED instead of FAIL?
```

False rejection analysis is important because excessive rejection can make automation economically useless even when it is safe.

---

# 137. Guidance for Debugging Excessive Human Review

If review rate is too high, do not simply loosen thresholds.

Determine why.

Possible causes:

```text
poor task specification

insufficient deterministic evidence

weak generated tests

diversity mapper too demanding

unsupported code patterns

gate budget too small

model instability

poor benchmark construction

unnecessarily broad X1 scope
```

Sometimes the correct response is to narrow X1 rather than weaken the gate.

---

# 138. Narrowing X1 Is a Valid Engineering Decision

If X1 initially includes:

```text
A
B
C
D
```

and evidence shows:

```text
A and B automate reliably

C and D generate excessive uncertainty
```

a valid production capability may become:

```text
X1 = A + B
```

with C and D remaining human work or becoming future capabilities.

Selective scope is not failure.

It is evidence-based capability definition.

---

# 139. Capability Expansion Should Be Incremental

A useful maturity path is:

```text
X1.0
very narrow deterministic task

        │
        ▼

X1.1
additional known variation

        │
        ▼

X1.2
additional repository patterns

        │
        ▼

X2
different task class
```

Each expansion should have qualification evidence.

This is preferable to launching a universal coding agent and attempting to discover its safe operating boundary after deployment.

---

# 140. Architecture Philosophy in One Diagram

```text
                         ┌────────────────────┐
                         │  HUMAN / PLATFORM  │
                         │  DEFINES AUTHORITY │
                         └─────────┬──────────┘
                                   │
                                   ▼
                         Task Specification
                                   │
                                   ▼
                     ┌────────────────────────┐
                     │ AI GENERATES CANDIDATE │
                     └────────────┬───────────┘
                                  │
                                  ▼
                           Frozen Candidate
                                  │
                                  ▼
                     ┌────────────────────────┐
                     │ AI HELPS ASK:          │
                     │ "HOW COULD THIS FAIL?" │
                     └────────────┬───────────┘
                                  │
                                  ▼
                       Diverse Testable Claims
                                  │
                                  ▼
                     ┌────────────────────────┐
                     │ DETERMINISTIC TOOLS    │
                     │ EXECUTE / MEASURE      │
                     └────────────┬───────────┘
                                  │
                                  ▼
                           Evidence Portfolio
                                  │
                                  ▼
                     ┌────────────────────────┐
                     │ DETERMINISTIC POLICY   │
                     └────────────┬───────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
                   PASS          FAIL         REVIEW
                                  │
                                  ▼
                     ┌────────────────────────┐
                     │ OFFLINE HIDDEN ORACLE  │
                     │ EVALUATES THE PLATFORM │
                     └────────────┬───────────┘
                                  │
                                  ▼
                         MEASURED CAPABILITY
```

This is the central philosophy of the repository.

---

# 141. Trust-Boundary Summary

The architecture deliberately prevents several actors from having authority they do not need.

```text
ChangeExecutionService
    CAN:
        generate candidate

    CANNOT:
        declare itself released
        alter hidden oracle
        alter gate policy


ReleaseGateService
    CAN:
        gather evidence
        apply gate policy

    CANNOT:
        access hidden benchmark oracle
        perform organizational human approval
        silently modify candidate


EvaluationCampaignRunner
    CAN:
        access hidden oracle
        evaluate completed pipeline outcome

    CANNOT:
        leak oracle into online gate


ExecutionEnvironment
    CAN:
        execute authorized workload

    CANNOT:
        decide release policy
        grant itself broader credentials


WorkflowIntegration
    CAN:
        receive/publish workflow state

    CANNOT:
        redefine technical gate semantics


Human reviewer
    CAN:
        act through approved external workflow

    DOES NOT:
        execute as hidden logic inside ReleaseGateService
```

These restrictions are as important as the positive capabilities.

---

# 142. The Most Important Architectural Invariants

The following should be treated as high-value invariants.

```text
INVARIANT 1
A gate decision refers to an exact candidate.

INVARIANT 2
A modified candidate requires a new gate decision.

INVARIANT 3
The change generator cannot modify its governing authority.

INVARIANT 4
The online release gate cannot access the hidden benchmark oracle.

INVARIANT 5
A human-review requirement is a gate output, not an internal human step.

INVARIANT 6
Gate policy is deterministic and versioned.

INVARIANT 7
Infrastructure failures are not silently converted into candidate failures.

INVARIANT 8
Generated code executes only in an approved bounded environment.

INVARIANT 9
Evidence identity and provenance are preserved.

INVARIANT 10
Qualification claims identify the capability/configuration and benchmark version.

INVARIANT 11
Small samples remain visibly uncertain.

INVARIANT 12
Business-value claims remain separate from technical assurance claims.
```

Automated tests should eventually protect these invariants wherever practical.

---

# 143. What Should Cause an Immediate Architecture Review

The following changes should trigger review rather than routine coding:

```text
allowing generated code production credentials

allowing the change agent to edit gate policy

allowing the gate to access hidden oracle data

removing candidate identity from gate decisions

replacing ternary gating with unconditional binary PASS/FAIL

allowing unbounded LLM loops

allowing autonomous production deployment

changing benchmark after observing qualification results without versioning

changing model/prompt materially without considering requalification

collapsing evidence into an unexplained scalar score

using business KPI as proof of code correctness

using generated test count as independent statistical sample size
```

These changes affect the assurance model.

---

# 144. Current POC Success Criterion

The POC should be considered technically promising if, for a carefully selected X1 capability, it can demonstrate:

```text
meaningful autonomous task coverage

low measured false-release behavior on a validated benchmark

transparent human-review behavior

bounded resource consumption

candidate-bound evidence

reproducible gate decisions

useful evidence diversity

stable orchestration

clear failure semantics
```

No single metric should determine success.

The result should be considered as a portfolio.

---

# 145. What Would Constitute a Negative but Valuable POC Result

The POC may discover that:

```text
release gating costs more than expected

test diversity remains weak

false releases remain too frequent

human-review rate is too high

synthetic benchmark transfer is poor

gate instability is excessive

X1 scope is too broad
```

Those are not failed experiments.

They identify the current boundary of practical automation.

A rigorous negative result is more valuable than a demonstration engineered to always PASS.

---

# 146. What Would Constitute a Dangerous POC Result

A dangerous outcome would be a polished demonstration in which:

```text
candidate generated

many tests generated

all tests pass

green status shown
```

but:

```text
tests share the generator's blind spots

benchmark oracle is visible

candidate identity is not bound

thresholds are arbitrary

sample size is tiny

failed attempts are hidden

token costs are omitted

human escalation is unavailable
```

Such a demonstration could create more confidence than the evidence warrants.

This architecture is deliberately designed to make those limitations visible.

---

# 147. Relationship Between B2 and B3

`NOT-IMPLEMENTED.md` answers:

```text
What is still missing?
```

This document answers:

```text
Why is the system designed this way?
```

The distinction matters.

For example:

```text
B2:
Azure sandbox adapter is not yet implemented.

B3:
Generated code must execute through an abstract sandbox boundary
because execution isolation is independent from release policy.
```

Similarly:

```text
B2:
Production thresholds are not calibrated.

B3:
Thresholds must come from empirical risk/performance analysis
rather than familiar-looking arbitrary numbers.
```

The two documents should therefore be maintained together.

---

# 148. How to Maintain This Document

When an important architectural decision changes:

```text
DO:
    update this document
    state why
    identify affected components
    identify whether qualification must be repeated

DO NOT:
    silently make the code inconsistent with the rationale
```

If implementation evidence disproves a recommendation here, the code should not be forced to preserve an outdated design.

Instead:

```text
change architecture
+
document rationale
+
version affected capability
+
re-evaluate where necessary.
```

This document is a design record, not scripture.

---

# 149. Recommended Decision-Record Pattern

For major future changes, add a section or ADR containing:

```text
Decision

Context

Alternatives considered

Why selected

Assurance implications

Operational implications

Evaluation required

Known uncertainties
```

Example:

```text
Decision:
Replace Container Apps Jobs with another sandbox technology.

Context:
Security review requires stronger workload isolation.

Alternatives:
A
B
C

Selected:
B

Reason:
...

Affected Components:
10, 3, 5

Qualification Impact:
Execution environment fingerprint changes.
Relevant X1 campaigns must be rerun.
```

This prevents architectural history from disappearing into pull-request comments.

---

# 150. Recommended Commenting Standard for the Codebase

Code comments should explain:

```text
WHY

TRUST BOUNDARY

ASSUMPTION

FAILURE SEMANTICS

EXTENSION POINT
```

They should not merely restate obvious Python.

Poor:

```python
# Increment count.
count += 1
```

Useful:

```python
# Count each benchmark CASE once at this aggregation level.
#
# Do not increment this value for repeated stochastic runs of the same
# case; repeated runs are correlated observations and are tracked in the
# nested run-level metrics instead.
case_count += 1
```

This commenting standard is particularly important because the repository is intended to remain understandable to junior engineers and data scientists.

---

# 151. Recommended Error-Handling Standard

Never use:

```python
try:
    ...
except Exception:
    pass
```

in assurance-critical paths.

Prefer:

```python
try:
    evidence = await executor.execute(request)

except SandboxTimeoutError as exc:
    # Infrastructure timeout does not establish that the candidate is
    # incorrect. Preserve the technical failure separately so Component 9
    # can apply the configured retry/escalation policy.
    raise EvidenceCollectionUnavailable(
        run_id=request.run_id,
        reason="sandbox_timeout",
    ) from exc
```

Failure semantics are part of the architecture.

---

# 152. Recommended "Not Implemented" Standard

If a production implementation cannot be responsibly supplied, prefer:

```python
raise NotImplementedError(
    "Production implementation requires an enterprise-approved "
    "identity and resource configuration. See NOT-IMPLEMENTED.md NI-XX."
)
```

over:

```python
return True
```

or:

```python
# TODO
pass
```

A visible absence is safer than a fake success path.

---

# 153. Recommended Testing Pyramid for the Platform

The repository should eventually contain several layers.

```text
UNIT TESTS
    domain policies
    state transitions
    metrics
    serialization
    evidence normalization

CONTRACT TESTS
    shared contracts
    adapter expectations

INTEGRATION TESTS
    storage
    Service Bus
    Azure DevOps
    sandbox execution

END-TO-END X1 TEST
    task
    → candidate
    → gate
    → evidence
    → workflow result

EVALUATION CAMPAIGNS
    benchmark-level statistical qualification
```

Evaluation campaigns are not a substitute for software tests.

Software tests are not a substitute for evaluation campaigns.

---

# 154. Recommended Separation of Repository Tests and AI Evaluations

A useful repository structure might eventually distinguish:

```text
tests/
    unit/
    integration/
    end_to_end/

evaluations/
    benchmarks/
    campaigns/
    analysis/
```

Why?

Because:

```text
pytest passing
```

means approximately:

```text
the platform implementation behaves according to its software tests.
```

It does not mean:

```text
the AI automation capability is sufficiently reliable.
```

That second claim belongs to evaluation.

---

# 155. Security and Assurance Are Related but Distinct

Examples:

```text
Sandbox prevents unauthorized network access.
    → security control

Gate detects incorrect mortgage calculation.
    → correctness/assurance control

Evidence hash detects artifact corruption.
    → integrity control

Hidden oracle measures false release.
    → evaluation control
```

The architecture should not use the word "safe" without specifying which dimension is meant.

---

# 156. Auditability

For any gate decision, a reviewer should eventually be able to answer:

```text
What task was requested?

Which specification governed it?

Which baseline was used?

Which candidate was produced?

Which model/configuration produced it?

Which evidence was collected?

Which tests ran?

Which mutations ran?

Which evidence gaps existed?

Which policy was applied?

Why did the policy produce this outcome?

What did it cost?

Where are the immutable artifacts?
```

If these questions cannot be answered, the evidence model is incomplete.

---

# 157. Explainability of Gate Decisions

The gate should produce structured reason codes.

Example:

```text
Outcome:
HUMAN_REVIEW_REQUIRED

Reason codes:
    INSUFFICIENT_BOUNDARY_EVIDENCE
    MUTATION_SCORE_BELOW_POLICY_TARGET
    SEMANTIC_REVIEW_DISAGREEMENT

Evidence:
    E-102
    E-103
    E-110
```

This is preferable to:

```text
AI confidence = 0.62
```

Structured reason codes support:

```text
debugging

metrics

workflow routing

benchmark analysis

human review
```

---

# 158. Reason Codes Should Be Stable Contracts

Free-form explanations are useful for humans.

But automation should rely on stable reason codes.

For example:

```python
class GateReasonCode(StrEnum):
    REQUIRED_TEST_FAILED = "required_test_failed"
    COMPILATION_FAILED = "compilation_failed"
    CRITICAL_STATIC_FINDING = "critical_static_finding"
    INSUFFICIENT_EVIDENCE_DIVERSITY = (
        "insufficient_evidence_diversity"
    )
    MUTATION_EVIDENCE_INSUFFICIENT = (
        "mutation_evidence_insufficient"
    )
    EVIDENCE_BUDGET_EXHAUSTED = (
        "evidence_budget_exhausted"
    )
```

Comments should explain each code's intended semantics.

Human-readable explanations can accompany them.

---

# 159. Why Reason Codes Matter for Evaluation

Component 5 can aggregate:

```text
30% review due to insufficient diversity

20% review due to budget exhaustion

10% failure due to compilation

5% failure due to critical static findings
```

This tells us where platform improvement should focus.

Without structured reasons, failure analysis becomes manual text mining.

---

# 160. Budget Exhaustion Is a Legitimate Outcome

Suppose the gate has:

```text
token budget
execution budget
wall-clock budget
```

and cannot obtain required evidence within those limits.

It should not pretend the evidence is sufficient.

A legitimate result is:

```text
HUMAN_REVIEW_REQUIRED

reason:
EVIDENCE_BUDGET_EXHAUSTED
```

This makes economic limits part of the system's explicit behavior.

---

# 161. Cost Is Part of Capability, Not an Afterthought

Two configurations may have identical benchmark success:

```text
Configuration A
$1 equivalent cost per task

Configuration B
$40 equivalent cost per task
```

They are not operationally equivalent.

Likewise:

```text
Configuration A
30 seconds

Configuration B
45 minutes
```

may have different usefulness.

Therefore capability evaluation should eventually consider a multi-dimensional frontier:

```text
quality

false release

review rate

latency

cost
```

rather than quality alone.

---

# 162. Latency Should Be Decomposed

Record at least:

```text
queue latency

change-generation latency

sandbox startup latency

deterministic-test latency

AI gate latency

mutation latency

evidence-persistence latency

workflow-publication latency
```

This helps determine whether the platform is slow because of:

```text
LLM reasoning
```

or:

```text
infrastructure overhead.
```

That distinction matters for optimization.

---

# 163. Cost Should Also Be Decomposed

Recommended categories:

```text
LLM_CHANGE_GENERATION

LLM_GATE_TEST_SYNTHESIS

LLM_GATE_SEMANTIC_REVIEW

LLM_DIVERSITY_MAPPING

SANDBOX_COMPUTE

MUTATION_COMPUTE

STORAGE

MESSAGING

OBSERVABILITY

HUMAN_REVIEW
```

The exact taxonomy may evolve.

The important principle is to avoid a single unexplained:

```text
AI COST.
```

---

# 164. Why Human Review Cost Must Be Included

A selective automation platform can appear cheap if human escalation is excluded.

Example:

```text
LLM cost = $0.50/task
```

but:

```text
60% of tasks require 20 minutes of senior review.
```

The true operating cost is materially different.

Component 8 should therefore eventually consume human-review effort from the external workflow.

---

# 165. Production Monitoring Should Preserve Candidate Lineage

After deployment:

```text
Deployment D
```

should link back to:

```text
Candidate C

GateDecision G

Run R

TaskSpecification S
```

This allows later incidents to be traced back to the exact automation configuration that produced the code.

Conceptually:

```text
Operational Incident
       │
       ▼
DeploymentId
       │
       ▼
CandidateId
       │
       ▼
GateDecision
       │
       ▼
Evidence Portfolio
```

This becomes valuable if feedback is introduced later.

---

# 166. Business KPI Lineage

Likewise, where technically and organizationally feasible:

```text
Business / Process Observation
       │
       ▼
Application / Deployment
       │
       ▼
Candidate
       │
       ▼
Automation Run
```

However, this linkage establishes lineage, not causal proof.

Other changes may have occurred simultaneously.

Causal attribution requires stronger study design.

---

# 167. Causal Attribution Is a Separate Analytical Problem

Suppose after an automated code release:

```text
mortgage processing time falls 5%.
```

It would be incorrect to automatically conclude:

```text
AI engineering automation caused a 5% improvement.
```

Possible confounders include:

```text
other releases

staffing changes

volume changes

policy changes

seasonality

upstream system changes
```

If causal attribution becomes important, appropriate methods may include:

```text
controlled rollout

A/B design where feasible

difference-in-differences

matched comparison

interrupted time series
```

That analytical layer is beyond the first engineering POC.

---

# 168. Why Feedback Is Postponed

A future system might use production outcomes to modify:

```text
skills

prompts

gate thresholds

benchmark composition
```

Automatically doing so introduces a self-modifying assurance system.

That raises difficult questions:

```text
Who approved the new policy?

Was it requalified?

Did benchmark leakage occur?

Did production noise alter the gate?

Can the old version be reproduced?
```

Therefore feedback should initially be:

```text
OBSERVE
+
ANALYZE
```

not:

```text
AUTOMATICALLY MODIFY.
```

---

# 169. Evaluation Governance

Eventually, changes to:

```text
benchmark

hidden oracle

gate policy

model configuration

skill

task scope
```

should have controlled ownership.

Otherwise an optimization team could accidentally tune both:

```text
the system
```

and:

```text
the exam
```

until performance looks artificially strong.

Separation between capability development and final qualification is desirable.

---

# 170. Benchmark Leakage Detection

Potential leakage paths include:

```text
oracle files accidentally mounted into sandbox

hidden tests present in repository history

prompt contains expected answer

artifact credentials allow hidden-store access

benchmark IDs encode defect type

reference patch stored in accessible location
```

The POC should include explicit checks for these conditions.

A high benchmark score is meaningless if the answer key is visible.

---

# 171. Evaluation Campaign Reproducibility Record

Each campaign should preserve something equivalent to:

```yaml
campaign_id: "..."

capability:
  task_type: "X1"
  specification_sha256: "..."

benchmark:
  benchmark_id: "..."
  benchmark_version: "..."
  manifest_sha256: "..."

change_execution:
  configuration_sha256: "..."
  model: "..."

release_gate:
  policy_sha256: "..."
  configuration_sha256: "..."

execution:
  runner_image_digest: "..."

statistics:
  method_version: "..."

started_at: "..."
completed_at: "..."
```

The exact schema belongs in the implementation.

The principle is that a result should identify the experiment that produced it.

---

# 172. Comparison Between Capability Versions

Suppose:

```text
X1-A

task success 75%
false release 2%
review 35%
cost $X
```

and:

```text
X1-B

task success 82%
false release 4%
review 15%
cost $Y
```

There may be no universally superior configuration.

Component 5 should support side-by-side comparison.

Risk owners may prefer A despite lower automation coverage.

Business owners may prefer B only if the higher false-release rate is acceptable.

The system should expose the trade-off rather than silently optimize one scalar objective.

---

# 173. Pareto Thinking

A useful analytical concept is the Pareto frontier across:

```text
false release ↓

human review ↓

cost ↓

latency ↓

task success ↑
```

A configuration is clearly unattractive if another configuration is:

```text
safer

cheaper

faster

and

more capable.
```

Otherwise selection may require explicit business/risk preference.

This is more disciplined than declaring one universal "AI quality score."

---

# 174. Model Confidence Is Not Gate Confidence

If an LLM returns:

```text
confidence = 0.94
```

that number should not automatically be interpreted as a calibrated probability that the code is correct.

Model self-reported confidence can be poorly calibrated.

The gate should prioritize external evidence.

If model confidence is retained, label it appropriately:

```text
MODEL_SELF_ASSESSMENT
```

rather than:

```text
PROBABILITY_OF_CORRECTNESS.
```

---

# 175. Confidence Should Be Earned Through Evaluation

If the platform eventually produces a calibrated risk estimate such as:

```text
estimated probability of unacceptable release
```

that estimate should be derived and validated against held-out empirical outcomes.

It should not simply be copied from an LLM's token probability or verbal confidence.

Calibration itself becomes an evaluation problem.

---

# 176. The Gate Does Not Need to Predict Everything

The release gate does not need to perfectly predict every future production failure.

Its role is narrower:

```text
enforce known hard requirements

collect useful independent evidence

detect likely candidate defects

recognize insufficient evidence

route uncertainty appropriately
```

Production monitoring remains necessary because some failures cannot be reproduced pre-release.

---

# 177. Defense in Depth

The overall assurance model is layered.

```text
TaskSpecification
      │
      ▼
bounded authority

ChangeExecution
      │
      ▼
candidate

ReleaseGate
      │
      ▼
pre-release assurance

Workflow Approval
      │
      ▼
organizational control

Sandbox / Deployment Controls
      │
      ▼
technical containment

Operational Monitoring
      │
      ▼
post-release detection

Rollback / Incident Process
      │
      ▼
recovery
```

No single layer should be presented as infallible.

---

# 178. Why This Architecture Is Suitable for an Enterprise POC

The design deliberately allows the first POC to be:

```text
small in scope
```

while still preserving:

```text
production-shaped interfaces.
```

For example:

```text
one X1 capability

one repository

one Azure DevOps integration

two controlled execution jobs

one evidence store

one benchmark corpus
```

can exercise the important boundaries without implementing an enterprise-wide coding platform.

This allows the architecture itself to be tested before broad investment.

---

# 179. What Should Be Abstracted During the First Demo

The first demo does not need full automation of:

```text
task intake classification

business prioritization

production deployment

human-review UI

business KPI integration

Finance systems

dynamic credential brokering
```

These can be manual or abstracted.

The core demo should focus on:

```text
CHANGE EXECUTION

RELEASE GATING

PIPELINE-LEVEL EVALUATION.
```

This preserves the original POC objective.

---

# 180. What Must Not Be Abstracted Away

Some elements are essential to the hypothesis and should be real enough to test.

These include:

```text
candidate identity

controlled execution

independent gate evidence

deterministic gate policy

evidence persistence

hidden benchmark oracle

pipeline metrics

token/cost measurement

PASS / FAIL / REVIEW semantics
```

If these are mocked away, the demo will not answer the central research question.

---

# 181. Azure POC Philosophy

Azure should provide infrastructure.

It should not dictate the domain architecture.

Conceptually:

```text
DOMAIN

ChangeExecutionService
ReleaseGateService
EvaluationCampaignRunner
Orchestrator
Evidence contracts


ADAPTERS

Azure Container Apps Jobs
Azure Blob Storage
Azure Service Bus
Azure DevOps
Azure Monitor / Application Insights
Azure identity services
```

This makes the code easier to test and prevents cloud SDK calls from spreading through the scientific/evaluation logic.

---

# 182. Local Development Must Remain Possible

A junior engineer or data scientist should be able to understand and exercise significant portions of the platform without provisioning the full Azure environment.

Therefore ports should have local/test implementations where safe.

Examples:

```text
LocalEvidenceRepository

DeterministicSandboxStub

InMemoryCorrelationStore

SyntheticModelAdapter
```

These are for software development and testing.

They must be clearly distinguished from production adapters.

---

# 183. Local Stubs Must Not Produce False Assurance

A local stub should never pretend to prove:

```text
Azure isolation works

managed identity works

Service Bus durability works

production evidence retention works
```

It proves only the domain logic around the adapter.

Integration tests must separately test the actual Azure implementation.

This distinction should appear in comments and test names.

---

# 184. Example Naming Convention

Prefer names that reveal responsibility:

```text
ReleaseGateService

EvidencePlanner

EvidenceDiversityMapper

GatePolicyEvaluator

AzureContainerAppsJobRunner

LocalDeterministicSandboxRunner

AzureBlobEvidenceRepository

InMemoryEvidenceRepository
```

Avoid ambiguous names such as:

```text
AIManager

Engine

Processor

Helper

Utils
```

unless the scope is genuinely obvious.

Clear naming is especially important for junior maintainers.

---

# 185. Domain Objects Should Be Immutable Where Practical

Objects such as:

```text
CandidateArtifact

GateDecision

ExecutionReceipt

BenchmarkResult
```

represent historical facts.

Prefer creating a new object rather than mutating an old fact.

Example:

```text
Candidate C1
    → GateDecision G1

repair

Candidate C2
    → GateDecision G2
```

not:

```text
Candidate C1 changed in place
and old G1 now ambiguously refers to it.
```

---

# 186. Time Must Be Explicit

Evidence should use timezone-aware timestamps.

Avoid:

```python
datetime.now()
```

without timezone.

Prefer:

```python
from datetime import datetime, timezone

created_at = datetime.now(timezone.utc)
```

where compatible with the shared contracts.

This seems minor until evidence from multiple services must be ordered reliably.

---

# 187. Randomness Must Be Visible

Where stochastic behavior exists, preserve:

```text
seed where supported

temperature

sampling configuration

number of candidates

number of retries
```

If the external model does not support reproducible seeds, document that limitation.

Do not describe a stochastic experiment as perfectly reproducible when it is not.

---

# 188. Deterministic Tests Must Actually Be Checked for Determinism

Some tests are flaky.

Therefore:

```text
test implemented in ordinary code
```

does not automatically mean:

```text
deterministic evidence.
```

The benchmark and gate may eventually need to detect or flag:

```text
timing-sensitive tests

network-dependent tests

random tests without controlled seed

environment-dependent tests
```

A flaky test should not become a hard release veto without appropriate handling.

---

# 189. External Dependencies

The first X1 should minimize external dependencies.

Where external systems are unavoidable, prefer:

```text
mocked deterministic service

recorded fixture

local emulator

contract test
```

for gate execution.

Live external dependencies can introduce:

```text
flakiness

cost

data leakage

non-reproducibility

rate limits
```

They complicate assurance.

---

# 190. Security Scanning

Security scanning should preferably use established deterministic or rule-based tooling where applicable.

AI can augment security reasoning but should not replace existing scanners simply because the platform is AI-oriented.

Pattern:

```text
existing security scanner
        │
        ▼
normalized findings
        │
        ▼
GatePolicy

+

AI adversarial reasoning
        │
        ▼
additional hypotheses
```

This preserves defense in depth.

---

# 191. Existing Enterprise Controls Should Be Reused

The platform should integrate with existing controls rather than duplicate them.

Potential examples include:

```text
repository branch policy

build validation

security scanning

artifact signing

release approval

change management

logging

identity governance
```

The AI-specific gate should add assurance where AI changes the engineering risk profile.

It should not create a parallel software-delivery universe unless necessary.

---

# 192. Why the Gate Still Adds Value When CI/CD Already Exists

Traditional CI/CD answers many questions:

```text
does it compile?

do known tests pass?

does scanner find known patterns?
```

The AI release gate adds value by asking:

```text
What might this generated change have misunderstood?

What new tests should exist specifically because of this change?

Which evidence classes are missing?

Can the tests detect plausible defects?

Are there semantic concerns not represented in the existing suite?
```

Therefore the gate should augment rather than replace established CI/CD.

---

# 193. Relationship to the Engineering Pipeline

The POC does not require redesigning the entire enterprise pipeline.

A practical integration point is:

```text
task
   │
   ▼
AI candidate
   │
   ▼
AI-specific release gate
   │
   ▼
normal PR / CI/CD process
```

Later maturity could integrate more deeply.

The first experiment should avoid unnecessary pipeline transformation.

---

# 194. Separation Between Release Gate and Existing CI

Some deterministic evidence may already come from existing CI.

The gate should be able to consume existing evidence rather than rerun everything unnecessarily.

However, evidence must remain candidate-bound.

For example:

```text
CI result
candidate commit abc123
```

can be incorporated into the evidence portfolio for:

```text
candidate abc123.
```

If the candidate changes, the old CI result is stale.

---

# 195. Evidence Reuse

Content-addressed evidence permits safe reuse under strict identity conditions.

For example:

```text
same candidate hash
+
same tool version
+
same configuration
+
same environment-relevant inputs
```

may allow reuse.

But reuse policy must be explicit.

A cached result from:

```text
different dependency lock
```

or:

```text
different candidate
```

must not silently be treated as equivalent.

---

# 196. Why This Document Is Long

The repository contains relatively simple top-level services.

The difficult part is not merely Python syntax.

The difficult part is preserving distinctions such as:

```text
candidate correctness
versus
platform reliability

AI evidence
versus
deterministic evidence

technical PASS
versus
organizational release approval

test count
versus
independent evidence

benchmark performance
versus
production performance

operational success
versus
business value

estimated savings
versus
realized savings
```

If these distinctions disappear during implementation, the code can remain technically elegant while the assurance model becomes invalid.

This document exists to prevent that.

---

# 197. Current Overall Doubts

Several important questions remain genuinely unsettled.

First, it is not yet established that the proposed evidence-diversity machinery will materially outperform simpler alternatives at acceptable cost. It is plausible that a smaller combination of strong deterministic tests, mutation testing, static analysis, and a second independent model captures most of the benefit. The POC should therefore treat the Evidence Diversity Mapper as an experimentally testable architectural hypothesis. Ablation studies are important.

Second, a narrow synthetic X1 benchmark can demonstrate internal technical capability but cannot establish that the system is ready to replace a broad population of real L1 engineering work. Real work contains ambiguity, organizational knowledge, dependency complexity, incomplete documentation, and unusual repositories that synthetic cases may underrepresent. Expansion from X1 to wider L1 scope should therefore occur incrementally and only after evidence supports it.

---

# 198. Additional Doubts About Statistical Assurance

The relationship between evidence quantity and statistical confidence requires particular caution.

Generated tests are often correlated.

Repeated model calls are often correlated.

Different models may have correlated training data and reasoning patterns.

Mutation operators cover only selected defect classes.

Therefore the platform should not claim a mathematically precise probability of candidate correctness merely because it has accumulated many artifacts.

The strongest early statistical claims should probably remain at the **benchmark-task / pipeline level**, where observable outcomes against hidden oracles can be counted transparently.

Even there, benchmark representativeness remains a separate source of uncertainty.

---

# 199. Additional Doubts About Economics

It is possible for the technical POC to succeed while the economic case remains weak.

For example:

```text
automation coverage is moderate

gate cost is high

human-review rate is substantial

benchmark maintenance is expensive
```

The system might still be technically impressive but fail to reduce total engineering cost.

Conversely, even modest automation may be economically useful if it removes high-volume repetitive contractor work.

Therefore technical qualification and economic evaluation should remain separate until empirical operating data exists.

---

# 200. Additional Doubts About Enterprise Deployment

The architecture deliberately does not settle:

```text
production sandbox technology

enterprise approval authority

retention policy

release authorization

exact Azure identity model

real X1 definition

acceptable false-release threshold
```

Those are not omissions that should be filled by guessing.

They require platform engineering, security, risk, engineering leadership, and potentially Finance or governance input.

B2 identifies these gaps explicitly.

B3 explains why the code should preserve boundaries around them.

---

# 201. Final Architectural Position

The architecture should not be understood as:

```text
AI writes code
+
AI checks code
+
AI releases code.
```

The intended model is:

```text
HUMANS / PLATFORM OWNERS
define bounded authority
        │
        ▼
AI
generates candidate
        │
        ▼
AI + DETERMINISTIC TOOLS
construct heterogeneous evidence
        │
        ▼
DETERMINISTIC POLICY
interprets evidence
        │
        ├── PASS
        ├── FAIL
        └── ABSTAIN / HUMAN REVIEW
        │
        ▼
EXISTING ENGINEERING GOVERNANCE
controls release
        │
        ▼
OPERATIONAL MEASUREMENT
observes real behavior
        │
        ▼
PROCESS / BUSINESS MEASUREMENT
estimates downstream value
```

Separately:

```text
HIDDEN BENCHMARK
        │
        ▼
EvaluationCampaignRunner
        │
        ▼
measures whether the entire automation system
actually deserves the level of trust being proposed.
```

That final separation is essential.

The release gate asks:

> **Should this candidate pass?**

The evaluation system asks:

> **Should we trust this gate and change-generation system to make that decision for this class of work?**

The enterprise ultimately asks:

> **Is the resulting level of selective automation safe, useful, operationally manageable, and economically worthwhile?**

Those are three different questions.

The repository should preserve them as three different questions.

