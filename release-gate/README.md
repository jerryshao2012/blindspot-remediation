# Release Gate

This directory is the canonical specification for a new, standalone release
gate. The gate independently reconstructs a repository change, runs
repository-owned checks, preserves evidence, and returns exactly one verdict:
`PASS`, `FAIL`, or `NEEDS_HUMAN`.

The v1 product is an independent Python 3.11+ CLI and a thin portable skill.
It does not import any A-series or B-series package. It runs configured
commands directly on a trusted host; it is not a sandbox and must not be used
for hostile repositories or patches.

This specification intentionally precedes production code. The JSON Schemas
and examples in this directory are the versioned v1 contract from which the
implementation will be built.

## Contract map

- [Design](docs/design.md): architecture, reconstruction, execution, and
  verdict rules.
- [Configuration](docs/configuration.md): `.release-gate.yaml` fields and
  evaluation semantics.
- [CLI](docs/cli.md): `init`, `validate`, `run`, output, and exit codes.
- [Evidence](docs/evidence.md): artifact layout, stable result, manifest, and
  size budgets.
- [Security](docs/security.md): trust boundary and operational safeguards.
- [Adoption](docs/adoption.md): repository onboarding and legacy coexistence.
- [Implementation plan](docs/implementation-plan.md): TDD-first delivery and
  cross-platform verification checklist.
- [Schemas](schemas): JSON Schema 2020-12 contracts for configuration, result,
  and manifest documents.
- [Examples](examples): generic, Python, and Node configurations.

## Normative terms

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative. When prose and a schema
disagree, the schema controls document shape and the prose controls runtime
semantics. A future incompatible change requires a new schema version; v1
files are not silently reinterpreted.

## Verdicts

| Verdict | Exit | Meaning |
|---|---:|---|
| `PASS` | 0 | Every verdict-contributing check completed and policy accepted the candidate. |
| `FAIL` | 1 | Complete evidence proves at least one blocking policy violation. |
| `NEEDS_HUMAN` | 2 | Required evidence is unavailable or policy explicitly requires review. |

`NEEDS_HUMAN` outranks `FAIL`. Invalid usage, input, or configuration before a
candidate verdict exits 3. An unrecoverable internal failure before complete
result/evidence finalization exits 4.

`PASS` means eligible under the recorded gate policy. The gate neither performs
nor authorizes a merge or deployment. It is not a security attestation or
proof that the software is defect free.

## Existing demo

`demo/gate/gate.sh` and `demo/gate/SKILL.md` are the unchanged legacy X1 demo.
Their documented commands remain valid. They are neither the implementation
nor the configuration of this standalone product. Canonical reusable-gate
documentation lives only under `release-gate/`.
