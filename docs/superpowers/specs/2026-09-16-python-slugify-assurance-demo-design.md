# Python Slugify Conceptual Diversity Demo Design

## Goal

Upgrade the executable `python-slugify` demo to exercise Release Gate 0.7.0's
conceptual diversity assessment. The demo must install a reviewed assurance
policy into the trusted base, run `release-gate assure`, inspect the separate
assurance result, and preserve the existing hidden-oracle comparison.

The example starts in advisory mode. It demonstrates measured conceptual
coverage without claiming exhaustive test semantics or enabling enforcement
before the reviewed mappings have been validated in practice.

## Trusted policy

Add `release-gate/demo/python-slugify/assets/.release-gate-assurance.yaml`.
Setup copies this file into the generated repository alongside
`.release-gate.yaml`, commits both policies, and then creates
`release-gate-demo-base`. Workbench validation compares both Git blobs with
their checked-in assets byte-for-byte.

The assurance policy defines one stable dimension, `behavior_region`, with the
values `transliteration`, `unicode`, `boundary`, `customization`, and
`cli_contract`. It maps these exact candidate-side JUnit identities:

| Region | Suite | Classname | Case |
|---|---|---|---|
| `transliteration` | `pytest` | `test.TestSlugify` | `test_cyrillic_text` |
| `unicode` | `pytest` | `test.TestSlugifyUnicode` | `test_emojis` |
| `boundary` | `pytest` | `test.TestSlugify` | `test_max_length_cutoff_not_required` |
| `customization` | `pytest` | `test.TestSlugify` | `test_replacements_german_umlaut_custom` |
| `cli_contract` | `pytest` | `test.TestCommandParams` | `test_two_text_sources_fails` |

Every selector uses check `tests-and-coverage` and report `junit`. Every mapping
records source `test.py` with reviewed SHA-256
`5262916dbabb42b0d63b7c3eaa200aa435e8bb6d888287a048ed649eb29d91b1`.
All five mappings use the conservative independence group
`upstream-test.py`, because they share one source file and suite lineage.

Each of the five regions requires one independent support. The maximum mapping
uncertainty rate is `0.95`, explicitly allowing the unmapped remainder of the
82-case JUnit report plus the unmapped check-level artifacts. The passing
control must remain at or below that limit; the test suite records the actual
rate so future evidence-shape changes fail visibly. The policy does not infer
concepts from test names and does not describe unmapped cases as coverage.

## Demo runner

Extend `demo.py` with an `AssuranceSummary` parser for the separate version-1
assurance result. It validates the mode, deterministic gate verdict, final
disposition, assessment status, evidence-sufficiency flag, reason codes,
linked gate-result path, coverage, and unmet requirements.

Add an `inspect-assurance --result <path>` command. It confirms that the
assurance package contains a manifest, prints the assessment fields and
diagnostics, and returns the linked deterministic result so the existing gate
inspection and oracle grading continue to operate on their original contract.

Change automated verification to invoke this command once per scenario:

```text
release-gate assure --repo <workbench-repository> \
  --base release-gate-demo-base \
  --output <workbench/evidence> \
  --run-id verify-<scenario>-<suffix>
```

The CLI's single `RESULT:` line is the assurance `result.json`, located under
`<output>/_assurance/<run-id>/result.json`. The deterministic result is read
only from the assurance result's absolute `gate_result_path`; the demo never
guesses its sibling location. Automated verification checks these outcomes:

| Scenario | Gate verdict | Assessment status | Advisory disposition |
|---|---|---|---|
| pass | `PASS` | `COMPLETE` | `PASS` |
| fail | `FAIL` | `NOT_EVALUATED` | `FAIL` |
| needs-human | `NEEDS_HUMAN` | `NOT_EVALUATED` | `NEEDS_HUMAN` |

For the passing scenario, verification also checks that the required regions
are satisfied and that the recorded uncertainty stays within the reviewed
limit. For non-passing deterministic verdicts, it checks that no conceptual
assessment was claimed. Oracle grading follows `gate_result_path` from the
assurance result and retains the existing classification logic.

## Documentation

Update the README paths to use `assure --base release-gate-demo-base`. Explain
the two outputs, `GATE_VERDICT` and `ASSURANCE_DISPOSITION`, and direct users to
the assurance result rather than treating the deterministic result as the
final enforced decision.

Document the reviewed mappings, source-hash protection, independence groups,
unmapped evidence, uncertainty, and the advisory limitation. Enabling
enforcement requires changing `mode` in the reviewed base policy, validating
the mappings and required regions, committing that policy change, and using
the `assure` exit code in CI.

The hidden oracle remains benchmark-only and outside the candidate repository.
It measures correctness after the decision and cannot contribute conceptual
support.

## Testing

Use test-first development for:

- assurance-policy parsing and its reviewed source hash;
- parser rejection of malformed assurance results;
- assurance inspection output and linked gate-result handling;
- setup and trusted-base validation of both policy files;
- README commands and interpretation guidance;
- automated PASS, FAIL, and NEEDS_HUMAN assurance expectations.

Run the focused demo tests, assurance tests, release metadata/version checks,
formatting, and type checks. The unit suite mocks command execution to verify
the three-scenario orchestration without network access. The live
`demo.py verify` remains an explicit qualification/manual check because setup
clones GitHub and installs dependencies; it may be skipped only when those
network operations are unavailable, and the skipped live check must be
reported rather than described as passing.

## Boundaries

This change does not map every upstream case, generate mappings, acquire new
evidence, modify the mapper engine, or publish/qualify a release. The demo does
not enable enforcement by default.
