# Index — where every original artifact went

This repository holds the artifacts from the `repo_diagram.txt` build flow, converted
from `.txt` into their proper formats. Use this file to find anything.

This document uses Simplified Technical English (ASD-STE100).

Open questions and findings to discuss are in [NOTES.md](NOTES.md).

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
| `B1` | consolidated shared contracts | [B1-consolidated-shared-contracts/](B1-consolidated-shared-contracts/) |
| `B2` | not-implemented register | [B2-not-implemented-register/NOT-IMPLEMENTED.md](B2-not-implemented-register/NOT-IMPLEMENTED.md) |
| `B3` | design rationale | [B3-design-rationale/DESIGN-RATIONALE.md](B3-design-rationale/DESIGN-RATIONALE.md) |
| `B4` | composition root + first end-to-end X1 test | [B4-composition-root/](B4-composition-root/) |
| `B5` | hidden-oracle evaluation campaign | [B5-evaluation-campaign/](B5-evaluation-campaign/) |
| `B6` | production configuration + reconciliation | [B6-production-configuration/](B6-production-configuration/) |
| `B7` | cross-component consistency review | [B7-consistency-review/](B7-consistency-review/) |
| `B8` | master README | [B8-master-readme/README.md](B8-master-readme/README.md) |
| `E1.txt` | evidence diversity mapper | [E1-E2-conceptual-diversity-mapper/E1_evidence_diversity_mapper_reference.py](E1-E2-conceptual-diversity-mapper/E1_evidence_diversity_mapper_reference.py) |
| `E2.txt` | its README | [E1-E2-conceptual-diversity-mapper/README.md](E1-E2-conceptual-diversity-mapper/README.md) |
| `prompt_AB_.txt` | reconstruct one repository from A + B | [prompts/prompt_AB_.txt](prompts/prompt_AB_.txt) |
| `prompt_truncate.txt` | cut down to a laptop-runnable demo | [prompts/prompt_truncate.txt](prompts/prompt_truncate.txt) |
| `prompt_E.txt` | preserve E1/E2 verbatim | [prompts/prompt_E.txt](prompts/prompt_E.txt) |
| `prompt_EBA.txt` | integrate the mapper into the release gate | [prompts/prompt_EBA.txt](prompts/prompt_EBA.txt) |
| `repo_diagram.txt` | the build flow | [prompts/repo_diagram.txt](prompts/repo_diagram.txt) |

All five prompts are now complete. The first versions of three of them were transcribed
from photographs that stopped partway through; those have been replaced.

### `prompt_AB` came in two versions, and only one is kept

Two variants arrived: `prompt_AB.txt` (280 lines) and `prompt_AB_.txt` (237 lines). They
are the same instruction set, reorganised. `prompt_AB_.txt` is the later revision:

- it replaces 20 flat numbered rules with named sections;
- it **adds** `EvidenceBundle` to the canonical contract list, which the older version
  omitted;
- it **adds** the rule that local test doubles must be named `local`, `fake`, `scripted`,
  `synthetic` or `in-memory`, so a stub cannot pass for a production adapter.

It drops the older rules 18 and 19, on failure-state distinctions and statistical
discipline. That loses nothing. Both are already carried by the artifacts the prompt
reconstructs: rule 18 is the twelve typed exceptions in B7 section 80, and rule 19 is
four lines of the B7 section 154 invariant checklist, enforced in B5 code where
`wilson_interval` returns `None` rather than a fake zero for an empty denominator. In a
prompt whose central instruction is COPY VERBATIM, restating them was redundant.

**Use `prompt_AB_.txt`.** The older variant is deliberately not kept, to avoid a second
A10-style situation where nobody can tell which version was used.

### The B-series is a second, parallel repository

The A-series describes twelve components, each its own Python package
(`ai_engineering_contracts`, `ai_engineering_change_executor`, and so on).

The B-series describes **one** package, `l1_automation`, with a completely different
internal layout. B4, B5, B6 and B7 are fragments of that single package, not four
separate projects. To run them you must merge the four `src/` trees into one directory.
`PYTHONPATH` is not enough, because `architecture/` is a regular package in B6 and so
B7's module inside it stays invisible.

B1 is different again. It keeps the A-series package name `ai_engineering_contracts`
but replaces its contents. See defect 11.

Each B directory also holds `B<n>-SOURCE.txt`. That is the original bundle document as
received, kept complete, because it contains migration steps and acceptance criteria
that are not code and have no declared filename.

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
| `B1-consolidated-shared-contracts/` | `ai_engineering_contracts` — **collides with A1** | — |
| `B4-composition-root/` | `l1_automation.bootstrap` | — |
| `B5-evaluation-campaign/` | `l1_automation.evaluation` | — |
| `B6-production-configuration/` | `l1_automation.{configuration,bootstrap,architecture}` | — |
| `B7-consistency-review/` | `l1_automation.architecture` | B6 |

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

**The B-series needs its own virtual environment.** B1 must never be installed beside
A1. See defect 11.

```bash
python -m venv .venv-b
.venv-b/bin/pip install "pydantic>=2.10,<3" pytest PyYAML
.venv-b/bin/pip install -e B1-consolidated-shared-contracts
```

B4 to B7 have no `pyproject.toml`. Run them with the source directory on the path:

```bash
cd B5-evaluation-campaign && PYTHONPATH=src ../.venv-b/bin/python -m pytest tests -q
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
| B1 | 16 / 16 pass | The cleanest artifact received. But see defect 11. |
| B4 | 6 / 6 pass | |
| B5 | 10 / 10 pass | |
| B6 | 10 / 13 pass | Defects 12 and 13. One failure was mail corruption, now repaired. |
| B7 | cannot import alone | Needs B6 merged into the same tree. Defect 14. |
| B4+B5+B6+B7 merged | 25 / 30 pass | Defect 15. |

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
| 11 | `A1` and `B1` | Both define the Python package `ai_engineering_contracts`, with incompatible contents. A1 has `TaskRunRequest` and `GateOutcome`; B1 has `TaskRequest` and `GateDisposition`. The distribution names differ (`ai-engineering-shared-contracts`, `ai-engineering-contracts`), so **pip installs both without any warning** and whichever comes last silently shadows the other. That would break A2, A3, A4 and A5. B1 is therefore installed in a separate `.venv-b`. |
| 12 | `B6-production-configuration/src/l1_automation/bootstrap/composition.py:125` | `_build_local_application()` imports six modules that exist nowhere in B1–B8: `l1_automation.capabilities.local_registry`, `.change_execution.local_service`, `.evidence.in_memory_repository`, `.release_gate.local_service`, `.workflow.in_memory_publisher`, `.orchestration.service`. The composition root cannot build anything. |
| 13 | `B6-production-configuration/tests/` | No `conftest.py` was supplied, but `test_readiness.py` requires the fixture `azure_settings` and `test_composition.py` requires `complete_azure_settings`. Both error. The source even comments that the fixture "should be" the one used by the configuration tests, so the author knew it was absent. |
| 14 | `B7-consistency-review` | Imports `l1_automation.architecture.repository_check`, which lives in B6. Because B6 makes `architecture/` a regular package, putting both on `PYTHONPATH` is not enough — the two directory trees must be physically merged. B7 collects zero tests on its own. |
| 15 | `B4`, `B5`, `B6`, `B7` merged | **B7's own architecture review fails on the repository B4–B7 describe.** `tools/run_b7_review.py` reports 7 violations: `bootstrap/x1_poc.py` redefines `GateOutcome`, `TaskRequest`, `TaskSpecification`, `CandidateArtifact`, `EvidenceArtifact` and `GateDecision`, and `evaluation/contracts.py` redefines `GateOutcome`. B4 and B5 both say these compatibility types are temporary and must be deleted during B6 reconciliation. That step was never performed, so the B-series does not meet its own acceptance criteria. |
| 16 | `B1` versus `B4`–`B7` | The two halves of the B-series are not connected. `l1_automation` never imports `ai_engineering_contracts` anywhere. B7's checker expects the canonical contracts to live in `l1_automation/contracts/`, which does not exist; B1 puts them in `ai_engineering_contracts` instead. Two different canonical homes are declared for the same contracts. |

## Files that were declared but never supplied

The source documents list these in their repository structure. The text never contained
them. They were not invented.

| Component | Missing |
|---|---|
| A9 | `src/ai_engineering_orchestrator/cli.py`, `README-NINTH-STEPS.md` |
| A10 | `README-TENTH-STEPS.md` |
| A11 | `tests/test_hashing.py`, `tests/test_validation.py`, `README-ELEVENTH-STEPS.md` |
| A12 | `tests/test_idempotency.py`, `tests/test_azure_devops.py`, `README-TWELFTH-STEPS.md` |
| B6 | `tests/conftest.py` (two fixtures are used but never defined) |
| B4–B7 | one `pyproject.toml` for `l1_automation`; B4 supplies only a fragment |

Two components also supplied files that their own declared structure does not list:
`A10` adds `src/execution_environment/profile_validation.py`, and `A11` adds
`src/task_specification_registry/yaml_loader.py` and `promotion.py`.

B6 also shows a recommended `pyproject.toml` and a pytest marker block, but presents them
as guidance rather than as files. They were not written out.

## Two corrections that were applied

Both are repairs to mail-gateway damage, not changes to the design.

**A-series.** Four URLs arrived wrapped by a rewriter
(`urldefense.com/v3/__...__;!!O9lNpA!...`), including `JSON_SCHEMA_DIALECT` in
`constants.py` and an f-string whose `{artifact_id}` had been mangled.

**B-series.** The same rewriter hit four URLs in
`B6-production-configuration/tests/configuration/test_loader.py`. One of them mattered:
`test_plain_http_service_endpoint_is_rejected` deliberately uses `http://` to prove that
plain HTTP is refused. The wrapper turned it into an `https://urldefense.com/...` URL, so
the test stopped testing anything and failed. Restoring the four originals fixed it. The
corrupted form is still visible in `B6-SOURCE.txt`, which is kept exactly as received.
