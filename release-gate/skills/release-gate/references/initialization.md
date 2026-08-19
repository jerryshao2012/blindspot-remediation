# Guided initialization reference

Read this file and `config-v1.schema.json` before proposing a policy. The JSON
Schema is the exact CLI v1 schema and is authoritative for field shapes,
limits, enums, and defaults. The CLI also applies semantic validation described
below. Do not guess a value or invent a field when repository data and the
user's explicit decisions do not determine it.

## Required shape

Every policy requires `version: 1`, a `scope` with at least one
`allowed_paths` pattern, and at least one item under `checks:`. Every check
requires an `id`, `mode`, `severity`, and non-empty `argv:` array. Commands are
argv arrays passed directly to a process without a shell; never render a shell
string, operators, expansion, or implicit quoting.

This is a structural example, not a command recommendation. Replace every
placeholder only with a user-approved value supported by a cited manifest, CI
file, or declared script:

```yaml
version: 1
scope:
  allowed_paths: ["<approved-pattern>"]
  forbidden_paths: []
  review_required_paths: ["/.release-gate.yaml"]
checks:
  - id: approved-check
    mode: candidate
    severity: blocking
    argv: ["<approved-executable>", "<approved-argument>"]
    cwd: "."
    timeout: 600
    inherit_environment: []
    exit_classes:
      pass: [0]
      fail: [1]
      error: []
```

`prepare` is optional. Include it only when the user approves preparation; each
step requires `id` and `argv` and accepts the same command fields as a check.
Do not infer dependency installation from a lockfile. A preparation failure or
error produces `NEEDS_HUMAN` and stops later execution.

## Decision mapping

- Command inclusion and complete argv -> one `checks` item, or one `prepare`
  item when the user explicitly classifies it as preparation. Cite the source
  file and key beside the proposal, but do not put citations in the YAML.
- Candidate/differential choice -> `mode: candidate` runs only the candidate;
  `mode: differential` runs base and candidate and detects candidate
  regressions. Do not choose between them without approval.
- Severity -> exactly `blocking`, `advisory`, or `informational`. Blocking
  ordinary failure yields `FAIL`; advisory ordinary failure yields
  `NEEDS_HUMAN`; informational ordinary failure is recorded. Errors yield
  `NEEDS_HUMAN` for every severity.
- Scope -> required `scope.allowed_paths`; optional `forbidden_paths` and
  `review_required_paths`. Patterns are repository-relative Git-wildmatch
  patterns under the schema's closed grammar. Ask for all three lists.
- Inherited environment names -> `inherit_environment`. No host variable is
  inherited implicitly. Record approved names only and never read their values.
  Omit literal `environment` unless the user explicitly supplies each value.
- Preparation/network behavior -> inclusion and argv of `prepare` and checks.
  V1 has no `network` field and does not sandbox network access. If network is
  disallowed, omit network-dependent preparation or use only an explicitly
  approved offline argv supported by its cited source; do not invent a flag.

Optional `cwd`, `timeout`, `environment`, `inherit_environment`, `exit_classes`,
`platform`, `reports`, `assertions`, and `limits` must follow the exact bundled
schema. IDs must be portable lowercase identifiers, preparation/check IDs must
be globally unique, report IDs unique per check, exit classes disjoint, and
assertion comparison must be compatible with check mode. Every field in the
rendered YAML must validate against both the bundled schema and CLI semantic
rules before it is shown for approval.
