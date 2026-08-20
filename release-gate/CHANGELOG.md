# Changelog

All notable changes to the standalone Release Gate are recorded here.

## 0.3.0

- Refresh a self-contained, non-gating rolling 10/100 gate-decision dashboard
  after each finalized `PASS`, `FAIL`, or `NEEDS_HUMAN` run.
- Add tamper-evident per-run HTML snapshots, mutable stable JSON/HTML reports,
  bounded history reconciliation, and hardened atomic publication.
- Bundle the decision-report schema with both the wheel and portable skill,
  and extend host qualification for report validation and refresh warnings.

## 0.2.3

- Add an optional, read-only Graphify advisory after exact CLI compatibility
  preflight without changing Release Gate policy, verdict, or runtime APIs.
- Document a checksum-first paired upgrade and rollback procedure for every
  supported assistant host.

## 0.2.2

- Retry evidence-file finalization after transient Windows sharing violations
  and support Windows hosts without `os.fchmod`.

## 0.2.1

- Fix isolated candidate capture when an ignored `.release-gate/runs/`
  directory already exists.

## 0.2.0

The release lifecycle qualifies `release-gate-v0.2.0-rc.1` on every advertised
assistant surface before byte-identical final promotion to
`release-gate-v0.2.0`. The GitHub release page is authoritative for publication
state, assets, and checksums; this changelog describes the version without
asserting which lifecycle stage it has reached.

- Add an explicit `init`, `validate`, and `run` skill interface for GitHub
  Copilot, Codex, Claude Code, and Antigravity.
- Add deterministic, assistant-specific skill archives paired with the exact
  0.2.0 CLI wheel.
- Add `release-gate --version`, approved-configuration initialization, and a
  required `run --base` argument.
- Document pinned installation, checksums, trust boundaries, upgrades,
  uninstall, and rollback.

## 0.1.0 — 2026-08-18

Status: initial repository implementation; not published to PyPI.

- Introduce the independent Python CLI, versioned policy and evidence schemas,
  three-way verdict engine, evidence finalization, and the first portable
  run-oriented skill.
