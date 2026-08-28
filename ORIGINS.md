# Origins — what the original artifacts were, what we use, and what we still need

This document explains the repository from the very beginning: where the files came
from, what each one is, which parts the current plan actually uses, and what still has
to be built. Read it before INDEX.md. INDEX.md tells you *where* every artifact went;
this file tells you *why it exists* and *whether it matters now*.

---

## 1. The story in six steps

1. **The question.** K wants to know: can an AI do simple ("Layer 1") engineering
   tasks — bump a package, rename a variable, sweep a deprecated call — and if it
   does, how would we know each result is safe to release?

2. **The proposed answer.** A pipeline with two halves. An AI makes the change
   (*ChangeExecutionService*). An independent gate checks it and says PASS, FAIL, or
   HUMAN_REVIEW_REQUIRED (*ReleaseGateService*). And because a gate's verdicts mean
   nothing until the gate itself is measured, an offline harness
   (*EvaluationCampaignRunner*) runs the same pipeline on tasks whose correct answer
   is already known, and counts how often the gate was right.

3. **The design documents.** To design this, about twenty documents were generated
   with an AI assistant (GitHub Copilot, per INDEX.md's A10 note): `A1.txt`–`A12.txt`
   (twelve components) and `B1.txt`–`B8.txt` (a second pass meant to reconcile the
   first twelve into one system), plus `E1.txt`/`E2.txt` (a separate "Evidence
   Diversity Mapper"). These are **descriptions of code, not code**.

4. **The prompts.** Five prompt files instructed an AI to turn those documents into
   real repositories, in stages (see the diagram in `prompts/repo_diagram.txt`).

5. **This repository.** It is the unpacked result of that process, plus an audit:
   every artifact converted from `.txt` into a real directory with real Python
   (~35,000 lines), catalogued in INDEX.md with its test status and known defects,
   with open questions in NOTES.md. Two of the four build stages never ran. Nothing
   in the tree calls an AI, and no end-to-end gated run has ever happened.

6. **What was delivered.** Runs 1–5 on Task X1 were executed and logged in `demo/runs/RUNLOG.md`
   (confirming ~88s latency and ~12 AIC cost per run, sizing the bill). The reusable production
   tool was built in [`release-gate/`](release-gate/) (version 0.6.0) as a standalone Python CLI
   and portable assistant skill (supporting Copilot, Codex, Claude Code, Antigravity) with
   a bounded repair state machine ($C0 \to C1 \to C2$) and rolling 10/100 decision dashboards.
   The `rate-limiter` benchmark was restored and hardened to test algorithmic invariants, 100%
   branch coverage, and mutation analysis. Live evaluation campaigns (`demo/campaign.sh`) and an
   interactive presentation suite (`docs/`) were built. The scaffolding's lasting value remains
   its *design thinking* and its *measurement math*, not its code.


---

## 2. The four repositories the build flow planned

From `prompts/repo_diagram.txt`:

```
A[1-12].txt + B[1-8].txt   --prompt_AB-------->  repo_0
repo_0                     --prompt_truncate-->  repo_demo_0
E1.txt + E2.txt            --prompt_E--------->  repo_evidence
repo_demo_0 + repo_evidence  --prompt_EBA----->  repo_demo_1
```

| Name | Meant to be | Was it built? |
|---|---|---|
| `repo_0` | One integrated repository implementing A + B as a single `l1_automation` package | **Partially.** The artifacts were unpacked here and run individually, but the merge into one package never happened. The A-series and B-series share zero imports. |
| `repo_demo_0` | A laptop-size cut of `repo_0` that ends at GateDecision and adds an LLM API connector (`L1_LLM_BASE_URL/_API_KEY/_MODEL`) | **No.** `prompt_truncate` was never executed. No model client of any kind exists in the tree. |
| `repo_evidence` | E1/E2 preserved verbatim as their own repository | **Yes** — `E1-E2-conceptual-diversity-mapper/`. |
| `repo_demo_1` | `repo_demo_0` with the mapper integrated into the gate's evidence planning | **No.** `prompt_EBA` was never executed. Its integration target, an `EvidencePlanner` class, exists nowhere in the tree. |

## 3. The five prompts

| File | What it instructs | Status |
|---|---|---|
| `prompts/prompt_AB_.txt` | Reconstruct one integrated repository from the 20 A/B files, with B1 authoritative for shared contracts | Partially executed: unpacking happened, integration did not. Two variants of this prompt existed; the older `prompt_AB.txt` was deliberately discarded (see INDEX.md and note N-5 — the two-versions-no-provenance failure this platform exists to prevent happened to its own build instructions). |
| `prompts/prompt_truncate.txt` | Create the laptop demo repo: scope ends at GateDecision, LLM connector via env vars, remove post-release/business modules | Never executed. Useful today as an **acceptance checklist** for whatever demo we do build — the current tree fails it (A6–A8 still present, no connector). |
| `prompts/prompt_E.txt` | Preserve E1/E2 verbatim with minimal scaffolding | Executed. |
| `prompts/prompt_EBA.txt` | Integrate the mapper behind a thin adapter so evidence planning can use conceptual-coverage gaps | Never executed. |
| `prompts/repo_diagram.txt` | The map of the whole flow | n/a — it is the diagram above. |

## 4. The A-series — twelve components

Verified state is from running every suite (see INDEX.md for exact counts and defects).

| ID | Directory | What it is | Verified state | In the new plan? |
|---|---|---|---|---|
| A1 | `A1-shared-contracts/` | Common data types for the A-series | Types work; the package's own test collection aborts on a broken import; only A2–A4 import it | Superseded by B1 if contracts are ever needed |
| A2 | `A2-change-execution-service/` | The thing that makes the change | Applies a **human-supplied patch — contains no AI call**; silently truncates large patches | **Replaced by Copilot CLI** |
| A3 | `A3-release-gate-service/` | The gate | The most complete component: clean-room re-execution of tests plus a deterministic policy. Known decision bugs: its own infrastructure failures become candidate FAILs; an interrupted control sequence can yield a false PASS; path-scope glob matching is broken | **Reference** for the gate skill's semantics; not the demo runtime |
| A4 | `A4-evidence-storage/` | Evidence store + recorder | Store works; the recorder crashes on every call and its tests never call it | Not needed |
| A5 | `A5-pipeline-evaluation/` | Readiness / campaign statistics | Wilson intervals correct; the readiness verdict ignores the false-block rate; imports none of the packages it declares as dependencies | **Keep the math**, ignore the verdict |
| A6 | `A6-production-observability/` | Post-release telemetry | Out of demo scope per `prompt_truncate` | Not needed |
| A7 | `A7-process-outcomes/` | Business-outcome attribution | "Attribution strength" is declared by the caller, not computed | Not needed |
| A8 | `A8-engineering-economics/` | Cost/value accounting | Computes confidence intervals, then ignores them in its verdicts | Not needed — cost lives in our run log |
| A9 | `A9-orchestrator/` | Control plane | Island; its ports fit no other component's types; its declared CLI file was never supplied | Not needed |
| A10 | `A10-execution-environment/` | Sandbox for untrusted code | Island; enforces no limit it declares; `execute()` crashes on every call | Not needed now; the *idea* matters when generated code runs unattended |
| A11 | `A11-task-specification-registry/` | Versioned, hashed task specs | Island; the hashing/versioning idea is the antidote to the N-5 provenance failures | **Idea reused** for our task specs; code not |
| A12 | `A12-workflow-integration/` | Jira / Azure DevOps bridge | Island; duplicate-run (idempotency) bug | Replaced by GitHub + Copilot CLI |

Note the pattern: **A5 through A12 neither import nor are imported by any other
component.** Eight of twelve components are islands.

## 5. The B-series — the reconciliation pass

| ID | Directory | What it is | Verified state | In the new plan? |
|---|---|---|---|---|
| B1 | `B1-consolidated-shared-contracts/` | Canonical contracts, v2 | Cleanest artifact received (16/16 tests). Cannot be co-installed with A1: pip silently merges the two package trees and breaks A2–A4. A one-line distribution rename fixes it | The contract base **if** any A/B code is reused |
| B2 | `B2-not-implemented-register/` | Register of what is deliberately unbuilt | 5,287 lines. Honest about enterprise blockers (Azure, RBAC); silent about self-inflicted gaps (no AI, no planner). Its NI-id convention appears in 0 of 49 `NotImplementedError` sites | Reference; compress later |
| B3 | `B3-design-rationale/` | Why the design is shaped this way | 8,057 lines. The principles are the best of the scaffolding; some are enforced in code, several are contradicted by it | **Mine for the principles**; do not maintain as-is |
| B4 | `B4-composition-root/` | Wires everything; first end-to-end "X1" run | Runs — but its "four evidence types" are one string comparison relabelled four times | Teaching example of what not to do; not needed |
| B5 | `B5-evaluation-campaign/` | The measurement harness + hidden oracle | Statistics module is correct (Wilson, explicit denominators, refuses fake zeros). The oracle is substring matching, and the runner has never been connected to any gate | **Reuse `statistics.py`** and the campaign shape, with an executable oracle instead |
| B6 | `B6-production-configuration/` | Final config + composition | Config loader mostly works; the composition root imports six modules that do not exist and has never executed | Not needed |
| B7 | `B7-consistency-review/` | Automated architecture checker | Three of its four checks scan zero files by construction and cannot fail | The **concept** (checks with falsification fixtures) is needed; this code is not |
| B8 | `B8-master-readme/` | Master README | 3,591 lines; useful narrative; several claims the code contradicts | Reference |

## 6. E1 / E2 — the Evidence Diversity Mapper

`E1-E2-conceptual-diversity-mapper/` — a ~4,000-line reference implementation plus a
long README, preserved verbatim per `prompt_E`. Its job: given a set of artifacts and
a concept schema, say which conceptual regions are covered, sparse, or missing.

It was never integrated into anything (that was `prompt_EBA`, never run). Its first
real use, per K, is simpler and cheaper than the planned integration: **audit the
benchmark corpus** — "these repos are all OOP libraries, none is service-shaped" — to
tell us what our benchmark cannot see. Park it until we have a corpus worth auditing.

## 7. How the artifacts map to K's HLD diagram

| HLD box | Artifact | Status |
|---|---|---|
| Task request | A11 specs, A1/B1 types | Exists on paper; three incompatible request types |
| ChangeExecutionService | A2 | Exists, but no AI inside → **Copilot CLI takes this role** |
| Candidate patch | A1/B1 `CandidateArtifact` | Exists |
| ReleaseGateService | A3 | Real, one of its three drawn engines built (deterministic execution; test synthesis and mutation analysis are explicitly excluded in code) |
| Gate decision | A3 policy | Real; four outcomes, not three (adds MORE_EVIDENCE_REQUIRED) |
| BenchmarkFactory → golden benchmark | B5 | Four toy cases; oracle is substring matching |
| EvaluationCampaignRunner | B5 + A5 | Structurally complete; never connected to a gate |
| Readiness report | A5 | Exists; ignores false-block rate |

## 8. What the current plan takes from the scaffolding

**Five ideas (the real inheritance):**

1. **Generator and verifier are separate.** Never ask the model that wrote the code
   whether its code is correct (B3, B8).
2. **Three-way verdict, with "cannot judge" distinct from "bad".** An infrastructure
   failure or missing evidence must not be recorded as a candidate failure (B3
   invariant 7, B5's `ORACLE_ERROR`).
3. **Measure the gate offline against known answers**, because production can only
   ever reveal bad changes that shipped — never good changes wrongly blocked
   (NOTES N-6, the sharpest thinking in the repo).
4. **Denominators and confidence intervals, never one composite score**
   (B5 `statistics.py`, `prompt_truncate`).
5. **Version and hash every governing artifact**, because this project itself lost
   track of which prompt and which A10 was current (N-5, A11's design).

**Two code pieces worth reusing:** B5's `statistics.py` (Wilson intervals done
right), and A3's policy semantics as a reference when writing the gate skill.

**Plus the audit itself:** INDEX.md and NOTES.md are the record of what was received
and what state it was in. That record is worth keeping — the scaffolding
demonstrates, on itself, the contract drift and provenance failures the platform was
designed to catch.

## 9. What was not used

- **A6–A8** (~5,500 lines): post-release telemetry, business outcomes, economics —
  explicitly out of scope for the demo by `prompt_truncate`'s own rules.
- **A9–A12** (~5,300 lines): islands with no importers; orchestration and workflow
  roles now filled by Copilot CLI + GitHub.
- **B4, B6** composition roots: one manufactures its evidence, the other never ran.
- **B7's checker code**: cannot fail, so its passes mean nothing.
- **A2 as executor** and the never-built LLM connector: Copilot CLI replaces both.
- **Two of the four build stages** (`prompt_truncate`, `prompt_EBA`): never executed;
  the repositories they were to produce do not exist.

Roughly speaking: of ~35,000 lines of Python received, the demo path ahead executes
none of it directly, and inherits two modules and five ideas.

## 10. What was built and what we still need

### What has been built

1. **The gate as a skill and CLI:** Standalone implementation in [`release-gate/`](release-gate/)
   (v0.6.0) with multi-agent skills (GitHub Copilot, OpenAI Codex, Claude Code, Antigravity),
   bounded repair state machine ($C0 \to C1 \to C2$), and fail-closed checks. The bash gate
   at `demo/gate/gate.sh` remains supported for teaching.
2. **The X1 task spec:** Implemented and versioned (`demo/tasks/X1.md`, `X1_v1.md`, `X1_v2.md`).
   Identified and proved the `₹500` and `♥ love` transliteration divergence between `text-unidecode`
   and `Unidecode`.
3. **The corpus benchmarks:**
   - `python-slugify` (Task X1): Admitted, pinned, and evaluated.
   - `rate-limiter`: Restored and hardened under `release-gate/demo/rate-limiter/` with 100% branch
     coverage, 8-mutant mutation gauntlet, and bounded repair loop.
   - Admitted candidate repos: `itsdangerous` (X2) and `cachetools` (X3); see `demo/CORPUS.md`.
4. **The run log & live campaigns:**
   - Runs 1–5 completed on Task X1 (v2) in `demo/runs/RUNLOG.md` (mean 88s, ~11.8 AIC).
   - Live campaign runner added (`demo/campaign.sh`), executing Anthropic Claude sessions through
     the gate and logging to `demo/runs/campaign-ledger.xlsx` while classifying executor errors as `EXEC_ERROR`.
5. **Observability dashboards & presentations:**
   - Rolling 10/100 gate decision dashboards (`_observability/`) with tamper-evident HTML snapshots.
   - Presentation hub (`docs/presentations.html`) with deep-dive interactive decks.

### What remains

1. **Corpus expansion:** Carding X2 (`itsdangerous`) and X3 (`cachetools`) on the bench.
2. **The mapper as a corpus audit:** Using `E1-E2-conceptual-diversity-mapper/` to analyze what
   service-shaped architectures the benchmark currently lacks.
3. **The backtest (NOTES N-8):** Replaying the gate over ~200 real historical merged changes in a
   target repository, using reverts as ground-truth labels.

**How many runs mean what** (B5's Wilson math — if every run passes, the true failure rate could still be up to):

| clean runs | true failure rate could still be |
|---|---|
| 5 | 43% |
| 10 | 28% |
| 20 | 16% |
| 30 | 11% |
| 100 | 4% |

So 5 runs size the bill; 30+ runs start to be evidence.

## 11. Rate-limiter benchmark (removed 2026-08-16, restored & hardened in 0.4.0+)

The repository originally contained `release-gate/demo/rate-limiter/`, a small hand-built rate limiter with
its own test-and-analysis chain that predated the scaffolding. It was temporarily removed on 2026-08-16
to focus on the A/B/E scaffolding audit (decision recorded in NOTES.md, closed note N-1).

Beginning in Release Gate 0.4.0, the rate limiter was **restored, redesigned, and hardened** under
[`release-gate/demo/rate-limiter/`](release-gate/demo/rate-limiter/) as the second canonical benchmark.
Unlike `python-slugify` (which tests dependency lifecycles and packaging blindspots), the rate limiter
benchmarks deep algorithmic invariants: 100% branch coverage, an 8-mutant mutation gauntlet,
a differential brute-force oracle, and the full $C0 \to C1 \to C2$ bounded repair workflow.

## 12. Current state

The production-ready tool lives in [`release-gate/`](release-gate/) (version 0.6.0).
It is completely independent of A1/A2/A3/A9/B6, treating the scaffolding as historical design
principles and audit evidence. The repository now includes:
- Production Release Gate CLI, schemas, and multi-agent assistant skills;
- Automated bounded repair workflows and rolling decision dashboards;
- Dual benchmark suites (`python-slugify` and `rate-limiter`);
- Interactive teaching demo and live campaign runner (`demo/`);
- Presentation hub and technical deep-dives (`docs/`).

