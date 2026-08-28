# Scaffolding ledger — what the demo took from the original design, and what it left

This is the exact accounting of the move from the scaffolding (`A1`–`A12`,
`B1`–`B8`, `E1`/`E2`: ~35,000 lines of generated Python) to the demo
(`demo/`: ~460 lines of shell and Python that run). For every component: what
job it was for, whether the demo does that job, and if so **where** — with the
file and line so the claim can be checked.

The one-sentence version: **the demo reuses the scaffolding's ideas, not its
code.** No file under `demo/` imports anything from `A*`, `B*` or `E1-E2-*`.
Every job the demo does, it does in a fresh, small implementation whose design
comes from the scaffolding's own principles.

For the story of where the scaffolding came from, read [ORIGINS.md](ORIGINS.md).
For per-artifact test status and defects, read [INDEX.md](INDEX.md).

---

## 1. Component by component

Legend for "In the demo": **YES (idea)** = the job is done, by new code built on
the scaffolding's principle; **YES (code)** = the scaffolding's code itself is
executed; **NO** = the job is not done, with the reason; **N/A** = the job is
outside the demo's scope by the scaffolding's own rules.

| ID | Component | Its job in the design | In the demo | Where / why |
|---|---|---|---|---|
| A1 | Shared contracts | Common data types (TaskRequest, CandidateArtifact, GateDecision…) | **NO** | The demo has one data shape: `evidence.json` (`gate.sh:194-211`) with `candidate_commit`, `candidate_diff_sha256`, `checks[]`, `verdict`. Two files that only ever pass a verdict and a truth value need no shared type library. |
| A2 | Change Execution | Make the code change | **YES (idea)** — role filled by **Copilot CLI** | The scaffolding's A2 applied a human-supplied patch and contained no AI. In the demo the executor is Copilot CLI, launched inside the workbench (`demo/RUN.md` step 2). Nothing from A2 is used. |
| A3 | Release Gate | Decide PASS / FAIL / HUMAN_REVIEW on independent evidence | **YES (idea)** | `demo/gate/gate.sh`. Same three-way verdict; same "re-run the tests yourself, do not trust the executor's report" principle (`gate.sh:106`). A3's four-way outcome (`MORE_EVIDENCE_REQUIRED`) is dropped: three states are enough for one deterministic pass. |
| A3 | ↳ infrastructure failure ≠ candidate failure (B3 invariant 7) | The gate must not blame the candidate when a check itself breaks | **YES (idea)** — and *fixed* | The scaffolding's A3 got this backwards (`ReleaseGateError` → candidate FAIL; `CheckStatus.ERROR` → FAIL). The demo maps pytest exit 2+ / timeout / missing tool to `error`, and `error` outranks `fail` (`gate.sh:84-89`, `:187-190`). Run 1 exercised exactly this branch: NEEDS_HUMAN, not FAIL. |
| A3 | ↳ scope check | Candidate must not touch what the task forbade | **YES (idea)** — narrower | A3 used `PurePosixPath.match` globs, which fail open on nested paths. The demo checks one literal file, `test.py` (`gate.sh:177-184`), because that is the one the candidate can use to rewrite its own evidence. Exact match; no glob. |
| A3 | ↳ evidence package | Immutable record of what the gate saw | **YES (idea)** — smaller | One `evidence.json` + `candidate.patch` + one log per check under `demo/runs/<run_id>/` (`gate.sh:194-212`). Hashed (`candidate_diff_sha256`), not signed. |
| A4 | Evidence storage | Persist evidence with lineage | **YES (idea)** — trivially | The filesystem: `demo/runs/<run_id>/`. One directory per run, never overwritten (`RUN.md`, why run-01 and run-01b are separate). A4's recorder crashed on every call and is not used. |
| A5 | Pipeline evaluation | Readiness statistics; Wilson intervals | **NO** (code) / **YES** (idea) | The intervals themselves are quoted (`ORIGINS.md` §10 table, `README.md` §6) but computed once, by hand, from B5's module — the demo has no statistics step yet. Needed when there are enough rows to summarise (≥5). |
| A6 | Production observability | Post-release telemetry | **N/A** | Out of scope by `prompts/prompt_truncate.txt:27-33`: the demo ends at the gate decision. |
| A7 | Process outcomes | Business-outcome attribution | **N/A** | Same. |
| A8 | Engineering economics | Cost / value accounting | **YES (idea)** — one column | Cost is recorded per run as what the tool reported, in the tool's unit, never estimated (`RUNLOG.md` header; `grade.sh:16-20`). A8's 2,169 lines of accounting are not used; the demo's "economics" is a `cost` column and a `model` column. |
| A9 | Orchestrator | Sequence the pipeline | **YES (idea)** — the orchestrator is **you** | The sequence in `demo/RUN.md`: reset → task → gate → grade. A9's ports fit no other component's types and it had no composition site. In the CI direction (see `README.md` §7 / ideation) GitHub becomes the orchestrator; either way A9 is not built. |
| A10 | Execution environment | Sandbox untrusted code | **NO** — known gap | The workbench is a venv in a temp-ish directory (`setup_workbench.sh`). Timeouts exist per check (`gate.sh:41`, `:59-70`), but there is no isolation. A10 enforced none of the limits it declared either; the *idea* matters as soon as generated code runs unattended. |
| A11 | Task specification registry | Versioned, hashed task specs | **YES (idea)** — by git | Task cards live in `demo/tasks/`, versioned by commit; the change from run 1's card to run 2's is a diff (`demo/tasks/X1-CHANGES.md`). A11's hashing code is not used. |
| A12 | Workflow integration | Jira / Azure DevOps bridge | **N/A** | No ticket system in the demo. GitHub issues would fill this role in the CI direction. |
| B1 | Consolidated contracts | Canonical types, v2 | **NO** | Same reason as A1. |
| B2 | NOT-IMPLEMENTED register | List what is deliberately unbuilt | **YES (idea)** | The demo's known gaps are stated inline where they bite (`gate.sh` header; `RUN.md` "the wall is a `cd`"; `CORPUS.md` "all three repos are pure libraries"), and this ledger's §3. B2's NI-id convention is not used. |
| B3 | Design rationale | Why the design is shaped this way | **YES (idea)** — the source of the principles | Every principle in §2 below is B3's. The document itself (8,057 lines) is not maintained; the principles that survived contact with code are restated in `README.md` §1–2. |
| B4 | Composition root + first X1 | Wire it together; one end-to-end run | **YES (idea)** — replaced entirely | The demo's "composition root" is `RUN.md`; its X1 is `demo/tasks/X1.md`. B4's own X1 manufactured four evidence types from one string comparison; the demo's six checks are six different programs (`gate.sh:106-184`). |
| B5 | Evaluation campaign + hidden oracle | Run the same pipeline on known-answer cases; grade the gate | **YES (idea)** — the offline lane | `demo/grade.sh` + `demo/oracle/test_x1_oracle.py` + `RUNLOG.md`. B5's oracle was substring matching (`required_fragment in content`); the demo's oracle is 15 executable assertions whose expected values were observed by running the code first (`test_x1_oracle.py` docstring). B5's four-box classification survives as `grade.sh:47-52`. B5's `statistics.py` is the one scaffolding module planned for reuse (see A5). |
| B6 | Production configuration | Config loader + composition | **NO** | Three policy numbers, in the script, where they can be seen (`gate.sh:39-41`). B6's composition root imported six modules that do not exist. |
| B7 | Consistency review | Automated architecture checks | **NO** — replaced by *falsification controls* | B7's checks scanned zero files by construction and could not fail. The demo instead proves each gate check *can* fire with a planted control run: `demo/runs/control2-lazy` (a lazy candidate → FALSE_RELEASE), `control3-broken-tool` (missing tool → NEEDS_HUMAN), `control4-tamper` (test.py edited → FAIL). See `README.md` §5. |
| B8 | Master README | Explain the system | **YES (idea)** | `README.md` at the root, written for someone who has never heard of any of this. B8's 3,591 lines are kept as reference. |
| E1/E2 | Evidence Diversity Mapper | Say which conceptual regions the evidence covers | **NO** — parked | Not integrated (`prompt_EBA` never ran; its target `EvidencePlanner` never existed). Its first real use is a corpus audit, not a gate component (`CORPUS.md` "What is deliberately not in the corpus yet"). |
| prompts | Build instructions | Turn the .txt into repos | **N/A** — historical | `prompt_truncate.txt` is used as an *acceptance checklist* (scope ends at the gate; report token counts explicitly or say unknown — `RUNLOG.md` header). |

Count: **0 components' code executed; 13 components' ideas carried; 6 explicitly not done or out of scope.**

---

## 2. The principles that crossed over — and where each lives now

These are the scaffolding's design commitments (mostly B3 / B8) that the demo
implements. This is the list to point at when someone asks "so what did we keep?"

| Principle (scaffolding source) | Where the demo enforces it |
|---|---|
| Generator and verifier are separate; never ask the model that made the change whether it is correct (B8 §"Why the gate should not be one LLM call", B3) | The only AI is Copilot, making the change. The gate is six deterministic programs reading exit codes (`gate.sh`). The oracle is plain `assert`s (`test_x1_oracle.py`). |
| Three-way verdict; "cannot judge" is not "bad" (B8 §"Failure versus missing assurance"; B3 invariant 7) | `pass / fail / error` per check; `error` → NEEDS_HUMAN and outranks `fail` (`gate.sh:187-190`). |
| Fail closed: a check that breaks is not a pass (B3; the scaffolding's own `must_not` idea) | Missing tool → error, not skip (`gate.sh:92-95`); secret scan: grep rc 1 is the *only* pass, rc≥2 is error (`gate.sh:169-174`); coverage that cannot be measured → error (`gate.sh:123-124`). |
| Do not trust executor-local results as release evidence (A3 docstring, README-THIRD-STEPS) | The gate re-runs the suite itself in its own venv (`gate.sh:106`). Run 1: Copilot said "82 passed", the gate found the tests could not run. |
| Candidate must not alter its own evidence (B8 §2293 "change expected assertion" as a negative candidate) | Scope check on `test.py` (`gate.sh:177-184`); the task card forbids it; `SKILL.md` forbids it. |
| Measure the gate offline against known truth, because production can only see one kind of mistake (NOTES N-6) | `grade.sh` + `oracle/`; the four boxes (`grade.sh:47-52`). |
| Hidden-oracle isolation: the online path must not see the answers (prompt_AB_, prompt_EBA) | `demo/oracle/` lives outside the workbench; Copilot is launched two directories below it (`RUN.md` step 2). Enforced by a `cd` — stated honestly as thin. |
| Explicit numerators and denominators; no composite score (prompt_truncate:238; B5 metrics docstring) | One row per run, one box per row, no aggregate score anywhere (`RUNLOG.md`). |
| Report resource use as observed, never invented (prompt_truncate:128) | `cost` and `model` columns take what the tool showed or `unknown` (`grade.sh:16-20`; `RUNLOG.md` header). |
| Repeated runs of one case are not new cases (B5-SOURCE:96-102) | Run ids are per event; run-01 and run-01b are two rows *because* they are two events, and the log says why (`RUNLOG.md` notes). |
| Green baseline before any change (implicit in B4's X1; made explicit here) | `setup_workbench.sh` refuses to report ready until the pinned suite is green; `CORPUS.md` admission rule. |
| A check must be shown able to fail before its pass means anything (the lesson of B7) | Control runs `control2-lazy`, `control3-broken-tool`, `control4-tamper` in `demo/runs/`. |

---

## 3. What the demo does *not* do — and how `release-gate` addresses it

Stated here so nobody has to discover it. Each maps to a scaffolding concern
that remains real, alongside how the standalone [`release-gate/`](release-gate/) (v0.6.0)
resolves or bounds it:

| Gap in Bash demo | Scaffolding concern | Status in `demo/` | Resolution in `release-gate` product |
|---|---|---|---|
| No sandbox — code runs in a plain venv | A10 | Known limitation; venv timeouts only | Evaluates in clean, isolated clones via private Git object DB (`--base <ref>`); non-modifying default |
| Oracle wall is a `cd` | prompt_AB_ hidden-oracle boundary | Adequate for manual runs; fragile in CI | Replaced by repo-owned `.release-gate.yaml` and separate evaluation suites; oracles isolated outside candidate tree |
| Evidence is hashed, not signed | A4 lineage; provenance | `candidate_diff_sha256` in JSON | Tamper-evident evidence packages, atomic report publication, SHA-256 patch digest verification, and immutable release asset checksums |
| No statistics step yet | A5 / B5 `statistics.py` | Runs 1–5 completed; Wilson intervals quoted in `RUNLOG.md`; live campaigns in `campaign-ledger.xlsx` | Self-contained rolling 10 and rolling 100 HTML/JSON gate decision dashboards (`_observability/`) and per-run HTML snapshots |
| Test check requires green, not differential | A3 baseline handling | Acceptable because benchmark repos are green | Base-trusted policy evaluated against `--base <ref>`; candidate cannot alter policy or test launchers |
| Corpus initially one task (X1) | E1/E2's job | `python-slugify` admitted | Dual benchmark suites: `python-slugify` (packaging/blindspots) and `rate-limiter` (100% coverage, 8-mutant gauntlet, brute-force model) |
| Gate invoked by hand | A9 / A12 orchestration | Automated campaigns via `campaign.sh` | Portable assistant skills across GitHub Copilot, OpenAI Codex, Claude Code, and Antigravity with bounded repair state machine ($C0 \to C1 \to C2$) |

---

## 4. Can the scaffolding be deleted?

Not yet — but for one reason only, and it is not "we might need the code."

The scaffolding directories are the **evidence for the audit** in `INDEX.md`
and `NOTES.md`: sixteen catalogued defects, the A1/B1 co-install collision, the
nine incompatible gate-verdict definitions, the architecture checker that scans
zero files. Those findings are the strongest example this project has of the
exact failure mode it exists to catch — contract drift and provenance loss in
AI-generated code — and every claim points at a file and line that must still
exist to be checked.

Recommendation, in two steps:

1. **Now:** keep the tree; add nothing to it; run nothing from it except
   `B5-evaluation-campaign/…/statistics.py` when the campaign is large enough
   to need it.
2. **When the demo has ≥5 rows and X2 is carded:** move `A6`, `A7`, `A8`,
   `A9`, `A10`, `A12`, `B4`, `B6`, `B7` to `archive/` in one commit (they are
   `N/A` or `NO` above and cited by nothing in `demo/`), leaving `A1`–`A5`,
   `B1`–`B3`, `B5`, `B8`, `E1-E2` and `prompts/` in place as the audit
   evidence and the design source. Update `INDEX.md` paths in the same commit.
   Nothing is lost — git keeps it — and the tree stops implying that 35,000
   lines are load-bearing.

---

## 5. Current state

The production-ready tool is implemented independently at [`release-gate/`](release-gate/) (version 0.6.0).
This does not revise the historical ledger: the A/B/E directories remain the received scaffolding and audit
evidence, and their recorded defects/test counts remain historical facts. A3 contributed concepts only;
it is not a package dependency.

The current implementation encompasses:
1. **`release-gate/` (v0.6.0):** Standalone Python CLI, versioned schemas, portable skills for 4 AI assistants,
   bounded repair state machine ($C0 \to C1 \to C2$), read-only Graphify diagnosis, and rolling 10/100 dashboards.
2. **`release-gate/demo/`:** Dual reproducible benchmarks (`python-slugify` and `rate-limiter`).
3. **`demo/`:** Completed Runs 1–5 on Task X1 (card v2), the bash teaching gate, `campaign.sh` automated runner,
   and `campaign-ledger.xlsx`.
4. **`docs/`:** Presentation hub (`presentations.html`) with interactive deep-dive slide decks.

