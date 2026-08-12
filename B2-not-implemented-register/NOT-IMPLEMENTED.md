# NOT-IMPLEMENTED.md

## B2 — Explicitly Unimplemented, Partially Implemented, and Enterprise-Dependent Capabilities

**Document status:** POC implementation register
**Audience:** Platform engineers, AI engineers, evaluation scientists, data scientists, reviewers, security engineers, and future maintainers
**Primary purpose:** Ensure that functionality which is not yet responsibly implementable is represented explicitly rather than hidden behind placeholders, fake success paths, or ambiguous TODO comments.

---

# 1. Purpose

This document records capabilities that are deliberately not fully implemented in the current L1 Engineering Automation POC.

The repository is intended to demonstrate and evaluate a bounded engineering-automation architecture consisting principally of:

```text
ChangeExecutionService

ReleaseGateService

EvaluationCampaignRunner
```

supported by:

```text
canonical contracts

task specifications

skills

evidence planning

Evidence Diversity Mapper

deterministic execution

mutation analysis

evidence persistence

orchestration

workflow integration

operational measurement

business/process measurement

resource accounting

Azure infrastructure adapters
```

Some of these capabilities can be implemented completely using provider-neutral software.

Others require enterprise-specific information that should not be invented.

Examples include:

```text
Azure subscription/resource IDs

managed identities

RBAC assignments

private-network architecture

approved model deployments

Azure DevOps/Jira credentials

evidence-retention policy

business KPI data sources

Finance-approved economic assumptions

production false-release tolerance
```

Where such information is unavailable, the repository should fail explicitly rather than manufacture plausible-looking production behavior.

---

# 2. Governing Principle

The governing rule for this document is:

> **UNKNOWN PRODUCTION DEPENDENCY != SAFE DEFAULT**

A missing implementation should never silently become:

```python
return True
```

or:

```python
return GateOutcome.PASS
```

or:

```python
return []
```

when the empty collection could be interpreted as "no problems found."

Likewise, avoid:

```python
try:
    ...
except Exception:
    pass
```

in assurance-critical paths.

If functionality is genuinely unavailable, prefer an explicit typed failure or:

```python
raise NotImplementedError(
    "NI-XX: explanation of the missing production capability. "
    "See NOT-IMPLEMENTED.md."
)
```

The specific exception type can later become more specialized.

The important principle is that unimplemented behavior must remain visible.

---

# 3. Relationship to the Rest of the Repository

The B-series artifacts have distinct purposes.

```text
B1
Canonical shared contracts

B2
This document:
explicit implementation gaps and how they should eventually be filled

B3
Design rationale:
why the architecture has the shape it does

B4
Composition root and deterministic X1 end-to-end software path

B5
Hidden-oracle evaluation campaign

B6
Production configuration and repository reconciliation

B7
Cross-component consistency and assurance review

B8
Master README
```

This document should be updated whenever one of the listed capabilities changes from:

```text
OPEN
```

to:

```text
PARTIALLY IMPLEMENTED
```

or:

```text
IMPLEMENTED
```

---

# 4. Status Definitions

Every NI item should use one of the following statuses.

## OPEN

The required capability is absent.

The repository may contain:

```text
interface

contract

documentation

example implementation
```

but no functioning implementation of the capability itself.

---

## PARTIALLY IMPLEMENTED

Some provider-neutral or local functionality exists, but one or more production-relevant pieces remain absent.

Example:

```text
ExecutionEnvironmentPort exists.

Local deterministic runner exists.

Azure Container Apps runner is absent.
```

---

## IMPLEMENTED

The required implementation exists and has appropriate tests.

An NI entry marked IMPLEMENTED should normally be removed from this document after its historical value is captured elsewhere, such as an ADR or changelog.

---

## DEFERRED

The capability is deliberately outside the current POC rather than merely unfinished.

Example:

```text
automatic feedback from production incidents into prompt/gate modification
```

Deferred functionality should not accidentally become a hidden requirement for the current POC.

---

# 5. Machine-Readable Convention

Every important production-facing `NotImplementedError` should include its NI identifier.

Example:

```python
raise NotImplementedError(
    "NI-07: Azure hidden-oracle execution requires an "
    "enterprise-approved isolated execution environment. "
    "See NOT-IMPLEMENTED.md."
)
```

This allows a future repository check to verify:

```text
documented NI item
        <->
actual unimplemented code site
```

A repository-wide search for:

```text
NotImplementedError
TODO
FIXME
pass
placeholder
mock
fake
temporary
```

should be part of B7 consistency review.

---

# 6. Summary Register

| ID | Capability | Status | Primary Component |
|---|---|---|---|
| NI-01 | Production Azure model client and model identity | PARTIALLY IMPLEMENTED | Components 2/3 |
| NI-02 | Production Azure isolated change-execution runner | PARTIALLY IMPLEMENTED | Component 10 |
| NI-03 | Production Azure isolated release-gate runner | PARTIALLY IMPLEMENTED | Components 3/10 |
| NI-04 | Azure evidence repository and enterprise retention | PARTIALLY IMPLEMENTED | Component 4 |
| NI-05 | Production workflow/Jira/Azure DevOps integration | PARTIALLY IMPLEMENTED | Component 12 |
| NI-06 | Durable orchestration/idempotency persistence | PARTIALLY IMPLEMENTED | Components 9/12 |
| NI-07 | Production Azure hidden-oracle executor | PARTIALLY IMPLEMENTED | Component 5 |
| NI-08 | Validated production-quality X1 benchmark corpus | OPEN | Component 5 |
| NI-09 | Production gate-policy calibration and thresholds | OPEN | Component 3 |
| NI-10 | Evidence Diversity Mapper empirical calibration | PARTIALLY IMPLEMENTED | Component 3 |
| NI-11 | Production mutation strategy and equivalent-mutant handling | PARTIALLY IMPLEMENTED | Component 3 |
| NI-12 | Hierarchical/statistically advanced campaign inference | DEFERRED | Component 5 |
| NI-13 | Production token, compute, and cost attribution | PARTIALLY IMPLEMENTED | Components 5/8 |
| NI-14 | Operational telemetry integration for released code | PARTIALLY IMPLEMENTED | Component 6 |
| NI-15 | Process-outcome and business-KPI connectors | DEFERRED | Component 7 |
| NI-16 | Finance-approved economic-value model | DEFERRED | Component 8 |
| NI-17 | Enterprise security/IAM/network hardening | OPEN | Component 10 / infrastructure |
| NI-18 | Artifact signing / attestation / software supply-chain evidence | DEFERRED | Components 3/4/10 |
| NI-19 | Production human-review workflow implementation | PARTIALLY IMPLEMENTED | Component 12 |
| NI-20 | Automatic production deployment and rollback | DEFERRED | External release system |
| NI-21 | Production feedback-learning loop | DEFERRED | Future architecture |
| NI-22 | Real historical L1 task distribution and representativeness study | OPEN | Component 5 |
| NI-23 | Capability qualification governance and approval authority | OPEN | Enterprise governance |
| NI-24 | Long-term schema migration and evidence-retention migration tooling | DEFERRED | Component 4 |
| NI-25 | Production concurrency / stale-base / merge-conflict strategy | PARTIALLY IMPLEMENTED | Components 2/9/12 |

---

# 7. NI-01 — Production Azure Model Client and Model Identity

**Status:** PARTIALLY IMPLEMENTED

## What Exists

The architecture assumes a provider-neutral model interface that can be consumed by:

```text
ChangeExecutionService

EvidencePlanner

test synthesis

semantic review

Evidence Diversity Mapper
```

without those application components importing the Azure model SDK directly.

Canonical request/response contracts should include or support:

```text
model/deployment identity

prompt/template identity

input token count

output token count

latency

structured-output validation

provider error information

correlation/run identity
```

Local deterministic test doubles can be used during unit and software-integration testing.

---

## What Is Missing

The production Azure model adapter cannot be completely specified without enterprise decisions including:

```text
approved Azure model resource

approved deployment

identity strategy

networking requirements

API version

permitted models

rate limits

retry policy

logging/data-retention restrictions
```

The exact model deployed may also affect qualification results.

Therefore the model deployment must eventually become part of capability identity.

---

## Why It Is Not Implemented Here

Hard-coding a guessed endpoint, API key, deployment name, or authentication mechanism would create a production-looking implementation that is not actually deployable or enterprise-approved.

A secret-based sample could also encourage the wrong authentication pattern.

The architecture should prefer managed/keyless identity where the enterprise Azure design supports it.

---

## Production Implementation Shape

Conceptually:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """
    Provider-neutral model request.

    The exact canonical definition should come from B1.
    """

    purpose: str
    prompt: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """
    Provider-neutral model result.

    Resource usage is evidence and should not be discarded.
    """

    text: str
    model_configuration_id: str

    input_tokens: int
    output_tokens: int

    latency_seconds: float


class ModelClientPort(Protocol):
    def complete(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        ...


class AzureOpenAIModelClient:
    """
    Production Azure implementation.

    Authentication/resource construction belongs here, not inside
    ChangeExecutionService or ReleaseGateService.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        credential,
    ) -> None:
        if not endpoint:
            raise ValueError(
                "endpoint must be non-empty."
            )

        if not deployment:
            raise ValueError(
                "deployment must be non-empty."
            )

        self._endpoint = endpoint
        self._deployment = deployment
        self._credential = credential

    def complete(
        self,
        request: ModelRequest,
    ) -> ModelResponse:

        raise NotImplementedError(
            "NI-01: Azure model invocation requires the enterprise-approved "
            "Azure model SDK configuration, authentication mechanism, "
            "deployment identity, retry policy, and telemetry policy. "
            "See NOT-IMPLEMENTED.md."
        )
```

---

## Implementation Notes

A production implementation should preserve:

```text
deployment identity

model/version information where available

API version

request purpose

token consumption

latency

retry count

structured-output parse result

provider failure category
```

Do not interpret provider timeout as:

```text
candidate FAIL
```

Model unavailability is an infrastructure/evidence-collection failure.

---

# 8. NI-02 — Production Azure Isolated Change-Execution Runner

**Status:** PARTIALLY IMPLEMENTED

## What Exists

Component 10 defines the conceptual execution-environment boundary.

Local deterministic execution can be implemented and tested.

The architecture already establishes that generated or modified code should not execute directly inside the long-lived application process.

---

## What Is Missing

The production Azure implementation of the change-execution sandbox remains enterprise-specific.

It requires decisions concerning:

```text
Azure Container Apps Job or alternative execution technology

container image

managed identity

repository access

CPU/memory limits

wall-time limit

network policy

filesystem policy

artifact output location

logging

cancellation

cleanup

container-image approval
```

---

## Why It Is Not Implemented Here

Generated code should be treated as untrusted or semi-trusted.

A generic Python `subprocess.run()` implementation marketed as production isolation would be misleading.

Likewise, code cannot responsibly invent:

```text
which identity may read which repository

which Azure network can be contacted

which storage account is allowed
```

---

## Production Implementation Shape

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    run_id: str
    candidate_id: str
    image_digest: str
    command: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    run_id: str
    candidate_id: str

    exit_code: int

    stdout_artifact_id: str
    stderr_artifact_id: str

    wall_time_seconds: float

    execution_environment_id: str


class ExecutionEnvironmentPort(Protocol):
    def execute(
        self,
        request: ExecutionRequest,
    ) -> ExecutionReceipt:
        ...


class AzureChangeExecutionJobRunner:
    """
    Azure adapter for finite change-execution jobs.

    The production adapter must start a job using an approved image and
    identity and must return an immutable execution receipt.
    """

    def __init__(
        self,
        *,
        subscription_id: str,
        resource_group: str,
        job_name: str,
        credential,
    ) -> None:
        self._subscription_id = subscription_id
        self._resource_group = resource_group
        self._job_name = job_name
        self._credential = credential

    def execute(
        self,
        request: ExecutionRequest,
    ) -> ExecutionReceipt:

        raise NotImplementedError(
            "NI-02: Azure change-execution sandbox requires the "
            "enterprise-approved Container Apps Job/resource configuration, "
            "managed identity, image, networking, repository access, "
            "resource limits, and artifact transport. "
            "See NOT-IMPLEMENTED.md."
        )
```

---

## Example Assumptions for a POC Implementation

Given an approved environment, a first implementation could reasonably assume:

```text
one finite job per candidate-generation attempt

ephemeral workspace

repository checkout at exact baseline revision

no production credentials

limited or disabled outbound network access

candidate exported to immutable artifact storage

explicit timeout

explicit CPU/memory budget
```

These assumptions should be configuration/policy, not hidden constants.

---

# 9. NI-03 — Production Azure Isolated Release-Gate Runner

**Status:** PARTIALLY IMPLEMENTED

## What Exists

The release-gate domain logic can exist independently of Azure.

It can coordinate:

```text
EvidencePlanner

EvidenceDiversityMapper

deterministic test execution

static analysis

mutation

semantic review

GatePolicy
```

Local/test execution adapters can exercise this behavior.

---

## What Is Missing

Production gating requires a separately isolated execution environment with its own identity and permissions.

It should not simply reuse the mutable workspace left behind by change generation.

---

## Why Separate Change and Gate Execution?

The generator may create:

```text
temporary files

generated tests

cached responses

modified environment state

uncommitted artifacts
```

If the gate inherits that environment, independence is weakened.

The intended structure is:

```text
CHANGE JOB
    |
    v
immutable CandidateArtifact
    |
    v
artifact repository
    |
    v
GATE JOB
```

---

## Example Production Adapter

```python
class AzureReleaseGateJobRunner:
    """
    Production release-gate execution adapter.

    This adapter should use an identity distinct from the change-execution
    identity and must not possess access to hidden qualification oracles.
    """

    def execute_gate_job(
        self,
        *,
        candidate_id: str,
        candidate_sha256: str,
        gate_policy_id: str,
    ):
        raise NotImplementedError(
            "NI-03: Azure release-gate execution requires the approved "
            "gate-job image, managed identity, repository/artifact access, "
            "network restrictions, resource limits, and execution receipt "
            "implementation. See NOT-IMPLEMENTED.md."
        )
```

---

## Production Requirement

The release-gate identity should:

```text
CAN READ
candidate artifact
public task specification
approved gate policy
permitted repository context

CAN WRITE
gate evidence
execution receipts
gate decision

CANNOT READ
hidden benchmark oracle
hidden qualification tests
reference solutions
```

---

# 10. NI-04 — Azure Evidence Repository and Enterprise Retention

**Status:** PARTIALLY IMPLEMENTED

## What Exists

The system has a logical evidence-repository responsibility.

Local/in-memory implementations can support:

```text
unit tests

local E2E tests

deterministic campaign tests
```

Evidence artifacts can be content-addressed and candidate-bound.

---

## What Is Missing

A production repository requires enterprise decisions concerning:

```text
Azure storage technology

container/account structure

encryption

managed identity

immutability controls

retention duration

legal/audit requirements

source-code classification

generated-test retention

model prompt/output retention

hidden-oracle separation

data deletion

cross-region replication
```

---

## Why It Is Not Implemented Here

A storage adapter without a retention/access-control design is not equivalent to an enterprise evidence store.

In particular, hidden oracle artifacts may require stronger access restrictions than ordinary release-gate evidence.

---

## Example Interface

```python
from typing import Protocol


class EvidenceRepositoryPort(Protocol):
    def put(
        self,
        *,
        artifact_id: str,
        content: bytes,
        sha256: str,
        media_type: str,
    ) -> None:
        ...

    def get(
        self,
        *,
        artifact_id: str,
    ) -> bytes:
        ...


class AzureBlobEvidenceRepository:
    """
    Production adapter stub.

    An actual implementation must verify content digest before/after storage
    and use enterprise-approved identity and retention controls.
    """

    def put(
        self,
        *,
        artifact_id: str,
        content: bytes,
        sha256: str,
        media_type: str,
    ) -> None:

        raise NotImplementedError(
            "NI-04: Azure evidence persistence requires the approved storage "
            "account/container, RBAC, retention, encryption, immutability, "
            "and data-classification policy. See NOT-IMPLEMENTED.md."
        )
```

---

# 11. NI-05 — Production Workflow / Jira / Azure DevOps Integration

**Status:** PARTIALLY IMPLEMENTED

## What Exists

Component 12 defines the workflow integration boundary.

The online platform should consume a canonical:

```text
TaskRequest
```

rather than a Jira-specific object.

Likewise, `GateDecision` should be translated into workflow status externally.

---

## What Is Missing

A production integration depends on:

```text
selected workflow system

project/repository identifiers

event source

authentication

webhook or queue design

PR conventions

status checks

review semantics

retry rules

rate limits

organizational permissions
```

---

## Example Adapter Shape

```python
class WorkflowTaskAdapter:
    """
    Translate provider-specific work into canonical TaskRequest objects.
    """

    def normalize_event(
        self,
        provider_event,
    ):
        raise NotImplementedError(
            "NI-05: Production workflow normalization requires the selected "
            "Jira/Azure DevOps event schema, repository mapping, credentials, "
            "and task-routing conventions. See NOT-IMPLEMENTED.md."
        )


class WorkflowStatusPublisher:
    """
    Publish candidate-bound automation status to the engineering workflow.
    """

    def publish_gate_decision(
        self,
        decision,
    ) -> None:
        raise NotImplementedError(
            "NI-05: Production workflow status publication requires the "
            "approved Jira/Azure DevOps integration and authorization model. "
            "See NOT-IMPLEMENTED.md."
        )
```

---

## Important Boundary

The workflow adapter must not independently interpret:

```text
mutation score

test pass rate

evidence diversity
```

to decide release.

Those semantics belong to `ReleaseGateService`.

---

# 12. NI-06 — Durable Orchestration and Idempotency Persistence

**Status:** PARTIALLY IMPLEMENTED

## What Exists

Component 9 defines deterministic orchestration.

Local operation can use:

```text
in-memory state

deterministic state transitions

explicit run identities
```

The architecture recognizes that external message delivery may be duplicated.

---

## What Is Missing

Production idempotency requires a persistent atomic claim mechanism.

Examples could include:

```text
database uniqueness constraint

transactional state table

durable workflow engine

atomic conditional write
```

The exact mechanism depends on enterprise infrastructure.

---

## Why This Matters

A duplicate task event must not accidentally create two independent engineering changes.

Conceptually:

```text
external event
     |
     v
stable idempotency key
     |
     v
atomic claim
     |
     +--> already claimed
     |        |
     |        v
     |      reuse/status
     |
     +--> new
              |
              v
        create orchestration run
```

Transport-level duplicate suppression should not be treated as a complete substitute for application-level idempotency.

---

## Example Interface

```python
from typing import Protocol


class IdempotencyStorePort(Protocol):
    def try_claim(
        self,
        *,
        key: str,
        run_id: str,
    ) -> bool:
        """
        Return True only if this caller atomically created the claim.

        Return False if the same logical operation was previously claimed.
        """
        ...


class AzureIdempotencyStore:
    def try_claim(
        self,
        *,
        key: str,
        run_id: str,
    ) -> bool:

        raise NotImplementedError(
            "NI-06: Durable idempotency requires an enterprise-approved "
            "atomic persistence mechanism and retention policy. "
            "See NOT-IMPLEMENTED.md."
        )
```

---

# 13. NI-07 — Production Azure Hidden-Oracle Executor

**Status:** PARTIALLY IMPLEMENTED

## What Exists

Component 5 defines:

```text
HiddenOraclePort

OracleAssessment

candidate binding

campaign comparison logic
```

A deterministic local hidden oracle can evaluate synthetic fixture cases.

The online pipeline is architecturally prevented from requiring hidden truth.

---

## What Is Missing

Production qualification requires a genuinely isolated hidden-oracle execution environment.

That environment should have:

```text
access to exact candidate

access to hidden benchmark artifacts

approved deterministic execution environment

separate identity

separate credentials

separate artifact store or restricted path

execution receipts

timeouts

resource limits
```

The change-generation and release-gate identities must not be able to read its hidden data.

---

## Why It Is Not Implemented Here

This is a security and experiment-validity boundary.

Simply storing:

```text
hidden_tests/
```

in the same mounted repository and instructing the model not to look would not provide adequate isolation.

---

## Production Adapter

```python
class AzureHiddenOracleExecutor:
    """
    Execute hidden qualification tests in an isolated Azure environment.

    The online change/gate services must not possess credentials allowing
    them to access the hidden artifacts used here.
    """

    def assess(
        self,
        *,
        benchmark_case_id: str,
        candidate_id: str,
        candidate_sha256: str,
    ):
        raise NotImplementedError(
            "NI-07: Production Azure hidden-oracle execution requires "
            "enterprise-approved workload identity, isolated hidden-artifact "
            "storage, Container Apps Job or equivalent execution resources, "
            "network controls, and immutable execution receipts. "
            "See NOT-IMPLEMENTED.md."
        )
```

---

## Example POC Implementation Assumptions

Given enterprise-approved Azure resources:

```text
1. Candidate is stored immutably.

2. EvaluationCampaignRunner submits candidate identity to the oracle job.

3. Oracle job receives no candidate-generation credentials.

4. Oracle job mounts/downloads hidden tests using its own identity.

5. Candidate is applied to a fresh benchmark baseline.

6. Hidden tests execute deterministically.

7. Oracle creates candidate-bound OracleAssessment.

8. Evidence is persisted in a hidden or restricted evidence domain.

9. Only the resulting assessment is exposed to the campaign runner.
```

---

# 14. NI-08 — Validated Production-Quality X1 Benchmark Corpus

**Status:** OPEN

## What Exists

The architecture supports:

```text
BenchmarkCase

BenchmarkFactory concept

hidden oracle

benchmark version

campaign runner

synthetic development cases
```

AI can assist in generating benchmark candidates.

---

## What Is Missing

The current repository cannot supply a production-quality X1 benchmark until X1 itself is concretely selected and historical task information becomes available.

A serious benchmark requires cases that represent the actual intended automation population.

---

## Required Benchmark Validation

Each qualification-quality benchmark case should establish:

```text
public task is coherent

baseline reproduces intended problem

task is solvable from public information

reference/known-good implementation satisfies requirements

hidden tests accept known-good implementation

known-bad implementations fail

oracle is not dependent on exact patch text unless required

environment is reproducible

task does not leak the answer

case is not an accidental duplicate

case metadata describes relevant task characteristics
```

---

## Example Validation Function

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BenchmarkValidationResult:
    case_id: str

    baseline_failure_reproduced: bool
    reference_solution_passes: bool
    known_bad_candidate_rejected: bool
    hidden_tests_operational: bool
    public_task_sufficient: bool

    notes: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return all(
            (
                self.baseline_failure_reproduced,
                self.reference_solution_passes,
                self.known_bad_candidate_rejected,
                self.hidden_tests_operational,
                self.public_task_sufficient,
            )
        )
```

This is an example of deterministic validation logic.

The actual benchmark validator should use canonical contracts from the repository.

---

# 15. NI-09 — Production Gate-Policy Calibration and Thresholds

**Status:** OPEN

## What Exists

The architecture supports an explicit deterministic `GatePolicy`.

It can represent:

```text
veto conditions

required evidence

thresholds

review conditions

budget exhaustion

scope violations
```

---

## What Is Missing

There is currently no empirical basis for claiming specific production thresholds such as:

```text
mutation score >= 0.85

at least 50 generated tests

evidence diversity >= 0.80

false release <= 1%

review rate <= 20%
```

Numbers that appear scientific are not necessarily scientifically justified.

---

## Why It Is Not Implemented

Thresholds depend on:

```text
X1 task risk

benchmark results

failure severity

false-release cost

false-rejection cost

human-review capacity

reversibility

downstream controls

gate resource cost
```

These values require POC evidence and enterprise risk decisions.

---

## Correct Interim Behavior

Development policies may contain explicitly labelled experimental thresholds.

Example:

```yaml
policy_version: "development-0.1"

status: "EXPERIMENTAL_NOT_PRODUCTION_CALIBRATED"

required_evidence:
  - repository_regression
  - static_analysis
  - task_specific_behavioral

notes:
  - >
    Thresholds in this policy exist only to exercise the POC.
    They have not been calibrated to a production false-release tolerance.
```

The experimental status should remain visible in evidence.

---

# 16. NI-10 — Evidence Diversity Mapper Empirical Calibration

**Status:** PARTIALLY IMPLEMENTED

## What Exists

The Evidence Diversity Mapper has a clear architectural role:

```text
inspect proposed/current evidence

identify missing evidence categories

identify duplicates or concentration

request targeted evidence expansion
```

It acts as a coordination layer.

---

## What Is Missing

We do not yet know empirically whether the mapper:

```text
reduces false releases

improves hidden-defect detection

improves mutation performance

reduces correlated blind spots

produces enough value to justify token cost
```

Nor do we yet know the best representation of evidence diversity.

---

## Important Limitation

The mapper must not label:

```text
different test
```

as:

```text
independent evidence
```

without justification.

The initial implementation should prefer categorical diversity:

```text
behavioral

boundary

negative

static

structural

mutation

property

security

integration
```

rather than claiming a mathematically calibrated independence score.

---

## Example Interface

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiversityGap:
    category: str
    reason: str
    priority: int


@dataclass(frozen=True, slots=True)
class DiversityAssessment:
    represented_categories: tuple[str, ...]
    gaps: tuple[DiversityGap, ...]
    adequate_for_policy: bool


class EvidenceDiversityMapper:
    def assess(
        self,
        *,
        evidence,
        required_categories: tuple[str, ...],
    ) -> DiversityAssessment:
        """
        Provider-neutral coordination logic can be implemented here.

        A production-calibrated scoring model remains NI-10.
        """

        represented = {
            item.evidence_type
            for item in evidence
        }

        gaps = tuple(
            DiversityGap(
                category=required,
                reason=(
                    "Required evidence category is not represented."
                ),
                priority=1,
            )
            for required in required_categories
            if required not in represented
        )

        return DiversityAssessment(
            represented_categories=tuple(
                sorted(represented)
            ),
            gaps=gaps,
            adequate_for_policy=not gaps,
        )
```

The simple example above is fully implementable but intentionally does not claim semantic independence.

---

# 17. NI-11 — Production Mutation Strategy and Equivalent-Mutant Handling

**Status:** PARTIALLY IMPLEMENTED

## What Exists

Mutation testing is part of the intended release-gate evidence portfolio.

The system can represent:

```text
mutants generated

mutants executed

mutants killed

mutants survived

mutation operator

execution result
```

---

## What Is Missing

The correct mutation strategy depends on X1.

Questions still requiring empirical work include:

```text
which operators represent realistic X1 failures?

how many mutants are useful?

which mutations are redundant?

how should timeouts be handled?

how should equivalent mutants be identified?

how should mutation evidence influence PASS versus REVIEW?
```

---

## Why Equivalent Mutants Matter

Some syntactic mutations do not change observable behavior.

Counting such a mutant as:

```text
survived defect
```

would unfairly penalize the test suite.

The first POC can conservatively preserve:

```text
KILLED

SURVIVED

INVALID

ERROR

POSSIBLY_EQUIVALENT
```

rather than pretend equivalent-mutant detection is solved.

---

## Example Result Contract

```python
from enum import StrEnum
from dataclasses import dataclass


class MutantOutcome(StrEnum):
    KILLED = "killed"
    SURVIVED = "survived"
    INVALID = "invalid"
    ERROR = "error"
    POSSIBLY_EQUIVALENT = "possibly_equivalent"


@dataclass(frozen=True, slots=True)
class MutationResult:
    mutant_id: str
    operator: str
    outcome: MutantOutcome

    execution_receipt_id: str | None

    details: str
```

---

# 18. NI-12 — Hierarchical / Advanced Statistical Campaign Inference

**Status:** DEFERRED

## What Exists

Component 5 can calculate transparent campaign statistics such as:

```text
task success

false release

false rejection

review rate

automation coverage

simple proportion confidence intervals
```

Wilson score intervals are a reasonable starting point for simple binomial proportions.

---

## What Is Missing

Repeated AI runs create hierarchical structure:

```text
benchmark case
    |
    +-- run 1
    +-- run 2
    +-- run 3
```

Cases themselves may cluster by:

```text
repository

task subtype

generator

difficulty
```

More mature analysis may therefore require:

```text
cluster-aware bootstrap

hierarchical Bayesian model

mixed-effects model

case-level aggregation

stratified analysis
```

---

## Why It Is Deferred

The correct method depends on the actual benchmark structure.

Implementing sophisticated statistics before observing:

```text
number of cases

runs per case

failure frequency

strata

correlation structure
```

would create unnecessary complexity.

---

## Interim Statistical Rule

Preserve:

```text
case_id

run_id

task stratum

repository

benchmark version
```

so advanced analysis remains possible later.

Do not pretend repeated runs are independent tasks.

---

# 19. NI-13 — Production Token, Compute, and Cost Attribution

**Status:** PARTIALLY IMPLEMENTED

## What Exists

The architecture recognizes resource usage as a first-class output.

At minimum the system should support:

```text
input tokens

output tokens

model calls

wall time

sandbox compute

test executions

mutation executions
```

---

## What Is Missing

Production cost attribution requires:

```text
actual enterprise model pricing

Azure compute pricing

storage pricing

network charges where material

human-review effort

internal cost allocation rules
```

These values change and may be negotiated enterprise rates rather than public prices.

---

## Architectural Rule

Component 5 should measure.

Component 8 should monetize.

Do not put cloud price tables inside `EvaluationCampaignRunner`.

---

## Example Usage Contract

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelUsage:
    model_configuration_id: str
    purpose: str

    input_tokens: int
    output_tokens: int
    calls: int

    latency_seconds: float


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    model_usage: tuple[ModelUsage, ...]

    sandbox_cpu_seconds: float
    sandbox_wall_seconds: float

    test_executions: int
    mutation_executions: int
```

This contract is measurable without assigning monetary value.

---

# 20. NI-14 — Operational Telemetry Integration for Released Code

**Status:** PARTIALLY IMPLEMENTED

## What Exists

The architecture defines a post-release measurement layer.

Possible normalized technical metrics include:

```text
execution success

latency

runtime errors

availability

resource usage

rollback

incident signal
```

---

## What Is Missing

Actual metrics depend on the runtime environment of the code that X1 modifies.

Different X1 changes may affect:

```text
API service

batch process

data pipeline

workflow

mortgage-processing service

internal platform component
```

The telemetry source therefore cannot be implemented generically without choosing the X1 target environment.

---

## Example Adapter Boundary

```python
from typing import Protocol


class OperationalMetricsPort(Protocol):
    def fetch_metrics(
        self,
        *,
        deployment_id: str,
        window_start_utc,
        window_end_utc,
    ):
        ...


class EnterpriseOperationalMetricsAdapter:
    def fetch_metrics(
        self,
        *,
        deployment_id: str,
        window_start_utc,
        window_end_utc,
    ):
        raise NotImplementedError(
            "NI-14: Production operational telemetry requires the target "
            "service, deployment lineage, approved telemetry source, metric "
            "definitions, and enterprise access configuration. "
            "See NOT-IMPLEMENTED.md."
        )
```

---

# 21. NI-15 — Process-Outcome and Business-KPI Connectors

**Status:** DEFERRED

## What Exists

The measurement architecture distinguishes:

```text
Layer 1 — Engineering / AI evaluation

Layer 2 — Operational technical metrics

Layer 3 — Process outcomes

Layer 4 — Business KPIs
```

This prevents technical success from being equated automatically with business value.

---

## What Is Missing

Actual process and business metrics depend on the chosen X1 use case.

A mortgage-related example might include:

```text
manual intervention rate

application processing time

rework

straight-through processing

cost per processed application
```

But those are examples, not universal platform metrics.

---

## Why It Is Deferred

Business data access, ownership, definitions, and privacy requirements must be determined by the line of business.

The first POC can validate engineering automation without implementing these connectors.

---

# 22. NI-16 — Finance-Approved Economic Value Model

**Status:** DEFERRED

## What Exists

The architecture can measure:

```text
tokens

compute

review rate

task throughput

automation coverage

latency
```

These can become inputs to economic analysis.

---

## What Is Missing

A credible enterprise value model requires agreement on:

```text
baseline human effort

offshore contractor cost

fixed versus variable cost

human-review cost

platform operating cost

rework

failure cost

capacity redeployment

realized versus theoretical savings
```

---

## Important Warning

Avoid simplistic arithmetic such as:

```text
automated tasks
x
historical developer hours
x
hourly rate
=
realized savings
```

unless Finance agrees that those hours translate into actual economic benefit.

The system should distinguish:

```text
gross automation-equivalent value
```

from:

```text
realized net economic value
```

---

# 23. NI-17 — Enterprise Security, IAM, and Network Hardening

**Status:** OPEN

## What Exists

The architecture creates security-relevant boundaries:

```text
separate change execution

separate release-gate execution

separate hidden oracle

least-privilege ports

no production secrets in generated code

provider-neutral domain services
```

---

## What Is Missing

A complete enterprise security implementation requires:

```text
threat model

identity design

RBAC

network segmentation

private endpoints

container registry policy

image scanning

secret policy

logging policy

security monitoring

incident response

data classification

penetration/security review
```

---

## Why It Cannot Be Invented Here

These are enterprise architecture decisions.

The POC should make them possible.

It should not claim that a few Python classes constitute an approved security architecture.

---

# 24. NI-18 — Artifact Signing, Attestation, and Supply-Chain Evidence

**Status:** DEFERRED

## What Exists

Artifacts can be content-hashed.

This provides identity and integrity checking.

---

## What Is Missing

A more mature platform may require:

```text
signed candidate artifacts

signed container images

SBOM

build provenance

attestations

approved package source

dependency vulnerability evidence
```

---

## Why It Is Deferred

This is valuable production hardening but not necessary to test the central POC hypothesis:

```text
Can X1 be generated, independently gated, and evaluated?
```

It should be integrated with existing enterprise software-supply-chain controls rather than recreated unnecessarily.

---

# 25. NI-19 — Production Human-Review Workflow

**Status:** PARTIALLY IMPLEMENTED

## What Exists

The release gate returns:

```text
HUMAN_REVIEW_REQUIRED
```

with structured reasons.

This is the correct release-gate responsibility.

---

## What Is Missing

The actual review workflow may require:

```text
Jira/Azure DevOps work item

review assignment

PR status

evidence links

review SLA

approval authority

audit record

resubmission path
```

---

## Why the Human Is Not Inside ReleaseGateService

The gate's responsibility is:

```text
determine that automation cannot safely resolve the candidate
```

The workflow system's responsibility is:

```text
obtain human action
```

This separation should remain.

---

## Example Publisher

```python
class HumanReviewPublisher:
    def request_review(
        self,
        *,
        run_id: str,
        candidate_id: str,
        reason_codes: tuple[str, ...],
        evidence_ids: tuple[str, ...],
    ) -> None:

        raise NotImplementedError(
            "NI-19: Human-review workflow requires the enterprise-approved "
            "work-item/PR mechanism, reviewer ownership, authorization, and "
            "audit process. See NOT-IMPLEMENTED.md."
        )
```

---

# 26. NI-20 — Automatic Production Deployment and Rollback

**Status:** DEFERRED

## What Exists

The architecture can reach:

```text
GateOutcome.PASS
```

and then publish a workflow state equivalent to:

```text
READY_FOR_RELEASE
```

---

## What Is Missing

The POC does not automatically deploy generated code to production.

Production deployment would require:

```text
release authorization

segregation of duties

deployment window

deployment strategy

rollback

health verification

change-management integration

incident handling
```

---

## Why It Is Deferred

The central POC hypothesis does not require autonomous production deployment.

A credible first demonstration can stop at:

```text
candidate generated

candidate gated

evidence persisted

PR/workflow status published
```

This avoids adding production blast radius before the assurance system itself has been validated.

---

# 27. NI-21 — Production Feedback / Automatic Learning Loop

**Status:** DEFERRED

## What Exists

The design may collect future signals such as:

```text
production error

rollback

human review

incident

process outcome

business KPI
```

---

## What Is Missing

The platform does not automatically use those signals to change:

```text
prompts

skills

gate thresholds

Evidence Diversity Mapper

benchmark

model selection
```

---

## Why It Is Deliberately Deferred

Automatic feedback can create a self-modifying assurance system.

Questions arise immediately:

```text
Who approved the new capability?

Was it requalified?

Did production noise contaminate the policy?

Can the previous configuration be reproduced?

Did benchmark leakage occur?
```

The first POC should:

```text
observe
+
store
+
analyze
```

rather than:

```text
automatically modify itself
```

---

# 28. NI-22 — Real Historical L1 Task Distribution and Representativeness Study

**Status:** OPEN

## What Exists

Synthetic benchmark cases can validate system mechanics.

The architecture supports benchmark metadata and slices.

---

## What Is Missing

We do not yet have a statistically characterized population of real X1/L1 work.

Relevant questions include:

```text
What task categories dominate?

What percentage are repetitive?

How often are requirements ambiguous?

How many repositories are involved?

What languages/frameworks dominate?

What is typical patch size?

How strong are existing tests?

How often are external dependencies involved?

What historical human-review effort is required?
```

---

## Why This Matters

A benchmark can be internally excellent but externally irrelevant.

Qualification claims should eventually be conditioned on how closely the benchmark represents the intended production population.

---

## Example Analysis Shape

Once historical task metadata is approved:

```text
Historical X1 Work
        |
        +--> task category distribution
        +--> repository distribution
        +--> complexity descriptors
        +--> failure type
        +--> historical effort

                versus

Benchmark X1
        |
        +--> same descriptors
```

Large mismatches should reduce confidence in external validity.

---

# 29. NI-23 — Capability Qualification Governance and Approval Authority

**Status:** OPEN

## What Exists

Component 5 can generate qualification evidence.

The architecture distinguishes:

```text
Candidate Release Gate
```

from:

```text
Capability Qualification Gate
```

---

## What Is Missing

The software cannot decide the organization's risk appetite.

A governance process must determine:

```text
who approves X1 for production?

what false-release tolerance is acceptable?

what confidence/uncertainty is required?

what automation coverage is economically meaningful?

what NI items block production?

what changes trigger requalification?
```

---

## Why It Is Not Implemented as Code

These are policy and accountability decisions.

A future deterministic qualification-policy engine can encode approved rules.

The rules themselves should not be invented by the engineering implementation.

---

# 30. NI-24 — Long-Term Schema Migration and Evidence-Retention Migration

**Status:** DEFERRED

## What Exists

The architecture recognizes that persisted contracts should have explicit schema identity/versioning.

---

## What Is Missing

Long-lived systems eventually require migration of:

```text
TaskRequest schema

CandidateArtifact schema

EvidenceArtifact schema

GateDecision schema

CampaignReport schema
```

as well as possible migration of storage layout.

---

## Why It Is Deferred

The POC has not yet accumulated long-lived historical data.

The important current requirement is:

```text
do not assume schema evolution is free
```

and preserve version identifiers in persisted contracts where appropriate.

---

# 31. NI-25 — Production Concurrency, Stale Base, and Merge Conflict Strategy

**Status:** PARTIALLY IMPLEMENTED

## What Exists

Candidate identity can bind:

```text
repository

baseline revision

patch
```

This allows stale-base detection conceptually.

---

## What Is Missing

A production system must determine what happens when:

```text
Task A starts from revision R

Task B starts from revision R

Task A merges

Task B attempts release
```

Possible strategies include:

```text
serial processing

branch isolation

stale-base FAIL

automatic rebase followed by new candidate identity and re-gating

human-review escalation
```

---

## Important Assurance Rule

If code changes after gating:

```text
new bytes
=
new candidate
=
new gate evaluation
```

A rebase cannot silently inherit the previous PASS.

---

# 32. Additional Implementation Gap — Production Evidence Planner Strategy

This capability is partly represented under NI-10 but deserves an explicit design note.

The planner can be implemented structurally before its strategy is empirically optimal.

A simple development implementation might:

```text
read required evidence families from GatePolicy

inspect already available evidence

request missing mandatory families

apply budget

terminate
```

A more advanced planner could use AI to generate task-specific failure hypotheses.

---

## Example Development Planner

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceRequest:
    evidence_family: str
    reason: str
    priority: int


class DeterministicEvidencePlanner:
    """
    Minimal fully implemented planner suitable for the POC.

    This planner is deliberately conservative and understandable.

    It does not claim to be an optimal production evidence-planning policy.
    """

    def plan(
        self,
        *,
        required_families: tuple[str, ...],
        available_families: tuple[str, ...],
    ) -> tuple[EvidenceRequest, ...]:

        available = set(
            available_families
        )

        return tuple(
            EvidenceRequest(
                evidence_family=family,
                reason=(
                    "Required evidence family is not currently available."
                ),
                priority=1,
            )
            for family in required_families
            if family not in available
        )
```

This is preferable to leaving the entire planner unimplemented.

AI-assisted planning can be layered on later and evaluated independently.

---

# 33. Additional Implementation Gap — Semantic Review Calibration

AI semantic review can identify:

```text
requirement misunderstanding

incorrect assumptions

unhandled edge cases

suspicious API usage

business-semantic risk
```

However, the system should not treat:

```text
LLM says HIGH risk
```

as equivalent to a deterministic critical defect without calibration.

A semantic-review finding should initially be represented as evidence.

Where practical, the planner should convert the finding into an executable challenge.

Example:

```text
AI finding:
"The implementation may mishandle the inclusive upper boundary."

        |
        v

generated targeted tests:
limit - 1
limit
limit + 1

        |
        v

deterministic execution
```

The transformation from semantic concern to testable evidence can be implemented before attempting to calibrate AI self-confidence.

---

# 34. Additional Implementation Gap — Generated Test Validation

AI-generated tests themselves can be wrong.

Therefore generated tests should eventually be checked for:

```text
syntax validity

execution validity

requirement linkage

trivial assertions

duplicate behavior

implementation overfitting

nondeterministic dependencies

mutation sensitivity
```

A first POC does not require a perfect universal test validator.

It should at minimum distinguish:

```text
test generated

test parsed

test executed

test produced valid assertion result
```

from:

```text
test generation attempted
```

---

# 35. Additional Implementation Gap — Near-Duplicate Evidence Detection

Exact duplicates are easy to remove using content hashes.

Near-duplicate evidence is harder.

For example:

```text
assert add(1, 2) == 3

assert add(2, 3) == 5

assert add(5, 8) == 13
```

may provide useful execution breadth but still exercise one behavioral concept.

Future Evidence Diversity Mapper versions may use:

```text
test structure

assertion target

code coverage

semantic embedding

mutation-kill profile
```

to estimate redundancy.

This should be treated as experimental.

Do not label the resulting score as true statistical independence without validation.

---

# 36. Additional Implementation Gap — Deterministic Test Flakiness Detection

A test written in ordinary Python is not automatically deterministic.

Potential nondeterminism includes:

```text
clock dependence

network dependence

randomness

thread scheduling

filesystem ordering

external service state
```

A mature gate may rerun suspect tests or classify them as flaky.

For the POC, tests intended as hard veto evidence should preferably:

```text
avoid external dependencies

control randomness

use deterministic fixtures

use bounded time
```

---

# 37. Additional Implementation Gap — Resource Budgets

The architecture supports budgets conceptually.

Actual production budgets remain empirical.

Examples:

```text
max LLM calls per candidate

max input/output tokens

max mutation executions

max sandbox CPU seconds

max wall time
```

Development configuration may use explicit experimental values.

Do not label those values as production-calibrated.

---

# 38. Additional Implementation Gap — Candidate Repair Loops

The change executor may eventually support bounded repair.

Example:

```text
Candidate C1
     |
     v
mechanical compile failure
     |
     v
structured feedback
     |
     v
ChangeExecution attempt 2
     |
     v
Candidate C2
```

Important rule:

```text
C2 is a NEW candidate.
```

The release gate should not silently repair C1 and then claim that C1 passed.

---

## Suggested Development Policy

A POC can use:

```text
maximum attempts = small explicit number

only clearly defined repair categories

new candidate identity per attempt

all failed attempts retained

token usage accumulated
```

The correct production retry/repair budget remains empirical.

---

# 39. Additional Implementation Gap — Infrastructure Retry Policy

Retries should be reason-aware.

Potentially retryable:

```text
temporary network failure

rate limit

transient Azure service error
```

Usually not retryable as infrastructure:

```text
compiler failure

deterministic test failure

policy violation
```

The system should record:

```text
retry reason

retry count

candidate identity

whether a new candidate was generated
```

Do not use:

```text
retry until something passes
```

as a hidden optimization strategy.

---

# 40. Additional Implementation Gap — Qualification Holdout Governance

A serious qualification process should distinguish:

```text
development/calibration benchmark

hidden qualification benchmark
```

The qualification set should not be repeatedly inspected while prompts and thresholds are tuned.

The POC can implement the mechanical separation.

Ownership and access governance require enterprise agreement.

---

# 41. Additional Implementation Gap — Benchmark Contamination Analysis

Private internally generated cases reduce some public benchmark contamination risk.

They do not prove absence of leakage or structural shortcuts.

Potential problems include:

```text
benchmark generator and solver share templates

task wording reveals defect type

repository naming reveals expected behavior

hidden files remain in Git history

reference patch is accidentally mounted
```

A production qualification environment should include explicit leakage checks.

---

# 42. Additional Implementation Gap — Qualification Slice Policy

Aggregate performance may hide poor performance on important subtypes.

Examples:

```text
configuration changes

boundary-condition fixes

API edits

validation logic

dependency updates
```

Component 5 should preserve slice metadata.

The exact minimum performance requirements per slice remain a governance decision.

---

# 43. Additional Implementation Gap — False-Release Investigation Workflow

Every false release should produce a structured investigation.

Suggested questions:

```text
Was the task specification ambiguous?

Was the candidate-generation reasoning wrong?

Was the relevant evidence family absent?

Did generated tests share the blind spot?

Did mutation fail to represent the defect?

Did Evidence Diversity Mapper miss the gap?

Did gate policy ignore a meaningful signal?

Was the hidden oracle itself wrong?
```

A formal root-cause workflow can be implemented after real campaigns begin producing enough failures to justify one.

---

# 44. Additional Implementation Gap — Human Review Outcome Capture

While the human reviewer should remain outside `ReleaseGateService`, later evaluation may benefit from capturing:

```text
human accepted

human rejected

human modified candidate

reason

review duration
```

This data can help measure:

```text
review burden

false escalation

economic cost

future benchmark quality
```

The first POC only needs the gate's review signal.

---

# 45. Additional Implementation Gap — Real Production Deployment Lineage

Once production deployment exists, the system should connect:

```text
Deployment
    |
    +-- candidate_id
    +-- candidate_sha256
    +-- gate_decision_id
    +-- capability_identity
    +-- qualification_campaign_id
```

This allows a later incident to be traced back through the assurance chain.

The POC can preserve the necessary IDs even before deployment integration exists.

---

# 46. Additional Implementation Gap — Causal Business Attribution

The architecture intentionally does not implement automatic causal claims such as:

```text
AI automation increased mortgage throughput by 7%.
```

Observed business improvement may be influenced by:

```text
volume

staffing

other releases

policy changes

seasonality

upstream systems

downstream systems
```

If causal attribution becomes important later, suitable analytical designs may include:

```text
controlled rollout

matched comparison

difference-in-differences

interrupted time series
```

depending on circumstances.

This is outside the first engineering POC.

---

# 47. What Is Fully Reasonable to Implement Now

Not every capability should remain behind `NotImplementedError`.

The following pieces are sufficiently provider-neutral to implement now:

```text
canonical data contracts

content hashing

candidate identity validation

deterministic gate-policy engine

local evidence repository

local deterministic execution fixtures

EvidencePlanner interfaces

basic Evidence Diversity Mapper

mutation-result contracts

campaign classifications

false-release calculation

Wilson intervals

campaign aggregation

resource-usage aggregation

local composition root

architecture dependency checks

configuration validation

task capability parsing

hidden-oracle interface

synthetic development oracle

deterministic B4 E2E fixture

deterministic B5 campaign fixture
```

These should be implemented rather than left as placeholders.

---

# 48. What Should Explicitly Remain Enterprise-Dependent

The following should not be fabricated:

```text
production Azure identities

RBAC

network topology

private endpoints

production model deployment

production source repository permissions

production Jira/Azure DevOps authorization

production hidden-oracle storage

production retention policy

production false-release tolerance

production human-review ownership

production business KPI connectors

Finance-approved savings assumptions
```

---

# 49. Recommended Exception Pattern

For a missing production adapter:

```python
class ProductionCapabilityUnavailable(RuntimeError):
    """
    Raised when a required production capability has deliberately not yet
    been implemented or approved.
    """


def require_azure_hidden_oracle():
    raise ProductionCapabilityUnavailable(
        "NI-07: Production hidden-oracle execution is unavailable. "
        "The current repository contains only the provider-neutral port "
        "and deterministic local fixture. See NOT-IMPLEMENTED.md."
    )
```

This is an acceptable evolution beyond `NotImplementedError`.

The important requirement is explicit failure semantics.

---

# 50. Dangerous Placeholder Patterns

The following patterns should trigger review.

## Fake PASS

```python
def gate(candidate):
    # TODO: real implementation later.
    return GateOutcome.PASS
```

This is prohibited.

---

## Fake Evidence

```python
def run_security_scan(candidate):
    return {
        "critical_findings": 0
    }
```

when no scan occurred.

This is prohibited.

Use:

```python
raise NotImplementedError(
    "NI-XX: security scan adapter is not implemented."
)
```

---

## Silent Empty Result

```python
def collect_mutation_results(candidate):
    return []
```

when mutation analysis was never executed.

An empty real result and unavailable analysis are different states.

---

## Broad Exception Conversion

```python
try:
    evidence = collect_evidence()
except Exception:
    return GateOutcome.FAIL
```

This destroys failure semantics.

---

## Fake Azure Adapter

```python
class AzureEvidenceRepository:
    def put(self, artifact):
        print("uploaded")
```

This is not a production adapter.

Name it clearly as a local/test fake if it exists only for demonstration.

---

# 51. Naming Rules for Test and Local Implementations

Use names that reveal trust level.

Good:

```text
InMemoryEvidenceRepository

LocalDeterministicSandbox

DeterministicX1ChangeExecutionService

FakeWorkflowPublisher

SyntheticHiddenOracle
```

Avoid calling these:

```text
EvidenceRepository

ProductionSandbox

DefaultOracle
```

if they are not production implementations.

A developer should be able to identify the trust level from the class name.

---

# 52. Production Adapter Completion Standard

An NI production adapter should not be considered implemented merely because API calls exist.

For example, an Azure execution adapter should also establish:

```text
configuration validation

authentication

authorization

timeout semantics

resource bounds

candidate identity

error mapping

correlation ID

execution receipt

integration tests

failure-path tests

telemetry
```

Likewise, an evidence repository needs more than:

```text
blob_client.upload_blob(...)
```

---

# 53. Implementation Completion Checklist for an NI Item

Before changing an NI item to IMPLEMENTED:

```text
[ ] Production implementation exists.

[ ] Provider-neutral interface remains intact.

[ ] Configuration is validated.

[ ] No production secrets are committed.

[ ] Errors have explicit semantics.

[ ] Candidate/task/run identity is preserved where applicable.

[ ] Resource usage is measured where applicable.

[ ] Unit tests exist.

[ ] Contract tests exist where appropriate.

[ ] Integration test exists.

[ ] Failure path is tested.

[ ] NOT-IMPLEMENTED.md is updated.

[ ] DESIGN-RATIONALE.md remains consistent.

[ ] B7 architecture checks pass.

[ ] Qualification impact has been considered.
```

---

# 54. Material Implementation Changes and Requalification

Completing some NI items may not alter AI behavior.

For example:

```text
replace in-memory evidence repository
with Azure Blob adapter
```

may primarily be infrastructure work.

Other NI implementations can materially change capability behavior.

Examples:

```text
new production model adapter

new Evidence Diversity Mapper

new mutation strategy

new gate policy

new EvidencePlanner

new sandbox environment
```

These changes should trigger consideration of requalification.

Do not assume:

```text
implementation completed
```

means:

```text
previous campaign evidence remains automatically applicable.
```

---

# 55. Recommended NI Dependency Order

The NI items do not all need to be completed before the first meaningful POC.

A reasonable sequence is:

```text
FIRST
-----

NI-08
define and validate a useful X1 development benchmark

NI-10
implement usable evidence-diversity coordination

NI-11
implement mutation evidence appropriate to X1

NI-01
connect approved model endpoint

NI-02
connect isolated change execution

NI-03
connect isolated gate execution


SECOND
------

NI-04
production evidence persistence

NI-06
durable orchestration/idempotency

NI-07
isolated hidden-oracle execution

NI-05
workflow integration


THEN
----

NI-09
calibrate gate policy from evidence

NI-13
production resource/cost attribution

NI-17
enterprise security hardening


LATER
-----

NI-14
operational metrics

NI-15
business/process metrics

NI-16
economic value

NI-18
additional supply-chain assurance

NI-20
autonomous deployment

NI-21
feedback learning
```

This ordering is not absolute.

It reflects the POC's core objective:

```text
change execution
+
release gating
+
pipeline-level evaluation
```

---

# 56. Minimum POC Without Completing Every NI Item

A meaningful first POC can operate with:

```text
approved X1 development task

local or approved Azure code execution

real model adapter

real ReleaseGateService

generated tests

deterministic tests

static evidence

mutation evidence

Evidence Diversity Mapper

deterministic GatePolicy

validated synthetic benchmark

hidden oracle

EvaluationCampaignRunner

resource measurement
```

while keeping:

```text
automatic deployment

business KPI integration

automatic feedback learning

full Finance model
```

deferred.

---

# 57. What Must Not Be Mocked Away in the Core Experiment

Some capabilities are essential to the hypothesis.

These should be real enough to evaluate:

```text
candidate identity

actual candidate generation

actual gate evidence

deterministic execution

actual gate policy

hidden oracle separation

benchmark truth

false-release measurement

resource accounting
```

If these are entirely mocked, the POC becomes only an architecture demonstration.

---

# 58. What May Be Manual During the First Demo

The following can reasonably be performed manually or through a simple local abstraction:

```text
task selection

initial benchmark curation

human-review assignment

production deployment

business KPI retrieval

Finance valuation

enterprise task-intake prioritization
```

This keeps the POC focused.

---

# 59. Required Comments Around Unimplemented Code

Every deliberately unimplemented production method should explain:

```text
WHAT is missing

WHY it is missing

WHICH NI item tracks it

WHAT information is required to implement it

WHAT the safe current behavior is
```

Example:

```python
def publish_to_production_workflow(
    self,
    decision,
) -> None:
    """
    Publish a candidate-bound GateDecision to the production engineering
    workflow.

    This cannot be implemented responsibly until the target Jira/Azure DevOps
    project, authentication mechanism, work-item conventions, and authorization
    rules are approved.

    Local development should use InMemoryWorkflowPublisher instead.

    NI-05 tracks the production implementation.
    """

    raise NotImplementedError(
        "NI-05: production workflow publication is not configured. "
        "See NOT-IMPLEMENTED.md."
    )
```

This standard makes the repository safer for junior maintainers.

---

# 60. Recommended Automated NI Audit

A future repository audit can detect untracked `NotImplementedError` calls.

Example:

```python
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


NI_PATTERN = re.compile(
    r"\bNI-\d{2}\b"
)


@dataclass(frozen=True, slots=True)
class UntrackedNotImplemented:
    path: Path
    line: int


def find_untracked_not_implemented(
    package_root: Path,
) -> tuple[UntrackedNotImplemented, ...]:
    """
    Find NotImplementedError calls that do not include an NI identifier.

    This is intentionally a static best-effort check.

    It does not replace review of whether the NI documentation is still
    semantically accurate.
    """

    findings: list[
        UntrackedNotImplemented
    ] = []

    for path in package_root.rglob(
        "*.py"
    ):
        tree = ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(path),
        )

        for node in ast.walk(
            tree
        ):
            if not isinstance(
                node,
                ast.Raise,
            ):
                continue

            exc = node.exc

            if not isinstance(
                exc,
                ast.Call,
            ):
                continue

            if not isinstance(
                exc.func,
                ast.Name,
            ):
                continue

            if (
                exc.func.id
                != "NotImplementedError"
            ):
                continue

            message_parts: list[
                str
            ] = []

            for arg in exc.args:
                if (
                    isinstance(
                        arg,
                        ast.Constant,
                    )
                    and isinstance(
                        arg.value,
                        str,
                    )
                ):
                    message_parts.append(
                        arg.value
                    )

            message = " ".join(
                message_parts
            )

            if not NI_PATTERN.search(
                message
            ):
                findings.append(
                    UntrackedNotImplemented(
                        path=path,
                        line=node.lineno,
                    )
                )

    return tuple(
        findings
    )
```

This can later become part of the B7 static architecture review.

---

# 61. Recommended NI Status Object

If the project eventually wants machine-readable NI status, a simple manifest can be added.

Example:

```yaml
not_implemented:

  NI-01:
    name: "Production Azure model client"
    status: "partial"
    component:
      - "change_execution"
      - "release_gate"

  NI-07:
    name: "Production Azure hidden-oracle executor"
    status: "partial"
    component:
      - "evaluation"

  NI-20:
    name: "Automatic production deployment and rollback"
    status: "deferred"
    component:
      - "external_release"
```

The Markdown file should remain the explanatory human-facing document.

The manifest would exist only if automation benefits justify it.

---

# 62. Things That Should Never Be Marked "Implemented" Based Solely on a Demo

Do not mark a capability implemented merely because:

```text
a notebook executed once

an Azure resource exists

a model produced a good answer

a test passed locally

a mock returned success

one synthetic task worked
```

Implementation status should describe engineering completeness.

Qualification status should describe measured capability.

Those are different.

---

# 63. Implementation Status Versus Qualification Status

A component may be fully implemented but unqualified.

Example:

```text
ReleaseGateService implementation:
COMPLETE

X1 release-gate qualification:
NOT YET ESTABLISHED
```

Conversely:

```text
local synthetic benchmark:
implemented

production historical benchmark:
not implemented
```

Do not use one status field to represent both.

---

# 64. NI Items That Block the First Real AI Evaluation

Before a genuine model-backed B5 campaign, the following must have sufficiently real implementations:

```text
NI-01
model client

NI-02
change execution environment

NI-03
gate execution environment or acceptable POC equivalent

NI-08
validated X1 benchmark

NI-10
usable evidence-diversity mechanism

NI-11
usable mutation mechanism
```

NI-07 can initially use a rigorously isolated local/private evaluation environment if Azure isolation is not yet required for the first development campaign.

However, a production qualification claim should eventually use the intended hidden-oracle isolation boundary.

---

# 65. NI Items That Block Production Qualification

A production qualification exercise should not proceed until:

```text
hidden oracle isolation is credible

benchmark is frozen and validated

capability identity is frozen

gate policy is frozen

resource accounting works

campaign evidence is immutable enough for audit

material infrastructure differences are understood
```

Relevant NI items include at least:

```text
NI-04

NI-07

NI-08

NI-09

NI-13

NI-17

NI-23
```

depending on the intended qualification claim.

---

# 66. NI Items That Do Not Block the Core POC

The following can reasonably remain deferred during the initial core experiment:

```text
NI-15
business KPI connectors

NI-16
Finance-approved ROI

NI-18
extended supply-chain attestation

NI-20
automatic production deployment

NI-21
automatic feedback learning

NI-24
long-term schema migration
```

Their absence should remain visible.

It should not prevent testing:

```text
generation

gating

evaluation
```

---

# 67. Azure Identity Separation — Required Future Implementation

One of the highest-value future infrastructure tasks is enforcing separate identities.

Conceptually:

```text
CHANGE EXECUTION IDENTITY
    |
    +--> read authorized source
    +--> read public task artifacts
    +--> write candidate
    |
    X--> hidden oracle


RELEASE GATE IDENTITY
    |
    +--> read candidate
    +--> read public specification
    +--> execute gate evidence
    +--> write gate evidence
    |
    X--> hidden oracle


HIDDEN ORACLE IDENTITY
    |
    +--> read candidate
    +--> read hidden benchmark
    +--> write OracleAssessment
```

The source code already reflects this trust model.

NI-17/NI-07 track the production infrastructure realization.

---

# 68. Azure Network Isolation — Required Future Implementation

Separate identities alone may not be sufficient.

A mature deployment should determine:

```text
which jobs need outbound internet?

which Azure services are reachable?

does generated code need network access?

should private endpoints be used?

how are DNS and egress controlled?

what data may be sent to model endpoints?
```

The POC can begin with strict network assumptions.

Production policy must be enterprise-approved.

---

# 69. Azure Container Image Policy — Required Future Implementation

Execution-image identity affects reproducibility.

The production implementation should eventually use:

```text
approved registry

scanned image

immutable image digest

pinned language/runtime dependencies
```

rather than relying only on:

```text
latest
```

tags.

A material execution-image change may affect qualification and should be tracked through capability/environment identity.

---

# 70. Hidden Oracle Should Not Share Mounts With Online Jobs

Avoid a deployment such as:

```text
one storage mount

/public
/hidden
```

with software convention being the only thing preventing the online gate from reading:

```text
/hidden
```

Prefer separate identity-controlled resources.

This is part of NI-07 and NI-17.

---

# 71. Production Evidence Retention Questions Still Requiring Decisions

Before NI-04 is closed, determine:

```text
How long are candidate patches retained?

How long are generated tests retained?

Are prompts retained?

Are model outputs retained?

Are source snapshots retained?

How are hidden oracle artifacts retained?

Can engineers retrieve historical evidence?

Who can retrieve it?

What must be deleted?

What must be immutable?

What audit requirements apply?
```

These are not appropriate guesses for the application developer.

---

# 72. Human Review Questions Still Requiring Decisions

Before NI-19 is closed, determine:

```text
Who is eligible to review?

Does reviewer seniority depend on task risk?

Can the original change-generation operator review?

What evidence is shown?

Can the reviewer edit the candidate?

If edited, does it become a new candidate?

Is re-gating mandatory after edits?

How is approval recorded?

How does review affect evaluation statistics?
```

The architectural default should remain:

```text
human edit
=
new candidate
=
new candidate identity
=
new gate evaluation
```

unless an explicitly approved workflow says otherwise.

---

# 73. Qualification Governance Questions Still Requiring Decisions

Before NI-23 can be considered implemented, define:

```text
Who owns X1?

Who owns GatePolicy?

Who owns the benchmark?

Who has access to the hidden holdout?

Who can change thresholds?

Who approves model changes?

Who accepts false-release risk?

What campaign result permits production?

What changes require full requalification?

What changes require only regression evaluation?
```

Software can enforce these rules after the organization defines them.

---

# 74. Current POC Confidence Claims That Are Allowed

The system may eventually claim something like:

```text
On validated synthetic benchmark B version 2.0,
capability X1 configuration C completed N cases,
automatically released R cases,
produced F false releases,
and had the reported uncertainty intervals.
```

This is an evidence-grounded statement.

---

# 75. Confidence Claims That Are Not Yet Allowed

Do not claim:

```text
X1 is 99.9% safe in production.

All L1 work can be automated.

The gate guarantees correctness.

The Evidence Diversity Mapper removes LLM blind spots.

Zero observed false releases means zero release risk.

Synthetic benchmark results directly equal real-production performance.

A high mutation score means production correctness.
```

Those conclusions require evidence that the current POC does not yet possess.

---

# 76. Relationship Between NI Items and Experiments

Some NI items can only be resolved empirically.

For example:

```text
NI-09 gate calibration

NI-10 evidence diversity calibration

NI-11 mutation strategy

NI-12 statistical sophistication

NI-22 representativeness
```

The correct implementation sequence is:

```text
implement measurable mechanism

run experiment

analyze evidence

update design

version capability
```

not:

```text
invent threshold

encode threshold

call it production-ready
```

---

# 77. Evidence Diversity Ablation Required Before NI-10 Closure

A useful experiment is:

```text
CONTROL

fixed token budget
+
ordinary generated tests


VERSUS


TREATMENT

same approximate token budget
+
Evidence Diversity Mapper
+
targeted evidence generation
```

Compare:

```text
hidden defect detection

false releases

mutation survivors

review rate

token cost

latency
```

If the mapper does not materially improve outcomes, simplify the design.

NI-10 should not be closed merely because the code exists.

---

# 78. Mutation Ablation Required Before NI-11 Closure

Compare gate variants such as:

```text
A
existing + generated tests

B
existing + generated tests + mutation

C
existing + generated tests + mutation + diversity mapping
```

Measure:

```text
false-release detection

additional review

compute cost

wall time

incremental evidence value
```

This determines whether mutation provides enough value for X1.

---

# 79. Model-Diversity Experiment

The architecture permits testing:

```text
Condition A
same model generates candidate and tests

Condition B
same model + Evidence Diversity Mapper

Condition C
model A generates candidate
model B generates tests

Condition D
model diversity
+
tool diversity
+
mutation
+
evidence diversity
```

The benchmark should determine which approach performs better.

Do not assume model diversity is automatically independent verification.

---

# 80. Token-Budget Experiment

Measure at least:

```text
change_execution_tokens

gate_planning_tokens

gate_test_generation_tokens

diversity_mapper_tokens

semantic_review_tokens

total_gate_tokens

total_pipeline_tokens
```

Then compare those costs with:

```text
false-release prevention

automation coverage

review rate
```

This addresses the earlier concern that sophisticated gating may consume as many or more tokens than candidate generation.

---

# 81. Deterministic Compute Experiment

Separately measure:

```text
test executions

mutation executions

CPU seconds

sandbox wall time

container starts
```

This prevents repeated deterministic testing from being misinterpreted as LLM token cost.

---

# 82. Small-Sample Discipline

The POC may begin with a limited number of benchmark cases.

If so, the correct result may be:

```text
evidence remains too limited for a strong reliability claim
```

Do not search for a statistical technique that makes a small dataset look precise.

The uncertainty is part of the result.

---

# 83. NI Closure Must Preserve Historical Evidence

Suppose NI-10 is eventually closed because a new mapper implementation exists.

Do not overwrite historical campaign reports.

A previous campaign remains evidence about:

```text
old capability configuration
```

The new mapper should create:

```text
new capability identity

new campaign
```

where behavior materially changes.

---

# 84. Recommended NOT-IMPLEMENTED Code Review Questions

When encountering an NI location, ask:

```text
1. Is the capability genuinely impossible to implement without missing
   enterprise information?

2. Could a provider-neutral portion be implemented now?

3. Does the current failure make the limitation obvious?

4. Could a caller misinterpret the failure as PASS or success?

5. Is the NI identifier documented here?

6. Does the code explain how the future implementation should behave?

7. Does the future implementation affect capability qualification?

8. Is a local deterministic implementation useful and clearly labelled?
```

---

# 85. Guidance for Junior Engineers

Do not "fix" a `NotImplementedError` simply by returning an object with default values.

Example:

```python
# WRONG

def assess(...):
    return OracleAssessment(
        acceptability=OracleAcceptability.ACCEPTABLE,
        ...
    )
```

This would convert:

```text
unknown
```

into:

```text
candidate is correct
```

and invalidate the entire evaluation.

Instead, determine:

```text
which NI item applies

which enterprise inputs are missing

which interface contract must be satisfied

which tests are required
```

before implementing the adapter.

---

# 86. Guidance for Junior Data Scientists

When working on evaluation code, distinguish:

```text
software fixture

development benchmark

qualification benchmark
```

A synthetic four-case test fixture is useful for validating:

```text
false-release calculation
```

It is not evidence that the AI platform itself has a 25% false-release rate in production.

Likewise, do not convert:

```text
number of generated tests
```

into:

```text
benchmark sample size
```

without explicit statistical justification.

---

# 87. Guidance for Evaluation Scientists

The most important unresolved evaluation questions are:

```text
benchmark validity

benchmark representativeness

correlated runs

shared model blind spots

evidence-family contribution

gate calibration

abstention tradeoff

sample size

false-release uncertainty
```

B2 deliberately keeps those gaps visible.

The architecture should support rigorous measurement rather than hide them behind implementation completeness.

---

# 88. Guidance for Platform Engineers

The most important unresolved infrastructure questions are:

```text
identity boundaries

Azure execution isolation

network policy

artifact storage

hidden-oracle isolation

idempotency persistence

workflow integration

telemetry

retention

production release controls
```

The domain architecture should remain provider-neutral while those decisions are resolved.

---

# 89. Guidance for Security Review

The following NI items are particularly security-relevant:

```text
NI-02
change execution sandbox

NI-03
release-gate sandbox

NI-04
evidence storage

NI-05
workflow integration

NI-07
hidden oracle

NI-17
IAM/network hardening

NI-18
supply-chain assurance

NI-20
deployment
```

A successful local POC does not close those security questions.

---

# 90. Guidance for Finance / Value Engineering

The following NI items are particularly relevant:

```text
NI-13
resource/cost attribution

NI-14
operational measurement

NI-15
process/business metrics

NI-16
economic model

NI-22
historical task distribution
```

The platform should first produce trustworthy engineering measurements.

Finance/value analysis can then translate those measurements into economic outcomes.

---

# 91. Recommended POC Stopping Point

The first POC should stop when it can credibly demonstrate:

```text
one bounded X1 capability

real AI candidate generation

candidate identity

independent release gating

heterogeneous evidence

mutation evidence

Evidence Diversity Mapper

deterministic GatePolicy

PASS / FAIL / HUMAN_REVIEW_REQUIRED

validated hidden benchmark

EvaluationCampaignRunner

false-release measurement

uncertainty

token/compute measurement
```

It does not need:

```text
autonomous production deployment

automatic feedback learning

complete business KPI integration
```

to answer the core research question.

---

# 92. Minimum "Real" Versus "Simulated" Matrix

| Capability | Can Be Simulated for Software Tests? | Must Be Real for AI POC? | Must Be Enterprise-Grade for Production? |
|---|---:|---:|---:|
| TaskRequest | Yes | Yes | Yes |
| Candidate identity | No fake semantics | Yes | Yes |
| AI generation | Yes for unit tests | Yes | Yes |
| Gate policy | Yes for unit tests | Yes | Yes |
| Test execution | Fixture locally | Yes | Yes |
| Evidence diversity | Simple locally | Yes | Calibrated |
| Mutation | Fixture locally | Yes | Calibrated |
| Hidden oracle | Fixture locally | Yes | Isolated |
| Campaign metrics | Deterministic tests | Yes | Yes |
| Azure persistence | Yes | Optional early | Yes |
| Jira/Azure DevOps | Yes | Optional early | Yes |
| Human workflow | Yes | Optional early | Yes |
| Business KPI | Yes | No | Later |
| Automatic deployment | No requirement | No | Later if approved |

---

# 93. B2 Completion Criteria

B2 should be considered complete when:

```text
[ ] Every known production gap has an NI identifier.

[ ] Every NI entry states its status.

[ ] Every NI entry explains what already exists.

[ ] Every NI entry explains what remains missing.

[ ] Every important missing implementation explains why it cannot yet be
    responsibly completed.

[ ] Production-looking placeholders never silently return success.

[ ] Important unimplemented production methods raise explicit errors.

[ ] Code-level errors reference the appropriate NI item.

[ ] Local/test adapters are clearly named.

[ ] Provider-neutral functionality is implemented where it can reasonably be
    implemented now.

[ ] Enterprise-specific values are not invented.

[ ] Gate thresholds are not falsely labelled production-calibrated.

[ ] Benchmark truth is not assumed merely because it is hidden.

[ ] AI-generated tests are not assumed correct.

[ ] Evidence diversity is not assumed to equal independence.

[ ] Small sample size is not hidden.

[ ] Resource measurement is separated from economic valuation.

[ ] Human review remains outside ReleaseGateService.

[ ] Automatic production deployment remains outside the current POC.

[ ] Feedback learning remains deferred.

[ ] B6/B7 architecture checks can identify stale or untracked
    NotImplementedError sites.

[ ] Closing an NI item requires tests and consideration of requalification.
```

---

# 94. Current Highest-Priority Open Questions

The most important unresolved questions are not all implementation questions.

They are:

```text
1. What exactly is X1?

2. What historical L1 task distribution should X1 represent?

3. How should a production-quality benchmark be constructed?

4. How much independent evidence does the gate actually need?

5. Does the Evidence Diversity Mapper materially reduce false releases?

6. Which mutation operators are meaningful for X1?

7. What is the achievable false-release versus automation-coverage frontier?

8. What fraction of tasks will require human review?

9. How much inference does the release gate consume?

10. How large must the qualification benchmark be?

11. What risk threshold will the organization accept?

12. Which enterprise Azure resources and identities will be approved?
```

Those questions should be answered with experiments and enterprise decisions.

They should not be answered by filling gaps with arbitrary constants.

---

# 95. Current Architectural Position

The repository should therefore make three kinds of statement.

## Implemented

Example:

```text
Candidate identity is content-bound and tested.
```

## Experimentally Implemented but Not Yet Validated

Example:

```text
Evidence Diversity Mapper exists, but its incremental assurance value has
not yet been established.
```

## Not Implemented

Example:

```text
Production Azure hidden-oracle execution is not available because the
enterprise identity/storage/isolation design has not yet been approved.
```

This vocabulary is more informative than a binary:

```text
done / not done
```

---

# 96. Final Principle

This document exists because the worst possible POC is not one with visible gaps.

The worst POC is one in which missing functionality is hidden behind interfaces that appear complete.

For an assurance-oriented engineering platform:

```text
UNKNOWN
```

must remain distinguishable from:

```text
FAIL
```

which must remain distinguishable from:

```text
HUMAN_REVIEW_REQUIRED
```

which must remain distinguishable from:

```text
PASS
```

and:

```text
NOT IMPLEMENTED
```

must remain distinguishable from all four.

The repository should therefore prefer:

```text
explicit incompleteness
```

over:

```text
false completeness.
```

That principle applies particularly strongly to:

```text
Azure security boundaries

hidden-oracle isolation

benchmark quality

gate calibration

economic assumptions

production deployment.
```

---

# 97. B2 Final Status

At the end of the current design phase:

```text
CORE ARCHITECTURE
    defined

CANONICAL CONTRACTS
    defined/reconciled through B1/B6

LOCAL SOFTWARE PATH
    defined through B4

OFFLINE EVALUATION PATH
    defined through B5

CONFIGURATION / COMPOSITION
    defined through B6

ASSURANCE CONSISTENCY REVIEW
    defined through B7

MASTER DOCUMENTATION
    defined through B8
```

The major remaining work is therefore not another conceptual architecture phase.

It is:

```text
implement enterprise-specific adapters

choose and freeze X1

construct and validate benchmark cases

run experiments

measure failures

calibrate the gate

measure cost

determine qualification criteria.
```

The NI register should be maintained throughout that work.

---

END OF NOT-IMPLEMENTED.md

