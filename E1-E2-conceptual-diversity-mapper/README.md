# Conceptual Diversity Mapper

## A Domain-Neutral Engine for Conceptual Coverage Mapping, Gap Detection, and Targeted Expansion

## 1. Overview

The **Conceptual Diversity Mapper** is a reusable software and data-science component for measuring whether a collection of artifacts adequately covers the conceptual space relevant to a task.

The motivating problem is that having many artifacts does not necessarily imply conceptual diversity. A collection may contain substantial lexical, syntactic, or surface-level variation while repeatedly representing the same underlying behaviors, strategies, failure modes, causal structures, or other concepts.

For example, a collection of 1,000 generated tests may contain hundreds of superficially different tests while exercising only a small number of behavioral conditions. Similarly, a large prompt dataset may contain considerable linguistic variation while covering only a narrow range of toxicity mechanisms, bias patterns, reasoning strategies, or policy situations.

The mapper therefore operates on an explicit **conceptual representation** of artifacts rather than treating textual or embedding-space distance as synonymous with conceptual diversity.

The fundamental workflow is:

    Artifact Collection
            |
            v
      Concept Schema
            |
            v
     Concept Mapping
            |
            v
     Coverage Analysis
            |
            v
       Coverage Gaps
            |
            v
    Expansion Requests
            |
            v
    External Generation /
       Data Collection
            |
            v
       Re-Mapping
            |
            v
    Coverage Verification

The system deliberately separates **measurement** from **generation**.

The mapper identifies where conceptual coverage is weak and describes what additional artifacts would improve it. Another system may decide how those artifacts should be generated, collected, executed, or validated.

This separation is particularly important when the mapper participates in higher-stakes workflows such as software-development automation or release assurance.

---

# 2. Initial Application: Evidence Diversity for L1 Engineering Automation

The first integration of the package is an **Evidence Diversity Mapper** supporting an AI-assisted software-development and release-assurance workflow.

In this application, an AI system proposes a candidate code change. Multiple forms of evidence may then be collected about that change, including:

- repository tests;
- generated behavioral tests;
- mutation-analysis results;
- static-analysis findings;
- compiler or type-checker results;
- semantic code review;
- invariant checks;
- dependency-failure tests;
- authorization tests;
- boundary-condition tests;
- concurrency tests;
- temporal-behavior tests.

A large amount of evidence does not necessarily imply that the evidence is conceptually broad.

For example, twenty generated tests derived from one seed test may provide considerably less independent conceptual support than twenty tests examining distinct behavioral conditions.

The Evidence Diversity Mapper therefore asks questions such as:

- Which behaviors have actually been examined?
- Which conceptual regions have strong support?
- Which regions have weak support?
- Which expected regions are absent?
- Which apparent evidence items descend from the same source?
- Which artifacts are conceptually duplicative?
- Which mappings are uncertain?
- What additional evidence would most improve coverage?

The mapper does **not** determine whether the candidate code change should be released.

In particular, it does not own:

- `ReleaseGateService`;
- release policy;
- `PASS`;
- `FAIL`;
- `HUMAN_REVIEW_REQUIRED`;
- test execution;
- mutation execution;
- static-analysis execution;
- code generation.

Its responsibility is narrower:

> Measure conceptual evidence coverage and describe deficiencies in that coverage.

---

# 3. Architectural Decision: Generic Core, Domain-Specific Adapters

A central design decision is to keep the fundamental diversity engine **domain-neutral**, while exposing domain-specific interfaces to clients.

For the initial L1 engineering application, the architecture is:

    L1 Engineering Automation
              |
              v
    EvidenceDiversityMapperAdapter
              |
              v
      GenericDiversityEngine
              |
       +------+------+
       |      |      |
    Mapping Coverage Expansion
       |      |      |
       +------+------+

The L1 client interacts with concepts such as:

- `EvidenceArtifact`;
- `EvidenceBundle`;
- `EvidenceCoverageGap`;
- `EvidenceExpansionRequest`;
- `EvidenceCoverageResult`.

It does not need to know that these are translated internally into generic contracts such as:

- `ArtifactDescriptor`;
- `ConceptMapping`;
- `CoverageRegion`;
- `CoverageGap`;
- `ExpansionRequest`.

This boundary is intentional.

The generic engine can therefore potentially support other domains such as:

- toxic-prompt datasets;
- bias datasets;
- compliant and non-compliant policy examples;
- golden QA datasets;
- evaluation datasets;
- strategy libraries;
- workflow libraries;
- planning datasets;
- code repositories;
- vulnerability corpora;
- synthetic training datasets.

Each domain can define its own artifact representation and Concept Schema while reusing the fundamental mapping, coverage, lineage, uncertainty, duplication, and expansion machinery.

---

# 4. Engineering Principle: Genericity Must Not Leak Into the Client Contract

The generic engine is an implementation and product-line decision.

It should not impose additional complexity on the L1 engineering client.

The client-facing contract therefore remains evidence-oriented.

This provides an **anti-corruption boundary** between the generic Diversity Mapper and the evidence domain.

The intended dependency direction is:

    Evidence Domain
         |
         v
    Evidence Adapter
         |
         v
    Generic Engine

and never:

    Generic Engine
         |
         v
    ReleaseGateService

The generic engine must not import or depend upon release-gating semantics.

This allows the Diversity Mapper implementation to evolve independently from the L1 automation architecture.

---

# 5. Core Data-Science Principle

The package distinguishes several kinds of diversity that are easily conflated:

1. lexical diversity;
2. syntactic diversity;
3. embedding-space diversity;
4. conceptual diversity.

Two artifacts may be lexically different while conceptually equivalent.

Conversely, two artifacts may use similar vocabulary while exercising meaningfully different behaviors.

For that reason, raw text embeddings are not treated as the conceptual space itself.

Instead, artifacts are mapped into explicit, interpretable **concept dimensions**.

Conceptual diversity is then evaluated primarily in that representation.

Embeddings, clustering, dimensionality reduction, density estimation, graph methods, or other statistical techniques may subsequently help analyze that conceptual representation, but they do not define conceptual diversity by themselves.

---

# 6. Concept Schemas

The central data-science abstraction is `ConceptSchema`.

A Concept Schema defines the conceptual dimensions against which artifacts are evaluated.

A schema contains multiple `ConceptDimension` objects.

Each dimension contains:

- a stable ID;
- a human-readable name;
- a definition;
- a rationale;
- a dimension type;
- possible values or numeric bounds where applicable;
- examples;
- counterexamples;
- provenance;
- derivation method;
- maturity confidence.

Supported dimension types include:

- Boolean;
- categorical;
- ordinal;
- continuous;
- multi-label.

For example, an initial evidence schema might include:

    Behavior Type
        normal
        boundary
        invalid input
        error handling
        dependency failure

    Authorization
        true / false

    Temporal Behavior
        true / false

    Concurrency
        true / false

    Invariant Preservation
        true / false

    Neighbor Interaction
        true / false

These dimensions are **not universal dimensions of software evidence**.

They represent an initial schema suitable for a POC and must remain versioned and empirically revisable.

---

# 7. Schema Discovery Is a Data-Science Problem

Creating the Concept Schema is one of the most important and difficult parts of the methodology.

The mapper should not assume that a human team already knows an exhaustive list of conceptual dimensions.

Candidate dimensions may be derived from several sources:

- domain experts;
- existing taxonomies;
- task specifications;
- known risk categories;
- observed failures;
- exploratory LLM analysis;
- empirical clustering;
- literature;
- existing datasets;
- combinations of these methods.

The code records the derivation method explicitly through `DerivationMethod`.

Supported provenance categories include:

    HUMAN_DEFINED
    EXISTING_TAXONOMY
    TASK_SPECIFICATION
    LLM_DISCOVERED
    EMPIRICAL_CLUSTER
    OBSERVED_FAILURE
    KNOWN_RISK_CATEGORY
    HYBRID

The recommended process is **hybrid** rather than relying entirely on either humans or an LLM.

---

# 8. Recommended Concept-Schema Development Workflow

A production schema should normally be developed iteratively.

## Step 1: Define the Artifact Archetype

Identify what kind of objects are being compared.

Examples include:

- toxic prompts;
- code repositories;
- software tests;
- evidence artifacts;
- business workflows;
- QA pairs;
- compliance examples;
- plans;
- strategies.

The conceptual dimensions should describe meaningful variation **within that archetype**.

## Step 2: Sample the Existing Population

Select a representative sample from the current artifact population.

The sample should intentionally include:

- common cases;
- unusual cases;
- known failures;
- known edge cases;
- artifacts from different sources;
- artifacts produced by different methods;
- artifacts from different time periods where relevant.

Schema discovery performed on an unrepresentative sample can produce an apparently coherent but incomplete conceptual model.

## Step 3: Obtain Candidate Dimensions

Candidate dimensions can be proposed independently through multiple mechanisms.

For example:

    Domain Experts
          |
          +----------------+
                           |
    Existing Taxonomies   |
          |                |
          +-------> Candidate Dimension Pool
          |                |
    LLM Discovery         |
          |                |
          +----------------+
                           |
    Empirical Analysis ---+

An LLM can be particularly useful for proposing candidate dimensions because the task involves abstraction across many examples.

However, LLM-generated dimensions should be treated as **hypotheses**, not automatically as ground truth.

## Step 4: Normalize and Consolidate Dimensions

Candidate dimensions may overlap.

For example:

    error behavior
    exception handling
    failure handling
    degraded execution

may partly describe the same conceptual axis.

Dimensions should therefore be reviewed for:

- semantic duplication;
- excessive correlation;
- ambiguous definitions;
- hierarchical relationships;
- unnecessary granularity;
- missing distinctions.

## Step 5: Define Operational Semantics

Every retained dimension should receive:

- a definition;
- inclusion criteria;
- exclusion criteria;
- examples;
- counterexamples;
- allowable values;
- expected mapping behavior;
- uncertainty behavior.

A dimension that cannot be mapped consistently is not yet operationally useful merely because its name sounds meaningful.

## Step 6: Map a Validation Sample

A separate sample should then be mapped into the candidate schema.

This tests whether the dimensions can actually distinguish artifacts in practice.

Important questions include:

- Are most artifacts mappable?
- Are many dimensions almost always UNKNOWN?
- Are dimensions highly redundant?
- Do different mapping methods agree?
- Do humans agree on ambiguous examples?
- Do dimensions correspond to meaningful downstream differences?

## Step 7: Revise the Schema

Dimensions may be:

- added;
- removed;
- split;
- merged;
- renamed;
- redefined;
- converted to another type.

Schema evolution must create a new schema version rather than silently changing historical semantics.

---

# 9. Versioning and Reproducibility

Concept schemas are first-class versioned objects.

Every `ConceptMapping`, `CoverageAssessment`, `CoverageGap`, and `ExpansionRequest` records the schema identity under which it was produced.

Historical results should therefore remain interpretable even after the schema evolves.

Reproducibility metadata should include, where applicable:

- schema ID;
- schema version;
- mapper version;
- model version;
- tool version;
- configuration hash;
- provenance;
- generation method;
- timestamps.

A result should not simply state:

    coverage = 72%

without identifying what conceptual schema and mapper configuration produced that result.

---

# 10. Artifact Mapping

After a schema exists, every artifact is mapped against its dimensions.

The core abstraction is:

    Artifact
       |
       v
    Concept Mapper
       |
       v
    ConceptMapping

A `ConceptMapping` contains one `DimensionMapping` per schema dimension.

Each dimension mapping records:

- dimension ID;
- status;
- value;
- confidence;
- method;
- rationale;
- uncertainty reason where applicable.

Mapping states include:

    MAPPED
    UNKNOWN
    UNRESOLVED
    UNSUPPORTED

UNKNOWN is an important first-class state.

Missing information must not silently become:

- false;
- zero;
- absent;
- normal;
- safe.

UNRESOLVED represents a different situation: relevant information exists, but the available methods disagree or remain ambiguous.

---

# 11. Mapping Strategies

The architecture intentionally separates mapping from coverage analysis.

Different mapping implementations can therefore be substituted without changing the coverage engine.

Possible mapping strategies include:

- deterministic rules;
- human annotations;
- classifiers;
- static analysis;
- AST analysis;
- graph analysis;
- embedding-based classifiers;
- LLM classification;
- multi-model adjudication;
- hybrid methods.

The reference implementation includes a fully operational:

    RuleBasedArtifactConceptMapper

This provides a deterministic mapping mechanism suitable for:

- unit tests;
- integration tests;
- early POCs;
- test doubles;
- explicitly structured evidence.

An `LLMArtifactConceptMapper` interface is also defined, but it deliberately raises `NotImplementedError` because production implementation requires organization-specific information such as:

- approved model provider;
- endpoint;
- authentication;
- deployment;
- schema-constrained output mechanism;
- timeout;
- retry policy;
- token limits;
- logging requirements;
- data-retention requirements.

Unknown production infrastructure is not represented through fake parameters or hidden placeholders.

---

# 12. Why Deterministic Mapping Comes First

For the initial POC, deterministic mapping is recommended before introducing LLM-based semantic mapping.

This establishes the correctness of:

- contracts;
- schemas;
- lineage handling;
- coverage calculations;
- gap generation;
- resource budgets;
- expansion requests;
- closed-loop verification.

Once these mechanics are independently testable, semantic mapping can be introduced as a replaceable component.

This sequencing helps distinguish two very different failure modes:

    Mapping Failure

from:

    Coverage Failure

Without this separation, poor model classification could incorrectly appear to be poor dataset coverage.

---

# 13. Coverage Mapping

Once artifacts have been mapped, the engine estimates how well the artifact collection represents the conceptual space.

The reference implementation begins with **dimension/value support analysis**.

For example:

    Behavior Type

        normal               -> 42 artifacts
        boundary              -> 5 artifacts
        invalid_input         -> 2 artifacts
        error_handling        -> 0 artifacts
        dependency_failure    -> 1 artifact

This representation is intentionally simple and interpretable.

Regions are classified as:

    REPRESENTED
    SPARSE
    ABSENT
    HIGHLY_REPEATED
    UNCERTAIN

A `CoverageRegion` records:

- conceptual coordinates;
- supporting artifact IDs;
- raw support count;
- lineage-aware support count;
- mean mapping confidence;
- conceptual duplicate count;
- region status;
- rationale.

---

# 14. Coverage Is Not Merely Clustering

Clustering can be useful, but clustering is not the definition of conceptual coverage.

A cluster identifies statistical structure under:

- a representation;
- a distance metric;
- an algorithm;
- hyperparameters.

It does not automatically establish that the cluster corresponds to a meaningful conceptual archetype.

Therefore:

    cluster != concept

and:

    embedding distance != conceptual difference

The preferred workflow is:

    Interpretable Concept Schema
              |
              v
       Artifact Mapping
              |
              v
      Conceptual Coordinates
              |
              v
    Coverage / Density Analysis

Clustering may then be used as an exploratory or complementary technique.

---

# 15. Higher-Order Concept Interactions

The reference implementation begins with independent dimension/value coverage because it is easy to inspect and validate.

However, many important gaps exist in **interactions between dimensions**.

For example, a dataset may separately contain:

    authorization examples

and:

    dependency-failure examples

while containing no examples of:

    authorization failure
            +
    dependency failure

Likewise, it may contain:

    concurrency tests

and:

    boundary tests

without testing:

    concurrency
        +
    boundary condition

Future coverage methods should therefore support:

- pairwise interaction coverage;
- higher-order interaction coverage;
- combinatorial coverage;
- graph-based concept interactions;
- conditional coverage;
- density estimation in conceptual space.

These methods should extend the existing `CoverageEngine` contract rather than requiring changes to the client-facing evidence API.

---

# 16. Dimensionality and the Curse of Dimensionality

Conceptual spaces can become large rapidly.

Suppose a schema contains 20 Boolean dimensions.

The theoretical joint space contains:

    2^20 = 1,048,576

possible combinations.

Attempting exhaustive coverage is therefore neither practical nor necessarily meaningful.

The data-science objective should not be:

> Fill every mathematically possible cell.

Instead, the objective should be:

> Identify meaningful conceptual regions whose absence matters for the intended use.

Possible approaches include:

- marginal coverage;
- pairwise coverage;
- selected higher-order interactions;
- hierarchical schemas;
- density estimation;
- graph neighborhoods;
- risk-weighted regions;
- empirically observed combinations;
- domain-constrained combinations.

The package should therefore treat coverage as a family of estimators rather than assuming one universal coverage statistic.

---

# 17. Sparse and Absent Regions

A sparse region contains some support but less support than expected.

An absent region contains no observed support.

These situations are not automatically equivalent to defects.

An absent region may be:

- genuinely missing;
- impossible;
- irrelevant;
- unsupported by the available sample;
- produced by an immature schema dimension.

For this reason, `CoverageGap` includes:

- support;
- uncertainty;
- priority;
- provenance;
- rationale.

A gap should remain inspectable rather than becoming an unexplained numeric score.

---

# 18. Mapping Uncertainty

Coverage estimates are only as reliable as the artifact mappings underneath them.

The mapper therefore propagates uncertainty explicitly.

For example:

    Artifact A
        concurrency = true
        confidence = 0.97

is different from:

    Artifact B
        concurrency = true
        confidence = 0.54

and both are different from:

    Artifact C
        concurrency = UNKNOWN

A region with many uncertain mappings may be classified as `UNCERTAIN` rather than confidently represented.

This prevents the system from converting model uncertainty into false coverage confidence.

---

# 19. Provenance and Lineage

Lineage is essential when artifacts are generated or transformed automatically.

Consider:

    Original Test
        |
        +---- Generated Variant A
        |
        +---- Generated Variant B
        |
        +---- Generated Variant C

Counting all four artifacts as four independent conceptual observations may exaggerate coverage.

`ArtifactLineage` therefore records information such as:

- parent artifact IDs;
- generation batch;
- generator identity;
- model identity;
- prompt-template identity;
- source method;
- transformation history.

The coverage engine reports both:

    raw artifact count

and:

    lineage-aware count

This distinction is particularly important for synthetic datasets.

---

# 20. Exact Versus Conceptual Duplication

The package distinguishes:

    exact duplication

from:

    conceptual duplication

Exact duplication is detected using stable content hashes.

Conceptual duplication is determined from normalized conceptual mappings.

For example, these two tests might contain different code:

    test_boundary_request_with_empty_header()

    test_empty_header_boundary_case()

but map to the same conceptual signature.

Lexical difference therefore does not automatically increase conceptual coverage.

The same principle applies to generated prompts, QA examples, workflows, strategies, and plans.

---

# 21. Targeted Expansion

After coverage gaps are identified, the mapper can translate selected gaps into structured `ExpansionRequest` objects.

An expansion request describes:

- which conceptual characteristic is needed;
- which gap motivated the request;
- its priority;
- how many additional artifacts may be requested;
- provenance;
- rationale.

Conceptually:

    CoverageGap
        |
        v
    ExpansionRequest

The mapper deliberately does not determine **how** the missing artifact should be produced.

In the evidence application:

    EvidenceExpansionRequest
            |
            v
       EvidencePlanner
            |
      +-----+------+------+
      |            |      |
    Tests       Static   Mutation
                Analysis  Analysis

This keeps measurement separate from acquisition.

---

# 22. Resource Budgets

Expansion must be constrained.

`ResourceBudget` allows callers to specify limits such as:

- maximum additional artifacts;
- maximum model calls;
- token budget;
- execution budget;
- elapsed-time budget;
- priority dimensions.

The expansion planner uses these constraints when selecting gaps.

This is important because conceptual coverage is generally an optimization problem under finite resources.

The practical objective is not:

> Maximize coverage without constraint.

It is closer to:

> Obtain the greatest useful increase in conceptual coverage under an acceptable acquisition cost.

---

# 23. Closed-Loop Expansion Verification

One of the most important properties of the architecture is that requested artifacts are **re-mapped after generation or collection**.

The system does not assume:

    "I asked the LLM for a concurrency example"

therefore:

    "I received a concurrency example."

Instead:

    Sparse Region
         |
         v
    Expansion Request
         |
         v
    External Generator
         |
         v
      New Artifact
         |
         v
    Independent Re-Mapping
         |
         v
    Coverage Verification

The new artifact is accepted as satisfying the request only if its independent mapping supports the requested conceptual characteristics.

Possible results include:

    SATISFIED_REQUEST
    PARTIALLY_SATISFIED
    DID_NOT_SATISFY
    UNRESOLVED

This closed loop is essential for synthetic-data generation because generator intent is not evidence of generator success.

---

# 24. Why the Closed Loop Improves on One-Shot Expansion

A weaker expansion architecture might perform:

    Sparse Region
         |
         v
    Ask LLM for More Examples
         |
         v
       Append Data

This can increase dataset size without meaningfully increasing conceptual coverage.

Generated examples may:

- repeat existing concepts;
- paraphrase existing artifacts;
- miss the requested conceptual target;
- collapse toward common patterns;
- introduce only lexical variation.

The improved workflow is:

    Sparse Region
         |
         v
    Infer Conceptual Signature
         |
         v
    Generate Candidate Artifacts
         |
         v
    Re-Extract Attributes
         |
         v
    Re-Map Concepts
         |
         v
    Re-Score Novelty and Coverage
         |
         v
    Reject Conceptual Duplicates
         |
         v
    Keep Only Coverage-Expanding Artifacts

This turns generation into a measured search process rather than an unconditional append operation.

---

# 25. Evidence-Specific Adapter

The evidence adapter converts `EvidenceArtifact` into the generic `ArtifactDescriptor`.

Evidence-specific information includes:

- candidate change ID;
- evidence type;
- observation;
- addressed claims;
- addressed behaviors;
- method;
- producer identity;
- result;
- confidence;
- provenance;
- parent evidence;
- generation batch;
- model identity;
- prompt-template identity;
- transformation history.

The adapter can also accept explicit `concept_hints` from deterministic evidence collectors.

For example:

    concept_hints = {
        "behavior_type": "boundary",
        "authorization": False,
        "temporal_behavior": False,
        "concurrency": False
    }

These hints enable deterministic POC integration.

They do not prevent a later semantic mapper from independently inferring concepts from richer evidence.

---

# 26. Data-Science Extension Points

The architecture intentionally allows the baseline coverage implementation to be replaced or augmented.

Important extension areas include:

### 26.1 LLM-Based Attribute Extraction

An LLM can map unstructured artifacts into structured Concept Schema dimensions.

This is especially useful where deterministic metadata is unavailable.

Such mapping should use:

- schema-constrained output;
- explicit UNKNOWN states;
- confidence or uncertainty estimation;
- validation against human annotations;
- versioned prompts;
- versioned model identifiers.

### 26.2 Embedding-Based Analysis

Embeddings can support:

- exploratory clustering;
- near-duplicate detection;
- outlier detection;
- local-neighborhood analysis;
- candidate novelty analysis.

Embeddings should normally complement rather than replace the interpretable Concept Schema.

### 26.3 Density Estimation

Conceptual coordinates can be analyzed for sparse regions using methods such as:

- nearest-neighbor distances;
- kernel density estimation;
- local outlier measures;
- clustering;
- graph density.

The appropriate method depends strongly on:

- dimension types;
- sample size;
- dimensionality;
- sparsity;
- whether dimensions are independent;
- whether the conceptual space contains meaningful geometry.

### 26.4 Interaction Coverage

Future engines can analyze:

- pairwise combinations;
- selected higher-order combinations;
- conditional combinations;
- risk-weighted combinations.

### 26.5 Graph-Based Coverage

Some conceptual domains are better represented as graphs than flat vectors.

For example:

    authentication
          |
          v
    authorization
          |
          v
    resource access

or:

    input validation
          |
          v
    parsing
          |
          v
    state mutation

Graph representations may capture relationships such as:

- causality;
- prerequisite;
- dependency;
- temporal ordering;
- containment;
- interaction.

The generic architecture should allow such representations without forcing the client-facing evidence contract to change.

---

# 27. Engineering Extension Points

The software architecture also separates several independently replaceable components.

## ArtifactConceptMapperPort

Responsible for:

    ArtifactDescriptor
        ->
    ConceptMapping

Implementations may use rules, LLMs, classifiers, static analysis, or hybrid methods.

## CoverageEngine

Responsible for:

    ConceptMappings
        ->
    CoverageAssessment

Alternative implementations can introduce more sophisticated density or interaction methods.

## ExpansionPlanner

Responsible for:

    CoverageGaps
        ->
    ExpansionRequests

Alternative implementations can perform cost-sensitive or optimization-based selection.

## ConceptDiscoveryPort

Responsible for:

    Artifact Population
        ->
    Candidate ConceptDimensions

Production LLM-based concept discovery remains an explicit integration point.

## EvidenceDiversityMapperAdapter

Responsible for maintaining the client-facing evidence contract while translating to and from the generic engine.

---

# 28. Error Semantics

Operational failures must never silently become statements about conceptual diversity.

For example:

    model timeout

must not become:

    no concurrency coverage

The architecture therefore distinguishes failures such as:

    MAPPER_UNAVAILABLE
    MODEL_UNAVAILABLE
    MALFORMED_MODEL_OUTPUT
    UNSUPPORTED_ARTIFACT
    INVALID_SCHEMA
    INSUFFICIENT_INFORMATION
    PARTIAL_MAPPING

Likewise, mapping states distinguish:

    UNKNOWN

from:

    false

and:

    UNRESOLVED

from:

    absent.

This distinction is critical when downstream systems consume mapper outputs.

---

# 29. Observability

The mapper maintains operational metrics including:

- artifacts processed;
- model calls;
- input tokens;
- output tokens;
- mapping failures;
- unresolved mappings;
- expansion requests;
- expansion candidates assessed;
- expansion candidates accepted;
- mapping latency;
- schema version.

One particularly useful metric is:

    expansion_acceptance_rate

which measures how often requested expansion artifacts actually satisfy their conceptual targets after independent re-mapping.

Low acceptance may indicate:

- poor generator steering;
- ambiguous concept definitions;
- weak mapping quality;
- impossible requests;
- conceptual collapse.

---

# 30. Testing Strategy

Testing should occur at several layers.

## Unit Tests

Test individual components such as:

- schema validation;
- mapping rules;
- UNKNOWN handling;
- conflicting mappings;
- lineage traversal;
- duplicate detection;
- region classification;
- budget enforcement;
- expansion assessment.

## Contract Tests

Verify that alternative implementations of:

    ArtifactConceptMapperPort

produce valid `ConceptMapping` objects.

Similarly, alternative coverage engines should preserve the required `CoverageAssessment` semantics.

## Integration Tests

Exercise:

    EvidenceArtifact
         |
         v
    EvidenceDiversityMapperAdapter
         |
         v
    GenericDiversityEngine
         |
         v
    EvidenceCoverageResult

without requiring live external models.

## Closed-Loop Tests

Test:

    initial coverage
         ->
    expansion request
         ->
    candidate artifact
         ->
    re-mapping
         ->
    expansion assessment

## Empirical Validation

The most important tests are ultimately empirical.

For the L1 evidence application, the question is not merely whether the mapper creates plausible clusters or attractive coverage visualizations.

The stronger question is whether mapper-guided evidence acquisition improves detection of hidden defects under comparable resource budgets.

---

# 31. Data-Science Validation

The Conceptual Diversity Mapper itself must be evaluated.

Important validation questions include:

### Schema Validity

Do the dimensions correspond to meaningful differences in the domain?

### Mapping Reliability

Do different annotators or mapping systems assign similar concepts to the same artifacts?

### Stability

Do small irrelevant changes to an artifact leave its conceptual mapping mostly unchanged?

### Sensitivity

Do meaningful conceptual changes alter the appropriate dimensions?

### Gap Validity

Do regions identified as sparse or absent correspond to genuine missing behavior?

### Expansion Effectiveness

Do targeted expansion requests actually produce artifacts in the requested regions?

### Downstream Utility

Does improved measured coverage produce better task outcomes?

For the L1 application, useful downstream outcomes may include:

- additional hidden faults discovered;
- reduction in false releases;
- improved mutation detection;
- broader behavioral evidence;
- improved detection of regressions.

---

# 32. The Critical Validation Experiment

A strong evaluation should compare:

    Mapper-Guided Evidence Acquisition

against:

    Unguided Evidence Acquisition

under approximately equal budgets.

For example:

    Strategy A
        Generate 20 additional tests normally.

    Strategy B
        Use the mapper to identify conceptual gaps,
        then acquire 20 tests targeted at those gaps.

The comparison should examine outcomes such as:

- unique faults discovered;
- mutation score improvement;
- behavioral coverage improvement;
- conceptual coverage improvement;
- redundant evidence rate;
- expansion acceptance rate;
- cost per newly covered conceptual region.

If mapper-guided acquisition does not outperform reasonable unguided baselines, the conceptual mapping may be scientifically interesting but operationally unjustified.

---

# 33. Avoiding Circular Validation

A major methodological risk is validating the mapper using only metrics produced by the mapper itself.

For example:

    Mapper identifies gaps.
    Mapper-guided generation fills gaps.
    Mapper reports higher coverage.

This alone does not prove that anything useful improved.

External validation signals are therefore necessary.

For software evidence these may include:

- hidden defects;
- seeded faults;
- mutation operators;
- independently authored tests;
- human expert review;
- historical production incidents;
- known vulnerability classes.

The strongest validation therefore links:

    Conceptual Coverage

to:

    Independent Task Outcomes

rather than merely to the mapper's own score.

---

# 34. Concept Drift and Schema Evolution

Conceptual schemas should be expected to evolve.

New artifact populations may reveal dimensions that were absent from the original sample.

New failure modes may appear.

New engineering architectures may create new behavioral interactions.

The system should therefore support:

    Schema v1
       |
       v
    Production Observations
       |
       v
    Newly Observed Concepts
       |
       v
    Schema Review
       |
       v
    Schema v2

Historical assessments remain associated with Schema v1.

New assessments can use Schema v2.

Schema evolution should be deliberate and versioned rather than silently modifying definitions.

---

# 35. When the Method Can Fail

The methodology can fail even when the software implementation is correct.

Important failure modes include:

- incomplete Concept Schemas;
- poorly defined dimensions;
- correlated or redundant dimensions;
- unreliable artifact mapping;
- over-reliance on LLM-generated taxonomies;
- sparse validation samples;
- false interpretation of statistical clusters as concepts;
- excessive dimensionality;
- treating impossible combinations as coverage gaps;
- synthetic-data lineage inflation;
- generator mode collapse;
- circular validation;
- failure to connect coverage with downstream outcomes.

The system therefore should not claim that a Concept Schema is exhaustive.

Coverage is always coverage **with respect to a particular versioned conceptual model**.

---

# 36. What the Mapper Does Not Prove

A high conceptual coverage score does not automatically prove:

- software correctness;
- software safety;
- release readiness;
- absence of vulnerabilities;
- absence of bias;
- dataset completeness;
- model robustness.

It means that, under a particular Concept Schema and mapping methodology, the observed artifact collection provides broader representation of the modeled conceptual space.

That distinction should remain explicit in downstream communication.

---

# 37. Recommended POC Sequence

The recommended implementation sequence is:

    1. Define EvidenceArtifact contract
                 |
                 v
    2. Create human-reviewed ConceptSchema v1
                 |
                 v
    3. Implement deterministic mapping
                 |
                 v
    4. Validate UNKNOWN semantics
                 |
                 v
    5. Implement lineage-aware coverage
                 |
                 v
    6. Produce structured CoverageGaps
                 |
                 v
    7. Add ResourceBudget
                 |
                 v
    8. Produce ExpansionRequests
                 |
                 v
    9. Re-map acquired evidence
                 |
                 v
    10. Verify gap reduction
                 |
                 v
    11. Build benchmark corpus
                 |
                 v
    12. Introduce semantic / LLM mapping
                 |
                 v
    13. Compare against deterministic baseline
                 |
                 v
    14. Add higher-order coverage methods
                 |
                 v
    15. Validate downstream engineering value

This sequence intentionally delays sophisticated modeling until the product contracts and evaluation methodology are stable.

---

# 38. Example Usage

A minimal deterministic POC can be created as follows:

    schema = build_example_evidence_schema()

    rules = build_example_evidence_mapping_rules()

    mapper = RuleBasedArtifactConceptMapper(
        rules=rules
    )

    engine = GenericDiversityEngine(
        concept_mapper=mapper
    )

    evidence_mapper = EvidenceDiversityMapperAdapter(
        engine=engine
    )

    bundle = build_example_evidence_bundle()

    budget = ResourceBudget(
        max_additional_artifacts=3,
        max_model_calls=3,
        token_budget=10000,
        execution_budget=10,
        elapsed_time_budget_seconds=60.0
    )

    result = evidence_mapper.assess_evidence_bundle(
        bundle=bundle,
        schema=schema,
        budget=budget
    )

The resulting `EvidenceCoverageResult` contains:

- artifact mappings;
- conceptual regions;
- mapping uncertainty;
- lineage-aware coverage;
- coverage gaps;
- prioritized expansion requests.

---

# 39. Expansion Example

After an external EvidencePlanner receives an `EvidenceExpansionRequest`, it may select an appropriate evidence collector.

For example:

    ExpansionRequest
          |
          v
    EvidencePlanner
          |
          v
    Generated Test
          |
          v
    EvidenceArtifact
          |
          v
    assess_generated_evidence()
          |
          v
    ExpansionAssessment

The returned assessment determines whether the collected evidence actually satisfies the conceptual request.

---

# 40. Production Integration Boundaries

The following components should remain outside this package:

    ReleaseGateService
    GatePolicy
    Code Generator
    Test Runner
    Mutation Runner
    Static Analyzer
    Compiler
    EvidencePlanner

The Diversity Mapper consumes outputs from these systems or provides structured requests to orchestration components.

It should not become the orchestration layer itself.

This keeps responsibilities clear and prevents conceptual coverage logic from becoming tightly coupled to a particular SDLC implementation.

---

# 41. Suggested Package Structure

As the reference implementation grows, the single-file prototype can be separated into modules:

    conceptual_diversity_mapper/
    |
    +-- schemas/
    |   +-- concepts.py
    |   +-- validation.py
    |
    +-- artifacts/
    |   +-- descriptors.py
    |   +-- lineage.py
    |
    +-- mapping/
    |   +-- ports.py
    |   +-- rule_based.py
    |   +-- llm_mapper.py
    |
    +-- coverage/
    |   +-- regions.py
    |   +-- engine.py
    |   +-- duplicates.py
    |
    +-- expansion/
    |   +-- requests.py
    |   +-- planner.py
    |   +-- verification.py
    |
    +-- discovery/
    |   +-- ports.py
    |   +-- llm_discovery.py
    |
    +-- observability/
    |   +-- metrics.py
    |
    +-- domains/
    |   +-- evidence/
    |       +-- contracts.py
    |       +-- adapter.py
    |       +-- schema.py
    |
    +-- tests/
    |   +-- unit/
    |   +-- contract/
    |   +-- integration/
    |   +-- empirical/
    |
    +-- __init__.py

The single-file implementation is useful for initial review and experimentation.

Modularization should occur when multiple contributors begin independently changing components.

---

# 42. Engineering Requirements for Productionization

Before production deployment, engineering work should address:

- API serialization contracts;
- schema registry/storage;
- persistence of assessments;
- model-client integration;
- retry behavior;
- timeout handling;
- structured logging;
- tracing;
- authentication;
- authorization;
- secrets management;
- data classification;
- redaction;
- rate limiting;
- concurrency;
- caching;
- deterministic replay where feasible;
- deployment configuration;
- monitoring;
- alerting;
- backward compatibility.

These concerns should be implemented around the existing ports rather than embedded into conceptual coverage algorithms.

---

# 43. Data-Science Requirements for Productionization

Before relying on mapper outputs operationally, the data-science work should establish:

- Concept Schema validity;
- annotation guidance;
- human agreement baselines;
- mapping precision and recall where measurable;
- uncertainty calibration;
- schema stability;
- duplicate-detection validity;
- gap-detection validity;
- expansion success rate;
- sensitivity to dataset size;
- robustness to lexical perturbation;
- robustness to generator identity;
- performance on known failure cases;
- comparison with embedding-only baselines;
- comparison with random expansion;
- comparison with unguided LLM generation;
- downstream utility.

The product should therefore be treated as both:

    a software system

and:

    a measurement system.

Engineering correctness alone does not establish measurement validity.

---

# 44. Relationship Between Engineering and Data Science

The engineering and data-science components should remain separable but tightly tested against each other.

Engineering provides:

    stable contracts
    versioning
    lineage
    persistence
    reproducibility
    adapters
    orchestration boundaries
    failure handling
    observability

Data science provides:

    conceptual representations
    mapping methods
    uncertainty estimation
    coverage estimators
    density methods
    duplicate criteria
    gap prioritization
    schema discovery
    empirical validation

Neither side is sufficient by itself.

A sophisticated coverage algorithm without reproducible schemas and provenance is difficult to operate safely.

A perfectly engineered API around an invalid Concept Schema produces reliable infrastructure for an unreliable measurement.

---

# 45. Recommended Ownership Model

A practical ownership split is:

## Diversity Mapper Product Team

Own:

- generic contracts;
- generic mapping interfaces;
- coverage engines;
- expansion contracts;
- lineage;
- duplication;
- uncertainty representation;
- schema versioning mechanics;
- observability;
- reusable validation tooling.

## Evidence-Domain Team

Own or co-own:

- EvidenceArtifact semantics;
- evidence-specific Concept Schema;
- evidence mapping validation;
- domain-specific benchmark data;
- interpretation of evidence gaps.

## L1 Automation Team

Own:

- EvidencePlanner;
- evidence collector selection;
- execution;
- orchestration;
- ReleaseGateService;
- release policy.

This keeps the generic mapper reusable without forcing domain experts to surrender control of domain semantics.

---

# 46. Initial Success Criteria

The first POC should demonstrate that the system can:

1. ingest a representative `EvidenceBundle`;
2. map artifacts into a versioned Concept Schema;
3. preserve explicit UNKNOWN states;
4. record mapping uncertainty;
5. detect exact duplicates;
6. detect conceptual duplicates;
7. preserve artifact lineage;
8. report raw and lineage-aware support;
9. identify represented, sparse, absent, repeated, and uncertain regions;
10. produce machine-readable `CoverageGap` objects;
11. respect caller-supplied resource budgets;
12. produce structured `EvidenceExpansionRequest` objects;
13. accept newly collected evidence;
14. independently re-map that evidence;
15. determine whether the requested conceptual gap was actually addressed;
16. expose reproducibility and operational metrics;
17. perform all of the above without coupling the mapper to release decisions.

These criteria test the architecture before requiring proof of broader operational value.

---

# 47. Longer-Term Success Criteria

After the POC, success should increasingly be judged by empirical outcomes.

For the L1 evidence application, the strongest target is:

> Under comparable evidence-acquisition budgets, mapper-guided acquisition discovers more relevant hidden failures, produces less redundant evidence, or reduces incorrect release decisions relative to reasonable unguided baselines.

For other domains, equivalent external outcome measures should be defined.

For example:

    Toxicity Dataset
        -> broader independently validated failure coverage

    Golden QA
        -> better downstream evaluation discrimination

    Compliance Examples
        -> improved judge performance on held-out cases

    Workflow Library
        -> broader strategy coverage and improved solution discovery

    Codebase Library
        -> broader structural / behavioral / vulnerability representation

This is the ultimate test of whether conceptual diversity mapping provides practical value.

---

# 48. Current Limitations

The reference implementation deliberately starts conservatively.

Current limitations include:

- the example Concept Schema is not exhaustive;
- coverage currently emphasizes individual dimensions rather than complex interactions;
- the deterministic mapper depends on explicit artifact metadata;
- production LLM mapping is not configured;
- production LLM concept discovery is not configured;
- no external persistence layer is included;
- no organization-specific model client is included;
- no release-gating logic is included;
- no evidence execution engine is included;
- continuous-space coverage uses simple bucketing;
- conceptual duplicate detection currently uses identical normalized conceptual signatures;
- gap priority uses a transparent heuristic rather than a learned utility model.

These are explicit extension points rather than hidden assumptions.

Where runtime or organization-specific information is genuinely unknown, the corresponding integration raises `NotImplementedError`.

---

# 49. Important Scientific Uncertainties

Several aspects of conceptual diversity measurement remain research and validation questions rather than settled engineering facts.

There may not be a single objectively correct Concept Schema for a domain.

Different schemas may capture different useful abstractions.

Concept dimensions may also interact in nonlinear or hierarchical ways that simple vector representations fail to capture.

Mapping uncertainty may be difficult to calibrate, particularly when LLMs perform attribute extraction.

Sparse regions are not necessarily important regions.

Conceptual novelty is not automatically equivalent to operational value.

High conceptual coverage is not automatically equivalent to completeness.

For these reasons, the mapper should expose its assumptions and provenance rather than presenting a coverage score as an absolute property of a dataset.

---

# 50. Design Philosophy

The system is built around five principles.

## 1. Concepts Before Surface Variation

Lexical or syntactic diversity is not sufficient evidence of conceptual diversity.

## 2. Measurement Before Generation

Understand the existing conceptual space before requesting additional artifacts.

## 3. Generation Is a Hypothesis

A generated artifact does not cover a requested concept until independent re-mapping confirms that it does.

## 4. Uncertainty Must Remain Visible

UNKNOWN, disagreement, low confidence, lineage, and schema maturity must not disappear inside aggregate scores.

## 5. Validate Against External Outcomes

The mapper should ultimately be judged by whether its notion of conceptual coverage improves the real task for which the artifact collection exists.

---

# 51. Summary

The Conceptual Diversity Mapper is designed as a reusable **measurement and targeted-expansion system** rather than a generic clustering utility or synthetic-data generator.

Its fundamental abstraction is:

    Artifacts
        +
    Versioned Concept Schema
        |
        v
    Interpretable Concept Mapping
        |
        v
    Coverage Measurement
        |
        v
    Explicit Coverage Gaps
        |
        v
    Budget-Constrained Expansion Requests
        |
        v
    External Acquisition
        |
        v
    Independent Re-Mapping
        |
        v
    Verified Coverage Improvement

For the initial L1 engineering application, this generic machinery is hidden behind an evidence-specific adapter.

This provides a deliberate balance:

> **Generic underneath, domain-specific at the boundary.**

The engineering architecture makes the mapper reusable.

The data-science methodology makes the representation meaningful.

The closed-loop expansion process makes generated diversity measurable.

The empirical validation framework determines whether that measured diversity actually improves downstream outcomes.
