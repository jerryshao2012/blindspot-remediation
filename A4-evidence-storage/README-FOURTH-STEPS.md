# Component 4 — Evidence Storage & Immutable Run Manifests

## 1. Purpose

Component 4 establishes durable provenance for the AI engineering platform.

Its primary question is:

> Can we later prove exactly what evidence supported a particular engineering
> run and whether that evidence has changed?

This is different from logging.

Logs help engineers understand execution.

Evidence storage supports reproducibility, assurance, audit, pipeline
evaluation, and later investigation.

---

## 2. Relationship to Components 1–3

The architecture now contains four major pieces:

```text
Task Package / Shared Contracts
             │
             ▼
ChangeExecutionService
             │
             ▼
Candidate Patch
             │
             ▼
ReleaseGateService
             │
             ▼
GateResult + Evidence
             │
             ▼
EvidenceRecorder
             │
             ▼
Immutable EvidenceStore
             │
             ▼
RunManifest
Component 4 does not decide whether software should be released.
That remains the responsibility of Component 3.
Component 4 records what Component 3 decided and the evidence supporting that
decision.
