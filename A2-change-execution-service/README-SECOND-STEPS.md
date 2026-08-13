# Deterministic ChangeExecutionService

## Purpose

This package implements the first executable version of
`ChangeExecutionService`.

It accepts:

1. A validated `TaskRunRequest`.
2. An immutable manually authored Git patch.
3. Executor configuration describing local feedback checks.

It produces:

1. A local candidate Git commit.
2. A normalized candidate patch.
3. Local check results.
4. A structured execution trace.
5. An immutable `ExecutionResult`.

This component does not use AI.

## Why begin with a manual patch?

The platform must prove that it can safely and reproducibly:

- validate input contracts;
- retrieve an immutable patch;
- clone the exact repository state;
- enforce file scope;
- run bounded commands;
- produce a candidate commit;
- preserve evidence;
- return structured failures.

Adding an LLM before these controls work would make it difficult to distinguish
agent failures from basic platform failures.

## Architectural boundary

The executor produces software.

It does not produce release authority.

Local checks may report that compilation and tests passed, but these results are
generated inside a workspace controlled by the executor. They are therefore
retained as claims and diagnostic feedback.

`ReleaseGateService` must later:

- clone the candidate commit independently;
- execute authoritative checks in a clean environment;
- generate additional evidence;
- apply release policy;
- emit PASS, FAIL, HUMAN_REVIEW_REQUIRED, or MORE_EVIDENCE_REQUIRED.

## Requirements

- Python 3.11 or newer
- Git
- The shared-contracts package from Component 1
- The build and test tools required by the target repository

## Installation

First install the shared contracts:

```bash
cd shared-contracts
python -m pip install -e ".[dev]"
```

Then install this component:

```bash
cd ../change-execution-service
python -m pip install -e ".[dev]"
```

## Run tests

```bash
ruff check .
mypy src
pytest
```

## Prepare a patch

From a clean repository checked out at the TaskRunRequest base commit:

```bash
git diff --binary --full-index > change.patch
```

The input patch should not include unrelated changes.

## Run the executor

```bash
change-executor \
  --task-request examples/task-request.json \
  --patch examples/change.patch \
  --config config/executor.local.yaml \
  --output artifacts/execution-result.json
```

Exit codes:

* 0: a candidate commit was produced;
* 2: the executor returned a structured non-success result;
* 1: CLI input or configuration could not be loaded.

## Local-check interpretation

A failed local check does not automatically prevent candidate creation.

This is intentional.

`ChangeExecutionService` is responsible for producing and documenting a
candidate. `ReleaseGateService` is responsible for applying authoritative
release policy.

A future task package may instruct an AI executor to use local failures as
feedback and repair its candidate before returning. That repair loop is not part
of this deterministic implementation.

## Scope enforcement

Each `TaskRunRequest` contains:

```json
{
  "permitted_paths": [
    "src/**/*.py",
    "tests/**/*.py"
  ],
  "prohibited_paths": [
    ".azure-pipelines/**",
    "infrastructure/**",
    "secrets/**"
  ]
}
```

Every changed path must match at least one permitted pattern and no prohibited
pattern.

Scope failure produces a structured failed `ExecutionResult`. No candidate
commit is emitted.

## Security properties

This POC includes the following controls:

* exact base-commit checkout;
* patch digest verification;
* `git apply --check` before application;
* no shell command execution;
* bounded command runtime;
* bounded captured output;
* deterministic tool-call budget;
* allow-listed process environment;
* repository-relative check working directories;
* tracked-file mutation detection after checks;
* no remote push or merge;
* immutable output artifacts;
* non-root Docker user.

These controls do not replace container, network, identity, and host security.

For production Azure deployment, add:

* managed identity;
* Key Vault;
* private networking;
* restricted outbound access;
* read-only base images;
* CPU and memory limits;
* Azure Blob artifact storage;
* centralized audit logging;
* malware and secret scanning;
* repository-specific command allow-lists.

## Azure deployment compatibility

The command-line application performs one finite execution and terminates. It
can therefore be packaged as a manually triggered Azure Container Apps Job.

The job should receive:

* a TaskRunRequest artifact location;
* a patch artifact location;
* a configuration artifact location;
* an output evidence location.

The local artifact implementation should be replaced with an Azure Blob
implementation satisfying the same load/store responsibilities.

## Known limitations

1. Only local `file://` patch artifacts are currently supported.
2. The repository may be local or accessible through Git using noninteractive
   credentials already present in the environment.
3. The executor does not push the candidate commit to a remote repository.
   The candidate patch artifact is the portable output.
4. The executor does not preserve a failed temporary workspace.
5. The configured commands are operator-approved rather than selected from a
   centrally managed tool registry.
6. There is no LLM, context retrieval, agent planning, editing, or repair loop.
7. Local checks are not release evidence.

Each limitation is explicit and fails safely. No intentionally unimplemented
method silently returns a placeholder result.

---

# Verification Commands

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest
```

# Design Result

After this component is installed, the platform has a complete deterministic
path:

```text
TaskRunRequest
    +
Immutable Manual Patch
    │
    ▼
ChangeExecutionService
    ├── verify patch digest
    ├── clone exact base commit
    ├── validate and apply patch
    ├── enforce file scope
    ├── run local feedback checks
    ├── create candidate commit
    ├── export normalized patch
    └── record execution evidence
    │
    ▼
ExecutionResult
    +
Candidate Patch Artifact
    +
Execution Trace
```

No function or class in this package is intentionally left unimplemented.

Unsupported functionality fails explicitly through a typed exception or a
structured failed `ExecutionResult`.
