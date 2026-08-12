# L1 Engineering Automation POC
## AI-Led Change Execution, Evidence-Based Release Gating, and Pipeline-Level Evaluation
---
## 1. Purpose
This repository implements a proof of concept for automating bounded software-engineering tasks that would otherwise be performed manually within an L1 engineering workflow.
The central hypothesis is deliberately narrower than "replace L1 developers with AI."
The hypothesis being tested is:
> For a well-defined engineering task type, such as `X1`, can an AI-led change-execution capability generate a candidate code change, can an independently designed release gate gather sufficiently diverse evidence to decide whether that exact candidate may proceed automatically, and can the complete capability be evaluated offline against validated hidden ground truth with quantified uncertainty, resource usage, and failure modes?
The repository is designed to make that question experimentally answerable.
It therefore separates:
1. code-change execution;
2. evidence planning;
3. evidence generation and collection;
4. evidence-diversity analysis;
5. deterministic execution;
6. release-gate decision making;
7. workflow/orchestration;
8. benchmark construction;
9. hidden-oracle evaluation;
10. pipeline-level evaluation;
11. statistical uncertainty;
12. resource and token measurement;
13. Azure infrastructure adapters;
14. composition and configuration.
The architecture intentionally avoids treating a single LLM call as either a software-engineering system or a release-assurance system.
---
## 2. Core Design Principle
The most important architectural separation is:

```text
AI PROPOSES A CHANGE
        |
        v
INDEPENDENT EVIDENCE IS COLLECTED
        |
        v
EXPLICIT POLICY DECIDES
        |
        v
PASS / FAIL / HUMAN_REVIEW_REQUIRED
```

The system should not ask the model that generated the code:
> "Do you think your code is correct?"
and treat the answer as release assurance.
AI can participate in assurance.
AI should not be the sole source of assurance.
Where deterministic evidence is available, deterministic evidence should be preferred.
Where AI-generated or AI-interpreted evidence is useful, its provenance should be explicit.
The final release-policy application should be deterministic wherever practical.
---
# 3. Business and Engineering Context
The POC is motivated by an enterprise engineering environment in which software-development work is organized across different engineering levels and some bounded L1 work is performed using variable-cost engineering capacity.
The economic hypothesis is that sufficiently standardized and bounded task categories may be candidates for AI-led execution.
However, economic attractiveness alone is insufficient.
Before automating such work, the organization needs evidence that the automation can:
- understand a defined task;
- modify the correct code;
- remain within authorized scope;
- produce a technically valid candidate;
- survive relevant tests;
- withstand independent evidence generation;
- detect plausible defects;
- abstain when assurance is insufficient;
- avoid releasing known-bad candidates;
- expose its evidence;
- measure its uncertainty;
- measure its cost;
- and be evaluated against ground truth.
This repository addresses that technical and evaluation problem.
It does not make workforce decisions.
---
# 4. The Unit of Automation
The preferred unit of automation is not:

```text
L1 developer
```

It is:

```text
qualified task capability
```

For example:

```text
X1 -> qualified for bounded automated execution
X2 -> qualified only with human review
X3 -> experimental
X4 -> unsupported
```

This distinction is important.
Engineering roles contain heterogeneous work.
A platform should therefore establish which task capabilities can be automated rather than infer that qualification of one task class implies automation of an entire role.
---
# 5. Scope of the POC
The initial POC intentionally focuses on a small number of components.
The primary runtime components are:

```text
ChangeExecutionService
ReleaseGateService
EvaluationCampaignRunner
```

Supporting components include:

```text
shared contracts
task/capability specifications
EvidencePlanner
EvidenceDiversityMapper
evidence collectors
deterministic execution
mutation analysis
gate policy
artifact repositories
benchmark infrastructure
hidden oracle
statistics
resource accounting
workflow adapters
Azure adapters
configuration
composition root
```

Several enterprise integrations may initially be represented through local adapters or explicit `NotImplementedError` implementations.
Those limitations are intentional and should be tracked in `NOT-IMPLEMENTED.md`.
---
# 6. What This POC Does Not Claim
This repository does not claim that:
- all L1 engineering work can be automated;
- autonomous software engineering is solved;
- AI-generated tests prove code correctness;
- mutation testing proves correctness;
- multiple LLMs provide mathematically independent evidence;
- synthetic benchmarks perfectly represent production work;
- confidence intervals eliminate benchmark bias;
- a passing release gate guarantees defect-free software;
- an offline benchmark automatically establishes production safety;
- operational success automatically produces business value;
- Azure infrastructure provides assurance by itself;
- human engineering judgment is unnecessary.
The purpose of the system is to measure these boundaries rather than hide them.
---
# 7. High-Level Architecture
The online path is:

```text
Task / Jira
    |
    v
Workflow Adapter
    |
    v
Capability Registry
    |
    v
Task Specification + Skill + Gate Policy
    |
    v
ChangeExecutionService
    |
    v
CandidateArtifact
    |
    v
ReleaseGateService
    |
    +--> EvidencePlanner
    |
    +--> EvidenceDiversityMapper
    |
    +--> deterministic evidence
    |
    +--> generated behavioral evidence
    |
    +--> static/compiler evidence
    |
    +--> mutation/adversarial evidence
    |
    v
EvidenceBundle
    |
    v
Deterministic Policy Engine
    |
    +----------+----------------------+
    |          |                      |
    v          v                      v
   PASS       FAIL         HUMAN_REVIEW_REQUIRED
    |                                  |
    v                                  v
 Release                        Workflow Signal
```

The offline qualification path is:

```text
BenchmarkFactory
      |
      v
BenchmarkValidation
      |
      v
Frozen Benchmark
      |
      v
EvaluationCampaignRunner
      |
      | invokes the SAME online capability
      v
ChangeExecutionService
      |
      v
CandidateArtifact
      |
      v
ReleaseGateService
      |
      v
GateDecision
      |
      +-----------------------------+
                                    |
Hidden Oracle ---------------------+
      |
      v
OracleAssessment
      |
      v
DecisionClassification
      |
      v
Campaign Metrics
      |
      +--> quality
      +--> uncertainty
      +--> resource usage
      +--> failure taxonomy
      +--> slice analysis
      |
      v
Qualification Evidence
```

---
# 8. Online and Offline Are Different Assurance Problems
The online release gate asks:
> Should this exact candidate be permitted to proceed automatically?
The offline evaluation campaign asks:
> How reliably does this exact versioned capability perform across a defined population of benchmark tasks?
These questions must not be confused.
A candidate passing a release gate does not qualify the overall automation capability.
Likewise, a qualified automation capability does not mean every generated candidate should pass.
A qualified capability should still be able to:

```text
PASS
FAIL
HUMAN_REVIEW_REQUIRED
```

individual candidates.
---
# 9. Repository Architecture
A recommended repository structure is:

```text
repository/
|
+-- README.md
+-- NOT-IMPLEMENTED.md
+-- DESIGN-RATIONALE.md
+-- pyproject.toml
|
+-- config/
|   |
|   +-- capabilities/
|   |   +-- x1/
|   |       +-- task.yaml
|   |       +-- gate-policy.yaml
|   |       +-- eval-spec.yaml
|   |       +-- SKILL.md
|   |
|   +-- environments/
|       +-- local.yaml
|       +-- azure-dev.yaml
|
+-- src/
|   +-- l1_automation/
|       |
|       +-- contracts/
|       |
|       +-- change_execution/
|       |
|       +-- release_gate/
|       |
|       +-- evidence/
|       |
|       +-- execution/
|       |
|       +-- mutation/
|       |
|       +-- workflow/
|       |
|       +-- evaluation/
|       |
|       +-- benchmark/
|       |
|       +-- statistics/
|       |
|       +-- resource_accounting/
|       |
|       +-- infrastructure/
|       |   +-- local/
|       |   +-- azure/
|       |
|       +-- configuration/
|       |
|       +-- bootstrap/
|       |
|       +-- architecture/
|
+-- tests/
|   |
|   +-- unit/
|   +-- contracts/
|   +-- architecture/
|   +-- configuration/
|   +-- integration/
|   +-- e2e/
|   +-- evaluation/
|
+-- tools/
    +-- run_b7_review.py
```

The exact physical layout may be adjusted to match the final repository.
The architectural boundaries should not.
---
# 10. Dependency Direction
The intended dependency direction is:

```text
CONTRACTS
    ^
    |
DOMAIN / APPLICATION
    ^
    |
PORTS
    ^
    |
INFRASTRUCTURE ADAPTERS
    ^
    |
COMPOSITION ROOT
```

Core application logic should not depend directly on Azure SDKs.
For example, avoid:

```python
class ReleaseGateService:
    def __init__(self):
        self.blob_client = BlobServiceClient(...)
```

Prefer dependency injection:

```python
class ReleaseGateService:
    def __init__(
        self,
        *,
        evidence_planner,
        evidence_collectors,
        policy_engine,
        evidence_repository,
    ):
        self._evidence_planner = evidence_planner
        self._evidence_collectors = evidence_collectors
        self._policy_engine = policy_engine
        self._evidence_repository = evidence_repository
```

The composition root determines whether those interfaces are backed by:

```text
local implementations
in-memory implementations
Azure implementations
```

---
# 11. Canonical Shared Contracts
Cross-component concepts should have one canonical representation.
Important contracts include:

```text
TaskRequest
TaskSpecification
CapabilityIdentity
CandidateArtifact
EvidenceArtifact
EvidenceBundle
EvidenceProvenance
ExecutionReceipt
GateDecision
GateOutcome
ResourceUsage
ModelUsage
BenchmarkCase
BenchmarkValidation
OracleAssessment
CampaignManifest
CampaignResult
```

Do not independently create:

```text
ChangeExecutionCandidate
ReleaseGateCandidate
EvaluationCandidate
```

when all three represent the same candidate.
Contract duplication eventually creates semantic drift.
---
# 12. Candidate Identity
The system must be able to establish exactly which artifact was evaluated.
Candidate identity should bind sufficient information to distinguish the candidate from other code states.
Conceptually:

```text
CandidateIdentity
    |
    +-- candidate_id
    +-- task_id
    +-- repository_identity
    +-- base_revision
    +-- patch_sha256
    +-- capability_identity
    +-- execution_image_digest
```

The release gate must evaluate the exact candidate represented by that identity.
A previously issued gate decision must not silently authorize a modified candidate.
---
# 13. Capability Identity
Evaluation results are meaningful only relative to a specific capability configuration.
A capability identity should therefore bind behaviorally important configuration such as:

```text
capability name
capability version
task specification
skill
gate policy
evaluation specification
model configuration
prompt/template identity
EvidencePlanner version
EvidenceDiversityMapper version
mutation strategy
execution environment
```

If a behaviorally material element changes, the system should create a new capability identity or otherwise establish that the previous qualification remains applicable.
---
# 14. Task Specification
Each supported task type should be explicitly specified.
For example:

```text
config/capabilities/x1/task.yaml
```

may define:

```yaml
task_type: X1
version: "1.0"
allowed_paths:
  - "src/**"
prohibited_paths:
  - ".github/**"
  - "infrastructure/production/**"
required_validation:
  - "pytest"
  - "python -m compileall src"
change_constraints:
  allow_dependency_changes: false
  allow_test_changes: true
```

The exact fields depend on X1.
The important design principle is that task policy should be explicit rather than buried inside an LLM prompt.
---
# 15. Skill Files
A task capability may include a `SKILL.md` or equivalent instruction artifact.
Its role is to describe how the automation should approach the engineering task.
It may include:
- task-specific reasoning guidance;
- repository conventions;
- expected workflow;
- relevant architectural patterns;
- prohibited behavior;
- validation expectations;
- escalation conditions.
Skills are part of capability configuration.
Material skill changes may therefore require re-evaluation.
---
# 16. ChangeExecutionService
`ChangeExecutionService` owns candidate generation.
Its conceptual contract is:

```text
TaskRequest
    +
TaskSpecification
    +
authorized repository context
    |
    v
ChangeExecutionService
    |
    v
CandidateArtifact
```

The service may use:
- an LLM;
- source code;
- task instructions;
- compiler artifacts;
- repository metadata;
- deterministic validation;
- iterative tool use.
It should not issue the final release authorization.
The architectural rule is:

```text
ChangeExecutionService proposes.
ReleaseGateService decides.
```

---
# 17. Change-Execution Provenance
A candidate should preserve provenance sufficient to investigate its creation.
Useful information includes:

```text
task identity
capability identity
repository revision
model configuration
prompt/template identity
candidate hash
execution environment
tool invocations
model usage
errors
timestamps
```

Hosted model execution may not always be perfectly reproducible.
The system should therefore prioritize strong provenance rather than promise exact replay where the underlying model provider cannot guarantee it.
---
# 18. ReleaseGateService
`ReleaseGateService` answers:
> Given this exact candidate and this exact gate policy, is sufficient evidence available to permit automated release?
The gate should coordinate evidence rather than act as one large AI reviewer.
Conceptually:

```text
CandidateArtifact
      |
      v
EvidencePlanner
      |
      v
EvidenceDiversityMapper
      |
      v
Evidence Collection
      |
      +--> repository tests
      |
      +--> generated tests
      |
      +--> static/compiler analysis
      |
      +--> mutation analysis
      |
      +--> structural analysis
      |
      +--> policy/scope checks
      |
      v
EvidenceBundle
      |
      v
GatePolicy
      |
      v
PASS / FAIL / HUMAN_REVIEW_REQUIRED
```

---
# 19. Human Review Semantics
Human review should not occur inside `ReleaseGateService`.
The gate should emit:

```text
HUMAN_REVIEW_REQUIRED
```

with structured reasons.
An external workflow may then:
- create a Jira item;
- assign a reviewer;
- hold the change;
- notify an operator;
- route the task to another process.
This preserves a clean boundary:

```text
gate determines automated assurance status
workflow manages human action
```

---
# 20. Why the Gate Should Not Be One LLM Call
Avoid making the final gate:

```python
decision = llm.ask(
    "Here is the candidate and all available information. "
    "Should we release it?"
)
```

This hides:
- evidence weighting;
- veto rules;
- abstention semantics;
- policy;
- uncertainty;
- reproducibility.
A stronger architecture is:

```text
LLM
 |
 v
typed evidence
deterministic tools
 |
 v
typed evidence
mutation analysis
 |
 v
typed evidence
all evidence
 |
 v
explicit policy
 |
 v
GateDecision
```

AI can reason.
Policy should remain inspectable.
---
# 21. EvidencePlanner
`EvidencePlanner` determines what evidence should be collected for a candidate.
Its inputs may include:

```text
TaskSpecification
CandidateArtifact
GatePolicy
available evidence capabilities
resource budget
```

Its output is an evidence plan.
The planner may use deterministic rules, AI assistance, or both.
The planner should not itself decide release.
It decides:

```text
what evidence should we seek?
```

The policy engine later decides:

```text
what does the collected evidence imply?
```

---
# 22. Evidence Diversity Mapper
One major risk in AI-led code generation is correlated blind spots.
If the same model:

```text
writes code
and
writes tests
```

the tests may inherit the same misunderstanding that produced the defect.
The `EvidenceDiversityMapper` exists to reduce evidence monoculture.
It may encourage evidence across dimensions such as:

```text
boundary conditions
negative cases
metamorphic properties
mutation-directed tests
alternate input structures
static structure
compiler artifacts
existing human-authored tests
alternate-model analysis
```

The mapper is a coordination layer.
It does not prove independence.
---
# 23. Diversity Is Not Independence
This distinction is critical.
Suppose one model generates 500 tests.
Those tests may be diverse in syntax while sharing one semantic misunderstanding.
Therefore:

```text
500 tests
```

does not imply:

```text
500 independent observations
```

The system should preserve evidence lineage so correlated evidence can be recognized.
---
# 24. Evidence Families
A useful conceptual taxonomy is:

```text
FAMILY A
Existing repository regression tests
FAMILY B
Compiler/static-analysis evidence
FAMILY C
Independently synthesized behavioral tests
FAMILY D
Mutation-directed evidence
FAMILY E
Metamorphic/property evidence
FAMILY F
Alternate-model review
FAMILY G
Execution/runtime evidence
FAMILY H
Policy/security evidence
```

The purpose is not to require every family for every task.
The purpose is to reason about missing forms of evidence rather than simply count tests.
---
# 25. Evidence Provenance
Evidence generated or interpreted using AI should record provenance.
Conceptually:

```python
@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    producer_type: str
    producer_identity: str
    generation_method: str
    execution_method: str
    interpretation_method: str
    parent_evidence_ids: tuple[str, ...]
    random_seed: int | None
    model_configuration_id: str | None
    prompt_template_sha256: str | None
```

The exact contract should follow the canonical implementation in the repository.
The principle is:

```text
evidence should be attributable
```

---
# 26. Deterministic and Nondeterministic Evidence
Do not classify evidence merely as:

```text
AI
or
non-AI
```

Instead distinguish:

```text
generation
execution
interpretation
```

For example:

```text
LLM generates test
       |
       v
deterministic runner executes test
       |
       v
deterministic assertion passes/fails
```

Generation is nondeterministic.
Execution may be deterministic.
Likewise:

```text
compiler generates AST
       |
       v
LLM interprets AST
```

The artifact is deterministic.
The interpretation is model-mediated.
These distinctions matter for assurance.
---
# 27. Static and Structural Evidence
The gate should not require an LLM to infer all program structure from raw source text.
Where useful, provide structured artifacts such as:

```text
ASTs
compiler diagnostics
type information
call graphs
dependency graphs
control-flow information
changed-symbol maps
coverage information
static-analysis findings
```

These artifacts can provide information that raw text review may miss.
However, if an LLM interprets them, the interpretation remains nondeterministic evidence.
---
# 28. Deterministic Execution
Generated code and tests should execute in a controlled environment.
The execution environment should capture relevant identity such as:

```text
container image digest
runtime version
dependency state
repository revision
environment configuration
```

Prefer immutable image digests to mutable tags.
For example:

```text
sha256:<digest>
```

is stronger identity than:

```text
x1-runner:latest
```

---
# 29. Mutation Testing
Mutation testing asks:
> If plausible defects were introduced into the code, would the tests detect them?
A mutation engine introduces controlled changes such as:

```text
comparison reversal
boolean inversion
boundary modification
removed condition
changed arithmetic operator
changed return behavior
```

Tests are then executed against the mutants.
A killed mutant indicates that the tests detected the introduced defect.
A surviving mutant indicates that the available tests did not detect it.
Mutation testing therefore evaluates test sensitivity.
It does not prove code correctness.
---
# 30. Mutation Evidence
Useful mutation metadata includes:

```text
mutation operator family
mutants generated
mutants executed
mutants killed
surviving mutants
equivalent or invalid mutants
timeout mutants
error mutants
```

Avoid reducing all mutation information to one percentage.
A mutation score can be useful.
It is not a probability that the candidate is correct.
---
# 31. Gate Policy
The final gate policy should distinguish:

```text
veto conditions
mandatory evidence
thresholded evidence
uncertainty conditions
review conditions
```

Illustratively:

```yaml
policy_version: "1.0"
veto_conditions:
  - compilation_failure
  - mandatory_regression_failure
  - unauthorized_file_change
mandatory_evidence_families:
  - repository_regression
  - static_analysis
  - independent_behavioral
  - mutation_analysis
review_conditions:
  - insufficient_evidence_diversity
  - unresolved_requirement_ambiguity
  - execution_environment_failure
  - statistical_uncertainty_too_high
```

These values are examples.
Actual X1 thresholds require empirical calibration.
---
# 32. Veto Evidence
Critical deterministic evidence should not become a statistical vote.
For example:

```text
mandatory regression test = FAIL
```

should not become:

```text
99 generated tests passed
1 mandatory regression failed
therefore 99% PASS
```

Some evidence has veto semantics.
Gate policy must make this explicit.
---
# 33. Failure Versus Missing Assurance
The gate must distinguish:

```text
evidence that the candidate is wrong
```

from:

```text
inability to gather sufficient evidence
```

Example:

```text
mandatory regression test reproducibly fails
```

may justify:

```text
FAIL
```

But:

```text
test-generation service unavailable
```

does not establish that the candidate is wrong.
It may justify:

```text
HUMAN_REVIEW_REQUIRED
```

because automated assurance could not be completed.
---
# 34. Evidence Budget
Release gating cannot collect evidence indefinitely.
The planner should eventually operate within explicit budgets such as:

```text
LLM tokens
LLM calls
deterministic executions
mutation executions
CPU time
wall time
estimated cost
```

Possible terminal states include:

```text
sufficient evidence to PASS
sufficient evidence to FAIL
insufficient evidence within budget
```

The third state naturally supports:

```text
HUMAN_REVIEW_REQUIRED
```

---
# 35. Adaptive Evidence Collection
Not every candidate should necessarily require maximum-cost evidence collection.
A future adaptive gate may operate approximately as:

```text
cheap deterministic evidence
        |
        v
obvious veto?
   |           |
  YES          NO
   |           |
   v           v
 FAIL     structural evidence
               |
               v
        enough evidence?
          |          |
         YES         NO
          |          |
          v          v
       DECIDE    generated /
                 mutation /
                 semantic evidence
                      |
                      v
                  DECIDE /
                   REVIEW
```

Adaptive stopping itself changes system behavior.
It must therefore be evaluated.
---
# 36. Workflow Layer
The workflow layer coordinates the end-to-end process.
Its responsibilities may include:

```text
receiving task events
resolving capability
invoking ChangeExecutionService
invoking ReleaseGateService
persisting workflow state
publishing results
handling retries
routing review signals
```

The workflow layer should not contain hidden release policy.
---
# 37. Jira Integration
Jira is an external workflow integration.
The core domain should not depend directly on Jira APIs.
Prefer:

```text
Jira Adapter
     |
     v
TaskRequest
     |
     v
Core Application
```

This allows the same application to be driven by:

```text
Jira
CLI
local fixtures
Azure Service Bus
evaluation campaigns
```

without rewriting core logic.
---
# 38. Idempotency
Message-based workflows may deliver a task more than once.
Therefore:

```text
duplicate delivery
```

must not accidentally produce:

```text
duplicate business operation
```

Use a stable external event identity to derive an idempotency key.
Conceptually:

```text
provider
   +
external event ID
   +
capability identity
       |
       v
idempotency key
```

Infrastructure retries must also remain distinct from intentional repeated evaluation trials.
---
# 39. Correlation IDs
Each end-to-end execution should preserve a correlation hierarchy such as:

```text
correlation_id
    |
    +-- task_id
    +-- run_id
    +-- candidate_id
    +-- evidence_ids
    +-- gate_decision_id
    +-- evaluation_case_id
```

This supports:
- debugging;
- auditability;
- cost attribution;
- evaluation;
- incident analysis.
---
# 40. Evidence Immutability
Assurance evidence should preferably be append-oriented and immutable.
Avoid:

```text
gate decision
    |
evidence overwritten later
```

because the historical decision becomes difficult to reconstruct.
Corrections should normally create new evidence artifacts.
The same principle applies to gate decisions.
---
# 41. EvaluationCampaignRunner
The `EvaluationCampaignRunner` evaluates the complete capability across benchmark tasks.
It should invoke the same logical online pipeline that production uses.
Avoid creating:

```text
production pipeline
and
special benchmark pipeline
```

with materially different behavior.
The preferred pattern is:

```text
EvaluationCampaignRunner
        |
        v
same online capability
        |
        v
CandidateArtifact
        |
        v
GateDecision
        |
        v
HiddenOracle
        |
        v
CampaignResult
```

---
# 42. BenchmarkFactory
For the POC, AI may assist in generating benchmark cases.
A benchmark case may include:

```text
starting codebase
known defect or requested change
public task description
hidden expected behavior
reference correction
hidden tests
validation metadata
```

AI generation alone does not create ground truth.
The benchmark must be validated.
---
# 43. Benchmark Validation
A stronger benchmark-construction sequence is:

```text
AI-assisted benchmark generation
        |
        v
build baseline
        |
        v
reproduce known problem
        |
        v
apply reference correction
        |
        v
verify expected behavior
        |
        v
run hidden tests
        |
        v
perform perturbation / mutation checks
        |
        v
independent validation
        |
        v
freeze benchmark case
```

The result should be described as:

```text
AI-assisted
empirically validated
frozen benchmark
```

rather than simply:

```text
AI-generated ground truth
```

---
# 44. Benchmark Quality Is an Evaluation Problem
Hidden does not mean correct.
A benchmark can contain:

```text
underspecified tasks
incorrect expected behavior
overly restrictive tests
implementation-specific tests
inadequate coverage
environment instability
incorrect reference patches
duplicate cases
unrepresentative tasks
```

Benchmark quality must therefore be evaluated separately from model performance.
---
# 45. Hidden Oracle
The hidden oracle establishes whether a benchmark candidate actually satisfies the benchmark task.
The oracle should prefer deterministic validation where possible.
It may use:

```text
hidden tests
expected behavior
reference artifacts
deterministic execution
controlled adjudication
```

The hidden oracle should not simply be:

```text
another LLM saying the patch looks correct
```

AI-assisted adjudication may be useful where deterministic evidence is insufficient, but it must be explicitly represented as such.
---
# 46. Oracle Isolation
The online capability must not access hidden oracle information.
Conceptually:

```text
CHANGE IDENTITY
    cannot read hidden oracle
GATE IDENTITY
    cannot read hidden oracle
ORACLE IDENTITY
    can read hidden oracle
```

This separation should exist both:

```text
in source-code dependency boundaries
```

and:

```text
in Azure identity / RBAC boundaries
```

---
# 47. Decision Classification
Offline evaluation compares:

```text
GateDecision
```

against:

```text
OracleAssessment
```

Important outcomes include:

```text
correct automated release
false release
correct rejection
false rejection
correct abstention
unnecessary abstention
oracle unresolved
benchmark invalid
infrastructure failure
```

These should not be collapsed into one generic accuracy number.
---
# 48. False Release
A particularly important event is:

```text
gate = PASS
oracle = INCORRECT
```

This is a:

```text
FALSE RELEASE
```

For an automated engineering platform, false-release behavior may be more important than aggregate accuracy.
Every false release should be retained as an investigation artifact.
---
# 49. Core Pipeline Metrics
Useful top-level metrics include:

```text
Capability Success Rate
Automated Release Rate
False Release Rate
False Rejection Rate
Review / Abstention Rate
Conditional Release Precision
End-to-End Automation Success Rate
```

Each answers a different question.
Do not collapse them into:

```text
AI score
```

---
# 50. Conditional Release Precision
One intuitive metric is:

```text
correct automated releases
--------------------------
all automated releases
```

This answers:
> When the platform automatically releases something, how often is that decision correct?
However, release precision must be paired with automation coverage.
A system that releases one trivial task and sends every other task to humans may have excellent release precision but negligible automation value.
---
# 51. Risk-Coverage Tradeoff
Release gating creates a tradeoff between:

```text
automation coverage
```

and:

```text
residual release risk
```

Conceptually:

```text
more conservative gate
        |
        +--> lower automated release rate
        |
        +--> potentially lower false-release exposure
more aggressive gate
        |
        +--> higher automated release rate
        |
        +--> potentially higher false-release exposure
```

The acceptable operating point is not purely a model decision.
It is a governance and business decision informed by evaluation evidence.
---
# 52. Statistical Unit of Observation
One of the most important evaluation principles in this repository is:

```text
test count != independent sample count
```

Suppose:

```text
100 benchmark tasks
300 generated tests per task
```

The top-level capability evaluation does not automatically have:

```text
n = 30,000
```

The natural first-level unit for task success may still be:

```text
n = 100 benchmark tasks
```

The tests primarily provide evidence about each candidate.
---
# 53. Confidence Intervals
Confidence intervals should always identify the quantity being estimated.
Examples:

```text
task success rate
false-release rate
automated-release rate
conditional release precision
abstention rate
```

Avoid statements such as:

```text
confidence = 97%
```

without defining confidence in what quantity.
---
# 54. Small Samples
A small number of benchmark tasks cannot establish extremely small failure probabilities merely because each task executes thousands of tests.
For example:

```text
20 benchmark tasks
1,000 tests per task
zero false releases
```

does not demonstrate a false-release probability below:

```text
1 / 20,000
```

for future engineering tasks.
The unit of generalization matters.
---
# 55. Wilson Intervals
For simple binary benchmark outcomes, Wilson score intervals are a reasonable deterministic starting point.
The repository includes or should include a deterministic implementation rather than asking an LLM to calculate statistical intervals.
However, Wilson intervals do not solve:

```text
benchmark correlation
benchmark bias
task clustering
contamination
incorrect labels
unrepresentative task distributions
```

Mathematical precision should not be confused with epistemic validity.
---
# 56. Clustered Benchmark Data
Benchmark tasks may be clustered by:

```text
repository
task family
code template
difficulty
generator
technology
```

If clustering is substantial, simple binomial intervals may understate uncertainty.
For the POC:
- preserve cluster metadata;
- report relevant slices;
- avoid exaggerated precision.
More mature analysis may later use:

```text
cluster bootstrap
hierarchical models
mixed-effects models
```

where justified.
---
# 57. Repeated Model Runs
Because AI generation is nondeterministic, qualification may execute multiple runs for the same benchmark task.
For example:

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

These repeated runs help measure:

```text
generation instability
gate instability
token variability
task-level variance
```

But three runs of one benchmark task do not become three unrelated benchmark tasks.
The hierarchical structure must be preserved.
---
# 58. Calibration and Qualification
Avoid repeatedly tuning the gate on the same dataset used to claim final performance.
Prefer:

```text
DEVELOPMENT / CALIBRATION SET
        |
        v
tune prompts / planner / gate
QUALIFICATION SET
        |
        v
estimate final capability behavior
```

Where possible, preserve a hidden qualification subset.
If the POC is too small to support clean separation, document that limitation explicitly.
---
# 59. Benchmark Representativeness
A benchmark can be internally valid but still fail to represent actual L1 work.
For example:

```text
500 validated Python bug fixes
```

do not necessarily represent:

```text
the real distribution of enterprise L1 engineering tasks
```

The benchmark should eventually be compared with historical task characteristics.
Possible descriptors include:

```text
task category
repository
language
patch size
files changed
dependency depth
context required
task ambiguity
test surface
```

---
# 60. Pipeline Failure Taxonomy
Pipeline failures should be typed.
Examples include:

```text
CHANGE_EXECUTION_FAILURE
INVALID_CANDIDATE
RELEASE_GATE_FAIL
RELEASE_GATE_REVIEW
RELEASE_GATE_INFRASTRUCTURE_FAILURE
ORACLE_INCORRECT
ORACLE_UNRESOLVED
BENCHMARK_INVALID
ENVIRONMENT_FAILURE
TIMEOUT
```

Do not collapse every non-success into:

```text
FAILED
```

Different failures require different remediation.
---
# 61. Infrastructure Failures
Suppose a campaign contains:

```text
100 planned tasks
80 valid completed tasks
20 infrastructure failures
```

Reporting:

```text
80% capability success
```

would incorrectly classify infrastructure failures as model failures.
Reporting:

```text
100% capability success
```

would hide serious platform unreliability.
Report separately:

```text
capability performance among valid trials
campaign execution reliability
```

---
# 62. Timeout Semantics
Timeouts should be typed.
Possible categories include:

```text
model timeout
test timeout
candidate-generation timeout
evidence-budget exhaustion
workflow timeout
infrastructure timeout
```

A deterministic test timeout may be candidate evidence.
A model endpoint timeout is usually infrastructure evidence.
An evidence-budget exhaustion may justify human review.
Avoid one generic:

```text
TIMEOUT = FAIL
```

---
# 63. Token Accounting
Token consumption should be measured by component and purpose.
Useful categories include:

```text
change_execution.context
change_execution.reasoning
change_execution.patch_generation
gate.planning
gate.test_generation
gate.diversity
gate.semantic_review
gate.mutation_generation
gate.evidence_interpretation
evaluation.benchmark_generation
evaluation.oracle_assistance
```

Do not assume:

```text
release gate tokens < code-generation tokens
```

The gate may be expensive.
Measure rather than assume.
---
# 64. Tokens Versus Deterministic Compute
Once an AI-generated test exists, executing that test repeatedly normally consumes deterministic compute rather than new LLM tokens.
Therefore separate:

```text
LLM usage
```

from:

```text
sandbox CPU
wall time
test executions
mutation executions
```

Narrower statistical uncertainty from additional independent AI-generated evidence may increase token usage.
Repeated deterministic execution primarily increases compute usage.
---
# 65. ResourceUsage
A resource contract may conceptually include:

```python
@dataclass(frozen=True, slots=True)
class ResourceUsage:
    model_usage: tuple[ModelUsage, ...]
    sandbox_cpu_seconds: float
    sandbox_wall_seconds: float
    test_executions: int
    mutation_executions: int
    bytes_read: int = 0
    bytes_written: int = 0
```

Use the repository's canonical contract if it differs.
Resource measurement belongs near execution.
Economic interpretation belongs in a separate cost/value layer.
---
# 66. Cost Is Not Assurance
A cheap candidate is not necessarily safe.
An expensive gate is not necessarily strong.
Therefore:

```text
resource measurement
```

and:

```text
assurance evaluation
```

must remain separate.
Later analysis can ask:

```text
cost per successful automated task
cost per correct automated release
cost per avoided human intervention
```

without contaminating the release policy.
---
# 67. Operational Metrics
After deployment, the platform may expose operational metrics such as:

```text
tasks received
tasks completed
task latency
candidate-generation latency
gate latency
queue depth
retry rate
dead-letter rate
infrastructure failure rate
review rate
token usage
compute usage
```

These measure platform operation.
They are not automatically measures of code correctness.
---
# 68. From Evals to Business KPIs
A useful measurement chain is:

```text
CAPABILITY / EVAL METRICS
        |
        v
RELEASED BEHAVIOR
        |
        v
OPERATIONAL OUTCOMES
        |
        v
PROCESS OUTCOMES
        |
        v
BUSINESS KPIs
```

The intermediate process-outcome layer is important.
---
# 69. Process Outcomes
For example:

```text
EVAL
----
generated change is correct
        |
        v
OPERATIONAL
-----------
service executes successfully
latency acceptable
no runtime failure
        |
        v
PROCESS OUTCOME
---------------
mortgage-processing step completes
manual intervention reduced
rework reduced
cycle time reduced
        |
        v
BUSINESS KPI
------------
processing cost
service-level performance
customer completion
business throughput
```

Business KPIs are affected by many confounders.
Do not directly attribute a business KPI movement to an eval score without causal evidence.
---
# 70. Candidate Release Gate Versus Capability Qualification Gate
The architecture contains two conceptually different gates.
## Candidate Release Gate
Operates online.
Question:
> Should this candidate proceed automatically?
## Capability Qualification Gate
Operates offline.
Question:
> Is this versioned automation capability sufficiently validated to operate for X1?
The distinction should remain explicit in code, documentation, dashboards, and governance.
---
# 71. Qualification Policy
A future qualification policy may include constraints such as:

```text
maximum false-release upper confidence bound
minimum automated-release coverage
minimum task success rate
maximum infrastructure failure rate
maximum unresolved benchmark defect rate
maximum cost per successful automated task
```

This repository should not invent arbitrary production thresholds.
Those values require:

```text
POC evidence
task risk
engineering judgment
governance input
business economics
```

---
# 72. Azure Architecture
The Azure implementation should preserve the domain architecture rather than redefine it.
A possible deployment shape is:

```text
Jira / External Trigger
        |
        v
Workflow Adapter
        |
        v
Azure Service Bus
        |
        v
Worker / Container App / Function
        |
        v
Application Services
        |
        +--> Azure OpenAI
        |
        +--> repository adapter
        |
        +--> execution environment
        |
        +--> evidence storage
        |
        +--> telemetry
```

The exact compute service may vary.
The domain contracts should not.
---
# 73. Azure Service Bus
Service Bus can provide asynchronous workflow delivery.
The application must nevertheless assume duplicate delivery is possible.
Therefore consumers should be idempotent.
Transport-level duplicate detection may be useful.
It should not replace application-level idempotency.
---
# 74. Azure Storage
Azure storage may hold artifacts such as:

```text
candidate manifests
evidence
execution receipts
gate decisions
campaign manifests
campaign results
```

Hidden oracle artifacts should use a separate access boundary.
The core application should depend on repository interfaces rather than Azure Blob SDK types.
---
# 75. Azure Identity
Use managed identity or equivalent workload identity where practical.
Separate identities should exist for materially different trust domains.
Conceptually:

```text
change-execution identity
release-gate identity
evaluation/oracle identity
```

The online identities should not have access to hidden benchmark truth.
---
# 76. Azure OpenAI
Model access should be encapsulated behind application ports.
Avoid spreading Azure OpenAI SDK calls throughout the codebase.
A model adapter should normalize:

```text
request
response
model identity
token usage
errors
latency
structured-output validation
```

into canonical application contracts.
---
# 77. Configuration
Configuration should be explicit and validated.
Separate:

```text
capability configuration
environment configuration
secrets
```

Examples:

```text
task behavior -> version-controlled capability files
Azure endpoint -> environment configuration
API credential -> secret store / managed identity
```

Do not hide assurance thresholds in undocumented environment variables.
Gate policy is part of the capability definition.
---
# 78. Composition Root
Object construction should be centralized.
Conceptually:

```python
def build_application(settings):
    evidence_repository = build_evidence_repository(settings)
    model_gateway = build_model_gateway(settings)
    execution_environment = build_execution_environment(settings)
    change_execution_service = ChangeExecutionService(
        model_gateway=model_gateway,
        execution_environment=execution_environment,
    )
    release_gate_service = ReleaseGateService(
        evidence_planner=build_evidence_planner(settings),
        evidence_collectors=build_evidence_collectors(settings),
        policy_engine=build_policy_engine(settings),
        evidence_repository=evidence_repository,
    )
    return Application(
        change_execution_service=change_execution_service,
        release_gate_service=release_gate_service,
    )
```

This is illustrative.
Use the actual B6 composition implementation in the repository.
---
# 79. Local Mode
The repository should support a deterministic local mode wherever practical.
Local mode is valuable because it allows developers and scientists to understand the system without requiring:

```text
Azure subscription
Jira
production repository
enterprise identity
LLM calls
```

A local deterministic X1 fixture should exercise the architecture end to end.
---
# 80. Local End-to-End Path
A deterministic local fixture should demonstrate:

```text
TaskRequest
    |
    v
Capability resolution
    |
    v
ChangeExecutionService
    |
    v
CandidateArtifact
    |
    v
ReleaseGateService
    |
    v
EvidenceBundle
    |
    v
GateDecision
```

The fixture should preserve:

```text
candidate identity
correlation ID
evidence lineage
gate policy identity
resource usage
```

without requiring external infrastructure.
---
# 81. Testing Strategy
The repository should contain multiple testing layers.

```text
LEVEL 1
Unit tests
LEVEL 2
Contract/schema tests
LEVEL 3
Component integration tests
LEVEL 4
Architecture-boundary tests
LEVEL 5
Local deterministic E2E tests
LEVEL 6
Azure integration tests
LEVEL 7
AI-backed evaluation campaigns
```

These serve different purposes.
Do not treat a large evaluation campaign as a unit test.
---
# 82. Ordinary CI
Ordinary pull-request CI should emphasize fast deterministic checks such as:

```text
syntax
unit tests
contract tests
serialization
hashing
gate-policy semantics
statistics
architecture boundaries
local deterministic E2E fixture
```

AI-backed campaigns may be too expensive and nondeterministic for every commit.
---
# 83. Qualification Campaigns
Large AI-backed campaigns are better suited to:

```text
material capability changes
model changes
prompt changes
gate-policy changes
planner changes
diversity-mapper changes
scheduled regression qualification
explicit release qualification
```

Campaign execution should always identify the exact capability version being evaluated.
---
# 84. Architecture Review
B7 introduced a deterministic repository-level architecture review.
Run:

```text
python tools/run_b7_review.py
```

The review should detect configured violations such as:

```text
Azure imports in core domain modules
hidden-oracle imports in online packages
duplicate canonical contracts
forbidden dependency direction
other repository architecture violations
```

A passing B7 static review does not mean the AI capability is qualified.
It means configured static architecture invariants were not violated.
---
# 85. Recommended Deterministic Test Sequence
A typical local verification sequence is:

```text
python tools/run_b7_review.py
```

then:

```text
pytest tests/architecture -q
```

then:

```text
pytest tests/configuration -q
```

then:

```text
pytest tests/bootstrap -q
```

then:

```text
pytest -m "not azure and not evaluation"
```

Then run the deterministic X1 end-to-end fixture.
The exact commands should be adjusted if the final repository test paths differ.
---
# 86. Gate Semantics Tests
The gate should have deterministic tests for cases such as:

```text
compilation failure
    -> FAIL
mandatory regression failure
    -> FAIL
all mandatory evidence satisfied
    -> PASS
required evidence unavailable
    -> HUMAN_REVIEW_REQUIRED
conflicting evidence without dominant failure
    -> HUMAN_REVIEW_REQUIRED
insufficient evidence diversity
    -> HUMAN_REVIEW_REQUIRED
```

These tests should not require an LLM.
They test policy semantics.
---
# 87. Gate Metamorphic Tests
Useful gate invariants include:

```text
Adding irrelevant positive evidence cannot override a veto.
Removing mandatory evidence cannot convert REVIEW to PASS.
Changing candidate identity invalidates reuse of a prior decision.
Changing gate-policy identity requires a new gate evaluation.
Reordering evidence does not alter deterministic policy outcome.
Duplicate evidence does not increase confidence simply because it is duplicated.
```

These are powerful tests because they verify system behavior rather than isolated examples.
---
# 88. Negative Candidates
The evaluation suite should deliberately include bad candidates.
Examples:

```text
syntax-breaking patch
mandatory regression
unauthorized-file modification
incomplete implementation
semantic reversal
test deletion
assertion weakening
configuration that disables validation
```

A gate evaluated only on correct candidates cannot establish false-release behavior.
---
# 89. Test Tampering
Candidates may attempt or accidentally make changes that weaken validation.
Examples:

```text
delete failing test
skip test
change expected assertion
disable static check
modify CI configuration
exclude failing path
```

Where outside authorized task scope, these should become explicit deterministic policy evidence.
---
# 90. Scope Enforcement
Task specifications should define authorized scope where feasible.
Examples:

```text
allowed paths
prohibited paths
permitted dependency changes
maximum files changed
maximum patch size
required validation commands
```

These constraints should be inspectable.
Do not rely exclusively on prompt instructions such as:

```text
"Please do not modify these files."
```

---
# 91. Benchmark Campaign Manifest
Every campaign should preserve an immutable manifest containing at least:

```text
campaign ID
benchmark version
capability identity
software commit
execution image digest
model configuration
gate-policy identity
planner version
diversity-mapper version
campaign configuration
case IDs
timestamps
```

This answers:
> What exactly did we qualify?
---
# 92. Campaign Report
A qualification report should separate:

```text
execution summary
capability performance
gate performance
false releases
false rejections
review / abstention
uncertainty
resource usage
benchmark-quality issues
infrastructure failures
slice analysis
limitations
```

Avoid reporting only one overall score.
---
# 93. False-Release Investigation
Every false release should answer:

```text
What task was requested?
What candidate was generated?
What evidence was collected?
Why did the gate pass?
What did the oracle detect?
Which evidence family was absent or misleading?
Did the planner fail?
Did the diversity mapper fail?
Did the policy fail?
Was the benchmark itself valid?
```

This analysis is more valuable than merely recording another failure count.
---
# 94. Component Evals
Individual components should also be evaluated.
For example:

```text
ChangeExecutionService evals
ReleaseGateService evals
EvidencePlanner evals
EvidenceDiversityMapper evals
mutation-strategy evals
```

Component evaluations help diagnose failure.
They do not replace end-to-end system evaluation.
---
# 95. Release-Gate Evaluation
The release gate can be evaluated independently using:

```text
known-good candidates
known-bad candidates
ambiguous candidates
insufficient-evidence candidates
test-tampering candidates
mutation-surviving candidates
```

This isolates gate discrimination from code-generation capability.
---
# 96. Change-Execution Evaluation
`ChangeExecutionService` can separately be measured on benchmark tasks using hidden oracle assessment of its generated candidates.
This distinguishes:

```text
generation failure
```

from:

```text
gate failure
```

The final system evaluation still needs both components together.
---
# 97. Evidence-Diversity Evaluation
The Evidence Diversity Mapper should itself be evaluated.
Useful experiments include:

```text
gate without mapper
versus
gate with mapper
```

Measure whether the mapper changes:

```text
false-release rate
mutation survival
behavioral coverage
review rate
token usage
wall time
```

Do not assume the mapper helps simply because its conceptual rationale is attractive.
---
# 98. Statistical Planning
Before running a qualification campaign, define:

```text
primary metric
critical failure event
desired uncertainty
benchmark population
sample-size rationale
repeated-run policy
invalid-case handling
stopping rule
```

Avoid running an experiment first and selecting favorable metrics afterward.
---
# 99. Primary and Secondary Metrics
Metrics should be classified.
For example:

```text
PRIMARY ASSURANCE METRICS
false-release behavior
conditional release precision
automation coverage
SECONDARY DIAGNOSTIC METRICS
task success
mutation score
review rate
token usage
latency
```

The actual hierarchy should be decided before qualification.
---
# 100. Security Boundary
This repository is not a complete enterprise security architecture.
Production deployment would require separate work covering:

```text
threat modeling
networking
IAM
secrets
dependency governance
software supply chain
container security
audit requirements
data classification
incident response
rollback
production support
```

The POC should make these integrations possible without claiming they have already been completed.
---
# 101. Sensitive Data
The POC should avoid production customer data.
Benchmark repositories should use:

```text
synthetic data
sanitized data
enterprise-approved non-sensitive fixtures
```

Source code itself may still be sensitive.
LLM prompts, logs, evidence, and telemetry must therefore be treated according to applicable enterprise data-classification requirements.
---
# 102. Network Isolation
Deterministic execution environments should preferably restrict network access unless the task explicitly requires it.
External network dependencies introduce:

```text
nondeterminism
security risk
data leakage
test instability
reproducibility problems
```

Any required network access should be explicit in task policy.
---
# 103. Secrets
Generated code and test environments should not receive broad production secrets.
Prefer:

```text
synthetic credentials
test credentials
managed identity
least privilege
```

Release gating should not require unrestricted production credentials to establish candidate quality.
---
# 104. NOT-IMPLEMENTED.md
`NOT-IMPLEMENTED.md` is a first-class engineering artifact.
It documents functionality that is intentionally absent from the POC.
Each entry should explain:

```text
identifier
missing capability
why it is not implemented
expected production implementation
interface involved
example implementation approach
security/enterprise considerations
what happens if the missing capability is invoked
```

Production-shaped functionality should not silently pretend to work.
---
# 105. Explicit NotImplementedError
Where a production adapter is intentionally unavailable, prefer:

```python
raise NotImplementedError(
    "NI-XX: This production adapter requires an enterprise-approved "
    "implementation. See NOT-IMPLEMENTED.md."
)
```

over:

```python
return True
```

or:

```python
pass
```

A visible failure is safer than a fake success.
---
# 106. DESIGN-RATIONALE.md
`DESIGN-RATIONALE.md` preserves the reasoning behind important architectural choices.
Examples include:

```text
why generation and gating are separate
why human review remains outside the gate
why the final policy should be deterministic
why evidence diversity does not imply independence
why benchmark truth is hidden
why synthetic benchmarks require validation
why test count is not sample size
why token usage and deterministic compute are separate
why pipeline evaluation wraps the online pipeline
why business KPIs remain downstream
```

Future engineers should understand not only what the architecture is, but why it exists.
---
# 107. Code Commentary Standard
The codebase is intentionally intended to remain understandable to junior engineers and data scientists.
Comments should explain:

```text
WHY
```

rather than merely repeat:

```text
WHAT
```

For example, avoid:

```python
# Increment counter.
counter += 1
```

Prefer:

```python
# Count intentional capability trials rather than infrastructure retries.
# Otherwise message redelivery could artificially increase the apparent
# evaluation sample size.
trial_count += 1
```

---
# 108. Type Safety
Assurance-critical boundaries should prefer:

```text
typed dataclasses
enums
Protocols
ABCs
typed result objects
```

over unrestricted:

```python
dict[str, Any]
```

Provider-specific raw metadata may remain flexible where appropriate.
Critical semantics should not exist only inside untyped dictionaries.
---
# 109. Explicit States
Important finite states should be enums.
Examples include:

```text
GateOutcome
EvidenceStatus
CampaignCaseStatus
DecisionClassification
RuntimeMode
```

This prevents semantic drift such as:

```text
human_review
review
needs_human
manual
```

all accidentally representing the same concept.
---
# 110. Exception Taxonomy
The repository should distinguish meaningful failure categories.
Examples include:

```text
ConfigurationError
InfrastructureUnavailableError
ContractValidationError
CandidateGenerationError
CandidateValidationError
EvidencePlanningError
EvidenceCollectionError
ExecutionEnvironmentError
GatePolicyError
OracleError
BenchmarkValidationError
CampaignExecutionError
```

Exceptions should retain useful cause and correlation information.
---
# 111. Hashing
Structured artifacts should be canonically serialized before hashing.
Avoid:

```python
hash(str(object))
```

Prefer stable serialization such as:

```text
sorted keys
stable separators
UTF-8
explicit schema
```

followed by:

```text
SHA-256
```

Hashes establish content identity.
They do not establish correctness or trustworthiness.
---
# 112. Schema Evolution
Persisted contracts should eventually include:

```text
schema_version
```

Changing a Python dataclass does not automatically make historical persisted artifacts compatible.
The POC may use a simple migration strategy.
It should not silently assume schema compatibility.
---
# 113. Audit Events
A common audit envelope can provide end-to-end traceability.
Conceptually:

```python
@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    event_type: str
    correlation_id: str
    task_id: str | None
    run_id: str | None
    candidate_id: str | None
    component: str
    component_version: str
    occurred_at_utc: str
    payload_sha256: str
```

Component-specific payloads may remain separate.
---
# 114. Logs Are Not Automatically Evidence
Logs serve:

```text
diagnosis
operations
observability
```

Evidence serves:

```text
gate reasoning
evaluation
auditability
```

A log entry may support evidence.
The release gate should not depend on scraping arbitrary log text as its primary assurance contract.
---
# 115. Time
Persisted timestamps should use UTC.
Where duration matters, use monotonic clocks internally where practical.
These answer different questions:

```text
UTC timestamp
    -> when did this occur?
monotonic duration
    -> how long did this operation take?
```

---
# 116. Concurrency
Two engineering tasks may target the same repository revision concurrently.
For example:

```text
Task A starts from revision R
Task B starts from revision R
Task A merges
Task B is now based on stale assumptions
```

A production system will eventually require:

```text
branch isolation
stale-base detection
optimistic concurrency
merge/rebase policy
```

Serial execution is acceptable for a bounded POC if explicitly documented.
---
# 117. Caching
Caching may reduce:

```text
token consumption
compilation
static analysis
repeated execution
```

but cache keys must include all behaviorally relevant identity.
Unsafe:

```text
task_type = X1
```

Safer:

```text
candidate hash
+
generator version
+
execution environment
+
policy-relevant configuration
```

Evidence must not be reused merely because two tasks appear similar.
---
# 118. Reproducibility
For deterministic components, exact replay should generally be expected.
For hosted LLM behavior, exact replay may not be guaranteed.
Therefore distinguish:

```text
reproducible provenance
```

from:

```text
identical model output
```

The first should be a platform requirement.
The second may depend on provider capabilities.
---
# 119. Material Changes
A future governance policy may classify capability changes.
For example:

```text
NON-BEHAVIORAL
documentation
telemetry destination
logging
POTENTIALLY BEHAVIORAL
dependency update
execution image change
BEHAVIORAL
model change
prompt change
skill change
gate-policy change
planner change
diversity-mapper change
```

The required level of requalification can depend on change class.
---
# 120. Qualification Evidence and Deployment
A production deployment should eventually be traceable to qualification evidence.
Conceptually:

```text
Deployment
    |
    +-- capability_identity
    +-- software_commit
    +-- image_digest
    +-- qualification_campaign_id
```

This creates the link:

```text
what was evaluated
```

to:

```text
what was deployed
```

---
# 121. Minimum Credible POC
The minimum credible demonstration is:

```text
TaskRequest
    |
    v
CapabilityRegistry
    |
    v
X1 specification
    |
    v
ChangeExecutionService
    |
    v
CandidateArtifact
    |
    v
ReleaseGateService
    |
    v
GateDecision
```

plus offline:

```text
Validated Benchmark
    |
    v
same online pipeline
    |
    v
Candidate + GateDecision
    |
    v
Hidden Oracle
    |
    v
Campaign Metrics
```

The goal is not to demonstrate autonomous software engineering generally.
The goal is to demonstrate a bounded task capability rigorously.
---
# 122. Minimum Evidence Demonstration
The POC should demonstrate the ability to represent heterogeneous evidence such as:

```text
existing regression tests
generated behavioral tests
static/compiler evidence
mutation evidence
scope/policy evidence
```

The final X1 gate policy should be empirically calibrated.
The architecture should not assume that exactly these evidence families are universally sufficient.
---
# 123. Minimum Campaign Characteristics
A useful POC campaign should contain:

```text
correctable tasks
difficult tasks
expected PASS cases
expected FAIL cases
expected REVIEW cases
repeated model runs
benchmark-validation records
resource accounting
negative candidates
```

No universal benchmark sample size is specified here.
Sample size should be determined by the uncertainty required for the intended decision.
---
# 124. Interpreting Strong Results
If the POC performs well, the correct conclusion is not:

```text
L1 developers can be replaced.
```

A stronger and more defensible conclusion is:
> Capability X1, under capability configuration C, achieved measured performance P on validated benchmark B under gate policy G with measured uncertainty U and resource usage R.
Then:

```text
X2
```

can be evaluated separately.
---
# 125. Interpreting Weak Results
If the POC performs poorly, do not automatically add more agents.
Investigate whether the limiting factor is:

```text
task ambiguity
context
generation
test synthesis
evidence diversity
mutation strategy
gate policy
benchmark quality
model capability
infrastructure
```

The appropriate response may be:

```text
narrow X1
increase review
automate only part of X1
change evidence strategy
improve benchmark
change model
stop automation for that task
```

The evaluation system should support all of these conclusions.
---
# 126. Known Fundamental Uncertainties
Several important questions remain empirical.
We do not yet know:
1. how well the selected X1 task can actually be automated;
2. how frequently correlated LLM blind spots survive release gating;
3. how much the Evidence Diversity Mapper reduces those failures;
4. which evidence families provide the greatest incremental assurance;
5. how predictive mutation analysis is for real X1 defects;
6. what automation coverage can be achieved at acceptable false-release risk;
7. how large the benchmark must be;
8. how representative synthetic benchmark tasks will be;
9. how much release gating will cost in LLM tokens;
10. how much deterministic compute the gate will require;
11. how frequently the gate will abstain;
12. whether alternate-model evidence materially improves assurance;
13. how stable capability performance will remain across model changes.
These are experimental questions.
Architecture alone cannot answer them.
---
# 127. Important Research Limitation
Software-engineering agent benchmarks themselves can contain defects.
Possible issues include:

```text
broken tasks
ambiguous requirements
incomplete tests
overly restrictive tests
contamination
incorrect reference behavior
unrepresentative task distributions
```

Therefore:

```text
hidden oracle
```

must not be interpreted as:

```text
infallible oracle
```

Benchmark validation is part of the assurance system.
---
# 128. Engineering Philosophy
This repository follows several principles.
## Principle 1
Prefer explicit contracts over implicit conventions.
## Principle 2
Prefer deterministic evidence where deterministic evidence is available.
## Principle 3
Use AI where it adds capability, not merely because AI is available.
## Principle 4
Do not let the code-generation model be its own unquestioned judge.
## Principle 5
Treat evidence diversity as useful but not equivalent to independence.
## Principle 6
Separate candidate release decisions from capability qualification.
## Principle 7
Evaluate the same pipeline that will actually operate.
## Principle 8
Keep hidden ground truth outside the online trust boundary.
## Principle 9
Measure uncertainty rather than hide small samples behind percentages.
## Principle 10
Measure tokens and deterministic compute separately.
## Principle 11
Fail explicitly when production functionality is not implemented.
## Principle 12
Keep architecture understandable to junior engineers and scientists.
## Principle 13
Allow experimental evidence to narrow or reject the automation hypothesis.
---
# 129. Assurance Chain
The complete assurance argument is:

```text
We know what task was requested.
        |
        v
We know which exact capability attempted it.
        |
        v
We know which exact candidate was produced.
        |
        v
We know which evidence was gathered.
        |
        v
We know how the gate policy interpreted that evidence.
        |
        v
We know whether the gate passed, failed, or abstained.
        |
        v
Offline, we compare those decisions against independently hidden,
validated benchmark truth.
        |
        v
We measure false releases, false rejections, automation coverage,
success, uncertainty, and resource consumption.
        |
        v
We bind those measurements to the exact capability version that
produced them.
```

This is the central assurance story of the POC.
---
# 130. Development Workflow
A developer making a change should generally:

```text
1. Understand the relevant canonical contracts.
2. Review DESIGN-RATIONALE.md for the affected boundary.
3. Review NOT-IMPLEMENTED.md for intentionally missing functionality.
4. Make the smallest coherent change.
5. Preserve type annotations and explanatory comments.
6. Add or update deterministic unit tests.
7. Add contract tests where a shared interface changes.
8. Run architecture checks.
9. Run deterministic local E2E tests.
10. Determine whether the change alters capability identity.
11. If behaviorally material, determine whether requalification is required.
```

---
# 131. Adding a New Task Type
A future task type such as `X2` should not be implemented by scattering:

```python
if task_type == "X2":
```

throughout the codebase.
Prefer a versioned capability package containing:

```text
task specification
skill
gate policy
evaluation specification
required adapters
benchmark definition
```

The common platform should execute the capability through shared contracts.
---
# 132. Adding a New Evidence Collector
A new evidence collector should:

```text
implement the canonical evidence-collector interface;
declare the evidence family it produces;
record provenance;
bind evidence to exact candidate identity;
return typed evidence;
report resource usage;
fail explicitly;
avoid making the final gate decision.
```

The collector should then be registered through composition/configuration rather than hard-coded into unrelated services.
---
# 133. Adding a New Model
A new model provider or deployment should be implemented behind the canonical model gateway.
The adapter should normalize:

```text
request
response
model identity
token accounting
structured output
provider errors
latency
```

Changing the model used by a qualified capability should generally be treated as behaviorally material.
---
# 134. Adding a New Azure Adapter
A new Azure adapter should:

```text
implement an existing application port;
remain outside core domain modules;
use managed identity where practical;
translate provider-specific errors into canonical exceptions;
preserve correlation IDs;
record operational telemetry;
avoid leaking Azure SDK types into shared contracts.
```

Contract tests should be reusable across local and Azure implementations.
---
# 135. Running an Evaluation Campaign
A qualification campaign should conceptually follow:

```text
1. Select frozen benchmark version.
2. Select frozen capability identity.
3. Validate campaign configuration.
4. Create CampaignManifest.
5. Execute benchmark cases.
6. Preserve intentional repeated runs.
7. Invoke the same online capability.
8. Evaluate exact candidates using hidden oracle.
9. Classify gate/oracle outcomes.
10. Separate infrastructure failures.
11. Compute primary metrics.
12. Compute uncertainty.
13. Compute resource usage.
14. Produce slice analysis.
15. Record benchmark-quality issues.
16. Produce limitations.
17. Preserve immutable campaign result.
```

---
# 136. Reading Campaign Results
Do not ask only:

```text
What was the success rate?
```

Ask:

```text
How often was the generated candidate correct?
How often did the gate automatically release?
How often did the gate release an incorrect candidate?
How often did the gate unnecessarily reject a correct candidate?
How often did the gate abstain?
What is the uncertainty around these estimates?
Which task strata failed?
What evidence was missing in false releases?
How many benchmark cases were invalid?
How many runs failed because of infrastructure?
What did the campaign cost?
How much of that cost came from generation versus gating?
```

These questions provide a more complete view of readiness.
---
# 137. Production Readiness
A successful POC does not by itself establish production readiness.
Production readiness additionally requires evidence concerning:

```text
enterprise Azure implementation
security
IAM
networking
resilience
data governance
software supply chain
operational support
monitoring
deployment controls
incident response
rollback
qualification thresholds
business ownership
risk acceptance
```

Those activities should be performed through the appropriate enterprise processes.
---
# 138. Ready for Qualification
The repository is conceptually ready for qualification when:

```text
[ ] canonical contracts are reconciled
[ ] NOT-IMPLEMENTED register matches source reality
[ ] design rationale matches implementation
[ ] deterministic X1 path works
[ ] offline evaluation invokes the same online pipeline
[ ] configuration/composition boundaries are enforced
[ ] architecture review passes
[ ] candidate identity is preserved end-to-end
[ ] capability identity is preserved end-to-end
[ ] evidence lineage is preserved
[ ] hidden oracle is isolated
[ ] gate semantics are deterministically tested
[ ] benchmark validation is explicit
[ ] statistical units are defined
[ ] resource accounting functions
[ ] retries cannot inflate sample size
[ ] campaign limitations are documented
```

This means:

```text
READY FOR QUALIFICATION
```

not:

```text
READY FOR PRODUCTION
```

---
# 139. Documentation Map
The principal documentation artifacts are:

```text
README.md
```

Purpose:

```text
Master explanation of the repository and how to use it.
```

---

```text
DESIGN-RATIONALE.md
```

Purpose:

```text
Why important architectural and evaluation decisions were made.
```

---

```text
NOT-IMPLEMENTED.md
```

Purpose:

```text
Explicit register of intentionally absent production functionality,
why it is absent, and how it should eventually be implemented.
```

These files should remain consistent with the source code.
---
# 140. Glossary
## Candidate
The exact proposed code change produced for a task.
## CandidateArtifact
Canonical representation of that candidate and its provenance.
## Capability
A versioned automation configuration for a bounded task type.
## CapabilityIdentity
Identity binding behaviorally relevant configuration.
## Task Type
A bounded class of engineering work such as `X1`.
## ChangeExecutionService
Application service responsible for producing a candidate.
## ReleaseGateService
Application service responsible for deciding whether sufficient evidence exists to automatically release a candidate.
## Evidence
Information relevant to candidate assurance.
## EvidenceArtifact
Typed, attributable representation of evidence.
## EvidencePlanner
Component deciding what evidence should be collected.
## EvidenceDiversityMapper
Component coordinating evidence heterogeneity and attempting to reduce correlated blind spots.
## Evidence Family
A category of evidence with a meaningfully different origin or assurance mechanism.
## EvidenceBundle
The exact set of evidence used for a gate evaluation.
## GatePolicy
Explicit rules converting evidence into a gate outcome.
## GateDecision
Immutable decision for an exact candidate under an exact policy and evidence set.
## PASS
The automated gate found sufficient evidence to permit automated progression.
## FAIL
The gate found dominant evidence that the candidate should not proceed.
## HUMAN_REVIEW_REQUIRED
The automated assurance process could not justify automatic release but did not necessarily establish that the candidate is technically incorrect.
## Mutation Testing
Technique that introduces controlled defects to determine whether tests detect them.
## BenchmarkFactory
Component/process used to construct evaluation benchmark cases.
## BenchmarkValidation
Evidence that a benchmark case is suitable for qualification use.
## Hidden Oracle
Offline component with privileged access to hidden benchmark truth.
## OracleAssessment
Assessment of whether the exact candidate satisfies the benchmark task.
## EvaluationCampaignRunner
Component executing a capability across benchmark cases and aggregating results.
## False Release
A candidate that receives `PASS` from the gate but is determined incorrect by the hidden oracle.
## False Rejection
A correct candidate that is rejected by the gate.
## Abstention
Decision not to automate because available assurance is insufficient.
## Automated Release Rate
Fraction of applicable tasks that receive automated release authorization.
## Conditional Release Precision
Fraction of automatically released candidates that are actually correct.
## Capability Success Rate
Fraction of benchmark tasks for which the capability produces a correct candidate.
## Qualification
Evidence-based decision about whether a versioned task capability is ready for an intended use.
## Operational Metric
Metric describing behavior of the running platform.
## Process Outcome
Measure of the downstream operational process affected by the software.
## Business KPI
Business-level outcome that may be influenced by the process.
## Idempotency
Property ensuring duplicate delivery does not cause unintended duplicate business operations.
## Correlation ID
Identifier linking artifacts and events from one logical execution.
## Provenance
Information describing how an artifact or evidence item was created.
## Lineage
Relationship between derived evidence and its parent evidence.
## Composition Root
Central location where concrete implementations are assembled into the application.
## Port
Application-facing interface defining a required capability.
## Adapter
Concrete implementation connecting a port to infrastructure or an external service.
## Deterministic
Expected to produce the same result from the same controlled inputs and environment.
## Nondeterministic
May produce different results even when apparent inputs are equivalent.
## X1
The initial bounded engineering task capability selected for the POC.
---
# 141. Final Perspective
The central engineering challenge in this project is not merely generating code with AI.
Modern models can already generate substantial amounts of code.
The more difficult problem is establishing when an AI-generated change deserves automated trust.
This repository therefore treats:

```text
generation
```

and:

```text
assurance
```

as separate engineering problems.
It then treats:

```text
candidate assurance
```

and:

```text
capability qualification
```

as separate evaluation problems.
Finally, it distinguishes:

```text
technical capability
```

from:

```text
operational performance
```

and:

```text
business value
```

so that evidence is not stretched beyond what it actually demonstrates.
The desired outcome of the POC is therefore not a demonstration that AI can produce a convincing patch.
The desired outcome is an experimentally defensible answer to the following question:
> For a precisely defined engineering task capability X1, under a precisely identified configuration, can an AI-led change-execution system combined with an independently designed evidence-based release gate achieve sufficient correctness, automation coverage, uncertainty, and resource efficiency to justify controlled production use?
If the evidence supports that proposition, X1 can move toward qualification.
If the evidence does not support it, the system should reveal why.
That ability to produce a credible negative result is as important as its ability to produce a positive one.
---
# 142. Final Repository Principle
The repository should remain organized around the following invariant:

```text
SPECIFY THE TASK
        |
        v
GENERATE THE CHANGE
        |
        v
IDENTIFY THE EXACT CANDIDATE
        |
        v
COLLECT DIVERSE EVIDENCE
        |
        v
APPLY EXPLICIT RELEASE POLICY
        |
        v
PASS / FAIL / REVIEW
        |
        v
EVALUATE THE SAME PIPELINE OFFLINE
        |
        v
COMPARE AGAINST VALIDATED HIDDEN TRUTH
        |
        v
MEASURE QUALITY + UNCERTAINTY + RESOURCES
        |
        v
QUALIFY ONLY WHAT THE EVIDENCE SUPPORTS
```

That is the governing architecture of the L1 Engineering Automation POC.
---
# 143. Status
With B1 through B8 complete, the design/documentation sequence is complete.
The next phase should emphasize:

```text
repository assembly
contract reconciliation
deterministic testing
X1 implementation
benchmark construction
Azure integration
experimental campaigns
measurement
qualification
```

rather than introducing additional major architectural abstractions before empirical evidence demonstrates that they are necessary.
---
END OF README.md