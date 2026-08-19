# Diagrams

> **Legacy demo:** These diagrams describe `demo/gate/gate.sh`; they are not
> the architecture of the reusable [`release-gate/`](../release-gate/README.md)
> product.

Two diagrams, in Mermaid. GitHub renders them in place; draw.io imports them
via *Arrange → Insert → Advanced → Mermaid* (paste the block); most IDEs
preview them.

## 1. One run, end to end — what actually happens

This is the sequence you drive by hand in `RUN.md`. The dashed line is the
boundary between the ONLINE lane (what would happen on any real change) and
the OFFLINE lane (grading the gate against the answer key). Notice the oracle
takes part only below the line, and Copilot only above it.

```mermaid
sequenceDiagram
    autonumber
    actor You
    participant WB as Workbench<br/>(python-slugify + venv)
    participant CP as Copilot CLI<br/>(the AI — makes the change)
    participant GATE as gate.sh<br/>(6 deterministic checks)
    participant OR as Hidden oracle<br/>(demo/oracle — 15 asserts)
    participant LOG as RUNLOG.md

    rect rgb(235, 245, 255)
    Note over You,GATE: ONLINE LANE — same steps as on any real change
    You->>WB: setup_workbench.sh reset
    WB-->>You: 82 passed — BASELINE GREEN
    You->>CP: paste task X1.md (start stopwatch)
    CP->>WB: edit setup.py, slugify.py, README, tox.ini
    CP-->>You: "Task complete — 82 passed" (stop stopwatch, note AIC + model)
    You->>GATE: gate.sh <workbench> <venv> run-NN
    GATE->>WB: re-run tests in the venv (do not trust Copilot's report)
    GATE->>WB: coverage vs baseline · mypy · ruff vs baseline · secret scan · test.py untouched?
    GATE-->>You: check table + VERDICT (PASS / FAIL / NEEDS_HUMAN)<br/>+ runs/run-NN/evidence.json
    end

    alt VERDICT = NEEDS_HUMAN
        Note over You: a check could not run — you are the human review box
        You->>WB: fix the environment (e.g. pip install the declared dep)
        You->>GATE: gate.sh … run-NNb  (new run id — a new event)
        GATE-->>You: VERDICT
    end

    rect rgb(235, 255, 235)
    Note over You,LOG: OFFLINE LANE — grade the gate against known truth
    You->>OR: grade.sh run-NN <wall_s> <cost> <model>
    OR->>WB: run the 15 hidden asserts against the changed code
    OR-->>You: truth = correct / wrong / oracle_error
    You->>LOG: box = gate verdict × truth<br/>good_pass · FALSE_RELEASE · FALSE_BLOCK · good_catch · escalated
    end
```

## 2. The HLD, mapped onto the demo

The manager's HLD has two lanes and a small set of boxes. This shows which
file plays each box today. Boxes drawn dashed exist in the HLD but are not
part of the demo yet.

```mermaid
flowchart TB
    subgraph ONLINE["ONLINE — every real or benchmark change"]
        direction LR
        T["Task request<br/><i>demo/tasks/X1.md</i>"]
        CES["ChangeExecutionService<br/><i>Copilot CLI</i>"]
        C["Candidate patch<br/><i>workbench diff → runs/…/candidate.patch</i>"]
        subgraph RGS["ReleaseGateService — <i>demo/gate/gate.sh</i>"]
            direction TB
            DE["deterministic execution<br/>tests · coverage · types · lint · secrets · scope"]
            TS["independent test synthesis"]:::notyet
            MA["mutation / adversarial analysis"]:::notyet
            GD["gate decision<br/>error → NEEDS_HUMAN<br/>else fail → FAIL<br/>else PASS"]
            DE --> GD
            TS -.-> GD
            MA -.-> GD
        end
        R["Release"]:::outside
        H["Human review<br/><i>you, on NEEDS_HUMAN</i>"]
        T --> CES --> C --> RGS
        GD -->|PASS| R
        GD -->|NEEDS_HUMAN| H
        GD -->|FAIL| X["blocked"]:::outside
    end

    subgraph OFFLINE["OFFLINE — development and qualification campaigns"]
        direction LR
        BF["BenchmarkFactory<br/><i>demo/CORPUS.md — 3 repos, hand-verified traps</i>"]
        GB["Validated golden benchmark<br/><i>pinned commit + task card + hidden oracle</i>"]
        subgraph ECR["EvaluationCampaignRunner — <i>you + demo/grade.sh</i>"]
            direction TB
            E1["invokes ChangeExecutionService<br/><i>(you paste the task)</i>"]
            E2["invokes ReleaseGateService<br/><i>(gate.sh)</i>"]
            E3["compares against hidden oracle<br/><i>demo/oracle/test_x1_oracle.py</i>"]
            E4["computes uncertainty and readiness<br/><i>B5 statistics.py — when ≥5 rows</i>"]:::notyet
            E1 --> E2 --> E3 --> E4
        end
        RR["Readiness report / campaign analysis<br/><i>demo/runs/RUNLOG.md</i>"]
        BF --> GB --> ECR --> RR
    end

    ONLINE -.->|"the same gate, run on known-answer tasks"| OFFLINE

    classDef notyet stroke-dasharray: 5 5,fill:#f6f6f6,color:#666
    classDef outside stroke-dasharray: 3 3,fill:#fff,color:#888
```

Reading the second diagram: the demo fills every solid box. The dashed boxes
are the honest gaps — two of the gate's three evidence engines in the HLD
(test synthesis, mutation analysis) are not built, and the statistics step
waits for enough rows to summarise. "Release" is dashed because the demo ends
at the gate decision on purpose (`prompts/prompt_truncate.txt`).
