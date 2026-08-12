# Index — where every original artifact went

This repository holds the artifacts from the `repo_diagram.txt` build flow, converted
from `.txt` into their proper formats. Use this file to find anything.

This document uses Simplified Technical English (ASD-STE100).

## The original build flow

```
A[1-12].txt + B[1-8].txt   --prompt_AB-------->  repo_0
repo_0                     --prompt_truncate-->  repo_demo_0
E1.txt + E2.txt            --prompt_E-------->   repo_evidence

repo_demo_0 + repo_evidence  --prompt_EBA-->     repo_demo_1
```

Source: [prompts/repo_diagram.txt](prompts/repo_diagram.txt)

## Artifact to location

| Original artifact | Component | Where it is now |
|---|---|---|
| `A1.txt` | 1 Shared Contracts | [A1-shared-contracts/](A1-shared-contracts/) |
| `A2.txt` | 2 Change Execution | [A2-change-execution-service/](A2-change-execution-service/) |
| `A3.txt` | 3 Release Gate | [A3-release-gate-service/](A3-release-gate-service/) |
| `A4.txt` | 4 Evidence Storage | [A4-evidence-storage/](A4-evidence-storage/) |
| `A5.txt` | 5 Pipeline Evaluation & Qualification | [A5-pipeline-evaluation/](A5-pipeline-evaluation/) |
| `A6.txt` | 6 Production Operational Observability | [A6-production-observability/](A6-production-observability/) |
| `A7.txt` | 7 Process Outcome & Business Measurement | [A7-process-outcomes/](A7-process-outcomes/) |
| `A8.txt` | 8 Engineering Productivity & Automation Economics | [A8-engineering-economics/](A8-engineering-economics/) |
| `A9.txt` | 9 Orchestrator / Control Plane | [A9-orchestrator/](A9-orchestrator/) |
| `A10.txt` | 10 Execution Environment & Sandbox | [A10-execution-environment/](A10-execution-environment/) |
| `A11.txt` | 11 Task Specification & Capability Registry | [A11-task-specification-registry/](A11-task-specification-registry/) |
| `A12.txt` | 12 Engineering Workflow Integration | [A12-workflow-integration/](A12-workflow-integration/) |
| `B1.txt` – `B8.txt` | blind-spot notes | **not received yet** |
| `E1.txt` | evidence diversity mapper | [E1-E2-conceptual-diversity-mapper/E1_evidence_diversity_mapper_reference.py](E1-E2-conceptual-diversity-mapper/E1_evidence_diversity_mapper_reference.py) |
| `E2.txt` | its README | [E1-E2-conceptual-diversity-mapper/README.md](E1-E2-conceptual-diversity-mapper/README.md) |
| `prompt_AB_.txt` | | [prompts/prompt_AB_.txt](prompts/prompt_AB_.txt) — **PARTIAL** |
| `prompt_truncate.txt` | | [prompts/prompt_truncate.txt](prompts/prompt_truncate.txt) — **PARTIAL** |
| `prompt_E.txt` | | [prompts/prompt_E.txt](prompts/prompt_E.txt) — complete |
| `prompt_EBA.txt` | | [prompts/prompt_EBA.txt](prompts/prompt_EBA.txt) — **PARTIAL** |
| `repo_diagram.txt` | | [prompts/repo_diagram.txt](prompts/repo_diagram.txt) — complete |

**Three prompts are incomplete.** They were transcribed from photographs that stopped
partway through the file. Each one carries a transcription note at the top and an end
marker where the photograph stopped. Replace them with the real files when you can.

### A10 came in two versions

Copilot produced `A10 (version x)` and `A10 (version y)`. Nobody knew which was newer.
They are the same text. Only one trailing blank line separates them. A third copy of the
same Component 10 document also arrived under the label `A12`, which was a mislabel. The
real Component 12 arrived later and is in `A12-workflow-integration/`.

Only one copy of A10 is stored.

## Python package names

The directory names carry the artifact ID. The Python package names inside do **not**,
because the components import each other by package name. Renaming the packages would
break the cross-component contract.

| Directory | Python package | Depends on |
|---|---|---|
| `A1-shared-contracts/` | `ai_engineering_contracts` | — |
| `A2-change-execution-service/` | `ai_engineering_change_executor` | A1 |
| `A3-release-gate-service/` | `ai_engineering_release_gate` | A1 |
| `A4-evidence-storage/` | `ai_engineering_evidence` | A1 |
| `A5-pipeline-evaluation/` | `ai_engineering_evaluation` | A1, A4 |
| `A6-production-observability/` | `ai_engineering_observability` | OpenTelemetry |
| `A7-process-outcomes/` | `ai_engineering_outcomes` | — |
| `A8-engineering-economics/` | `ai_engineering_economics` | — |
| `A9-orchestrator/` | `ai_engineering_orchestrator` | — |
| `A10-execution-environment/` | `execution_environment` | — |
| `A11-task-specification-registry/` | `task_specification_registry` | — |
| `A12-workflow-integration/` | `engineering_workflow_integration` | httpx |
| `E1-E2-conceptual-diversity-mapper/` | single module, not a package | — |

## Install order

A1 comes first. A4 comes before A5. The others are independent.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e A1-shared-contracts
for d in A2-change-execution-service A3-release-gate-service A4-evidence-storage \
         A5-pipeline-evaluation A6-production-observability A7-process-outcomes \
         A8-engineering-economics A9-orchestrator A10-execution-environment \
         A11-task-specification-registry A12-workflow-integration; do
  pip install -e "$d"
done
```

The E1/E2 mapper has no third-party dependency and needs no install. Run it directly:

```bash
python E1-E2-conceptual-diversity-mapper/E1_evidence_diversity_mapper_reference.py
```

## Current test status

| Component | Tests | Note |
|---|---|---|
| A1 | 10 / 10 pass in `test_contracts.py` | `test_schema_export.py` cannot import. Defect 1. |
| A2 | 2 / 7 pass | One root cause, one line. Defect 2. |
| A3 | 4 / 10 pass | Two root causes, two lines. Defects 3 and 4. |
| A4 | 9 / 9 pass | The recorder is never tested. Defect 5. |
| A5 | 10 / 10 pass | |
| A6 | 7 / 7 pass | Needs `opentelemetry-api` and `opentelemetry-sdk`. |
| A7 | 8 / 9 pass | Defect 6. |
| A8 | 8 / 8 pass | |
| A9 | 6 / 6 pass | `cli.py` is missing. Defect 7. |
| A10 | 5 / 6 pass | Defects 8 and 9. |
| A11 | 3 / 3 pass | Two declared test files are missing. |
| A12 | 6 / 6 pass | Two declared test files are missing. Defect 10. |
| E1/E2 mapper | 8 / 8 pass | One open finding in the example fixture. |

## Open defects

Nothing below was changed. Everything is preserved as received, because `prompt_E.txt`
says to report issues and not to alter the design.

| # | Where | Defect |
|---|---|---|
| 1 | `A1-shared-contracts/src/ai_engineering_contracts/schema_export.py:22` | `from typing import type`. `typing` has no `type`; it is a builtin. ImportError kills the module and the `export-contract-schemas` script. Delete the line. |
| 2 | `A2-change-execution-service/tests/conftest.py`, `run_git()` | `.strip()` removes the trailing newline that a Git patch requires. `git apply` then reports `corrupt patch`. Causes 5 failures. |
| 3 | `A3-release-gate-service/tests/conftest.py`, `run_git()` | Same defect as 2. Causes 3 failures. |
| 4 | `A3-release-gate-service/tests/test_policy.py:40` | `exit_code=None if False else None`. `ControlResult` has no `exit_code` field and forbids extras. Causes 3 failures. |
| 5 | `A4-evidence-storage/src/ai_engineering_evidence/recorder.py:158` | Reads `execution_result.execution_artifacts`. A1's `ExecutionResult` has no such field, so `record_run()` raises `AttributeError` on every call. The tests do not catch this: `tests/test_recorder.py` tests the store twice and never calls the recorder. |
| 6 | `A7-process-outcomes/tests/test_attribution.py:61` | `assert assessment.absolute_difference == -0.10`. `0.20 - 0.30` is `-0.09999999999999998` in binary floating point. The calculation is correct; the test is brittle. Use `pytest.approx`. |
| 7 | `A9-orchestrator` | `src/ai_engineering_orchestrator/cli.py` is in the declared structure and `pyproject.toml` points the `engineering-orchestrator` console script at `cli:main`, but the file was never supplied. The installed command fails with `ModuleNotFoundError`. |
| 8 | `A10-execution-environment/src/execution_environment/hashing.py:24` | `canonical_json_bytes()` converts a Pydantic model only at the top level. `service.py:89` passes a plain dict holding nested models (`network`, `limits`), so `json.dumps` raises `TypeError`. **`ExecutionEnvironmentService.execute()` fails on every call.** |
| 9 | `A10-execution-environment/Dockerfile` | The final `CMD [ ... ]` spans five lines. Dockerfile JSON-array form must be on one line. Every other Dockerfile in this repository uses the single-line form. The image cannot build. Not confirmed against a real build — no Docker daemon was running here. |
| 10 | `A9`, `A12` and `A1` | Three incompatible task-request types. `A1.TaskRunRequest` has 16 fields; `A9.TaskRequest` has 9; `A12.TaskRequest` has 9. Only `task_type`, `requested_by` and `metadata` are common to all three. Neither A9 nor A12 imports `ai_engineering_contracts`. `A12.OrchestratorPort.submit_task()` cannot feed `A9.EngineeringAutomationOrchestrator.run()`. **This is contract drift, the blind spot the platform exists to catch.** |

## Files that were declared but never supplied

The source documents list these in their repository structure. The text never contained
them. They were not invented.

| Component | Missing |
|---|---|
| A9 | `src/ai_engineering_orchestrator/cli.py`, `README-NINTH-STEPS.md` |
| A10 | `README-TENTH-STEPS.md` |
| A11 | `tests/test_hashing.py`, `tests/test_validation.py`, `README-ELEVENTH-STEPS.md` |
| A12 | `tests/test_idempotency.py`, `tests/test_azure_devops.py`, `README-TWELFTH-STEPS.md` |

Two components also supplied files that their own declared structure does not list:
`A10` adds `src/execution_environment/profile_validation.py`, and `A11` adds
`src/task_specification_registry/yaml_loader.py` and `promotion.py`.

## One correction that was applied

Four URLs arrived wrapped by a mail-gateway rewriter
(`urldefense.com/v3/__...__;!!O9lNpA!...`), including `JSON_SCHEMA_DIALECT` in
`constants.py` and an f-string whose `{artifact_id}` had been mangled. That is transit
corruption, not source code, so the original URLs were restored.
