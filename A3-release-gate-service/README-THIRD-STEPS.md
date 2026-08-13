# Deterministic ReleaseGateService

## Purpose

This package implements the first authoritative release gate for the AI
engineering platform.

It independently reconstructs a candidate patch and produces:

- authoritative deterministic control results;
- normalized metrics;
- an immutable evidence package;
- a deterministic release recommendation;
- an auditable gate trace.

The possible recommendations are:

- `PASS`
- `FAIL`
- `HUMAN_REVIEW_REQUIRED`
- `MORE_EVIDENCE_REQUIRED`

## What this component proves

Before adding AI to release assurance, the platform must demonstrate that it can:

1. Validate immutable gate inputs.
2. Reconstruct a candidate from the exact base commit.
3. Enforce authorized file scope.
4. Execute deterministic controls in a clean workspace.
5. Parse structured reports.
6. Normalize evidence without metric collisions.
7. Apply a versioned policy deterministically.
8. Preserve the evidence underlying the decision.
9. Keep human activity outside the release gate.
10. Return zero LLM token usage honestly.

## Architectural boundary

The executor produces software.

The release gate produces evidence and a recommendation.

The release gate does not:

- generate the candidate;
- trust executor-local tests;
- merge code;
- deploy code;
- access hidden benchmark oracles;
- perform human review;
- use an LLM in Component 3.

## Clean-room reconstruction

Component 2 creates a candidate commit in a disposable local clone and exports a
normalized patch.

Component 3 receives:

- `GateRequest`;
- `ExecutionResult`;
- the candidate patch bytes.

The gate:

1. Verifies the patch SHA-256.
2. Verifies patch metadata against base and candidate commit IDs.
3. Clones the repository independently.
4. Checks out the exact base commit.
5. Validates the patch before applying it.
6. Applies and stages the patch.
7. Calculates a Git tree identifier.
8. Runs authoritative controls.

The reconstructed Git tree is included in the evidence package and GateResult
metadata.

## Installation

Install Component 1 first:

```bash
cd shared-contracts
python -m pip install -e ".[dev]"
```

Then install Component 3:

```bash
cd ../release-gate-service
python -m pip install -e ".[dev]"
```

The target repository must also contain the tools referenced by its evaluation
specification. For the supplied Python example:

```bash
python -m pip install pytest coverage
```

## Run the tests

```bash
ruff check .
mypy src
pytest
```

## Run the gate

```bash
release-gate \
  --gate-request examples/gate-request.json \
  --candidate-patch artifacts/candidate.patch \
  --candidate-patch-metadata artifacts/execution-result.json \
  --config config/gate.local.yaml \
  --output gate-artifacts/gate-result.json
```

Exit codes:

| Exit code | Meaning |
|---|---|
| 0 | PASS |
| 2 | HUMAN_REVIEW_REQUIRED |
| 3 | MORE_EVIDENCE_REQUIRED |
| 4 | FAIL |
| 1 | Input, configuration, or unrecoverable execution error |

## Evaluation specification

The evaluation specification answers:

> What controls should run, and what evidence should they produce?

Each control declares:

* identifier;
* executable and arguments;
* timeout;
* working directory;
* environment;
* severity;
* evidence strategy;
* expected exit codes;
* structured reports;
* whether later controls should continue after failure.

Commands are never executed through a shell.

## Release policy

The release policy answers:

> How should authoritative evidence become a recommendation?

The policy handles:

* mandatory failures;
* dominant failures;
* advisory failures;
* warnings;
* skipped mandatory controls;
* missing metrics;
* numeric thresholds.

Decision precedence is fixed:

```text
FAIL
  >
HUMAN_REVIEW_REQUIRED
  >
MORE_EVIDENCE_REQUIRED
  >
PASS
```

This order prevents a lower-severity condition from hiding a more serious
failure.

## Control severity

### Informational

Recorded for evidence and reporting. It does not independently alter the gate
decision.

### Advisory

A failure normally produces HUMAN_REVIEW_REQUIRED.

### Mandatory

A failure normally produces FAIL.

### Dominant failure

A failure always overrides lower-priority evidence and produces FAIL under the
default policy.

Examples include:

* candidate integrity failure;
* unauthorized file changes;
* detected credentials;
* prohibited dependency introduction;
* severe security-policy violation.

## Structured evidence reports

Component 3 supports:

### JUnit XML

Extracted metrics include:

* tests_total
* tests_passed
* tests_failures
* tests_errors
* tests_skipped
* tests_time_seconds

### Coverage.py JSON

Extracted metrics include:

* coverage_percent
* statements_total
* statements_covered
* statements_missing
* branches_total
* branches_covered
* branches_missing

### Generic JSON metrics

A control can declare dotted JSON paths:

```yaml
metric_paths:
  mutation_score: "metrics.mutation_score"
  survived_mutants: "metrics.survived"
```

This permits future deterministic tools to integrate without changing the core
release-gate code.

## Metric namespacing

Metrics are normalized as:

```text
<control_id>.<metric_name>
```

Examples:

```text
pytest.tests_failures
coverage-json.coverage_percent
mutation.mutation_score
```

This prevents two controls from silently overwriting each other's metrics.

## Workspace-integrity rule

A gate control may create ignored temporary artifacts such as:

* coverage data;
* JUnit reports;
* caches;
* compiled output.

A gate control may not modify tracked candidate source or the staged candidate
tree.

Any such modification becomes an authoritative control error.

## Why AI is excluded from Component 3

The first gate should establish a trustworthy deterministic core before AI is
introduced.

AI will later be useful for:

* requirement interpretation;
* independent test synthesis;
* compiler-artifact interpretation;
* hypothesis generation;
* evidence-diversity mapping;
* mutation-targeted test generation;
* assurance planning.

AI should not be used to decide:

* whether a command ran;
* whether compilation succeeded;
* whether a test failed;
* whether a file changed;
* whether a report existed;
* whether a numeric threshold passed;
* what final deterministic decision policy requires.

## Current limitations

1. Artifact access is limited to `file://` URIs.
2. Candidate commits are reconstructed from patches rather than fetched from a
   controlled candidate repository.
3. Candidate commit metadata is checked, but Component 1 does not yet contain a
   first-class candidate-tree field.
4. Commands are operator-configured rather than selected through an enterprise
   tool registry.
5. The process environment is bounded, but this is not a complete sandbox.
6. There is no AI-generated evidence.
7. There is no mutation testing unless a deterministic external mutation tool is
   configured through a command and JSON report.
8. There is no evidence-diversity mapper.
9. There is no evidence-planning loop.
10. There is exactly one deterministic evidence round.
11. `preserve_successful_workspace` and `preserve_failed_workspace` are reserved
    configuration fields. The current implementation always uses disposable
    temporary workspaces and does not silently pretend otherwise.

## Azure deployment direction

The service is a finite command-line workload and can later run as an Azure
Container Apps Job.

The Azure version should replace local artifact access with:

* Azure Blob Storage;
* managed identity;
* Key Vault where required;
* private networking;
* restricted outbound access;
* Azure Container Registry;
* Application Insights operational telemetry.

The gate managed identity should be able to:

* read the base repository;
* read immutable candidate artifacts;
* write gate evidence.

It should not be able to:

* alter the candidate;
* merge code;
* deploy code;
* read hidden benchmark oracles.

## Next component

The next agreed implementation step is:

> Evidence storage and immutable run manifests.

Component 3 already writes local immutable evidence artifacts. The next step
should formalize the run-manifest package and prepare the storage abstraction for
Azure Blob Storage without changing the executor or gate public interfaces.

---

# Verification Commands

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest
```

# Resulting Workflow

```text
GateRequest
    +
ExecutionResult
    +
Immutable Candidate Patch
    │
    ▼
ReleaseGateService
    ├── validate artifact identity and digest
    ├── clone exact base commit
    ├── reconstruct candidate cleanly
    ├── calculate candidate Git tree
    ├── enforce authorized path scope
    ├── run authoritative deterministic controls
    ├── parse JUnit, coverage, and JSON evidence
    ├── normalize metrics
    ├── apply deterministic release policy
    └── preserve evidence and trace
    │
    ▼
GateResult
    ├── PASS
    ├── FAIL
    ├── HUMAN_REVIEW_REQUIRED
    └── MORE_EVIDENCE_REQUIRED
```

No class or function in this package is intentionally left unimplemented.

Unsupported functionality either:

* fails explicitly through a typed exception;
* produces an authoritative failed control;
* produces MORE_EVIDENCE_REQUIRED; or
* is documented as outside the current component's scope.
