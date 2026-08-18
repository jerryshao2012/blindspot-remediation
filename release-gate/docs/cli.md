# CLI Contract

The installed console command is `release-gate`. It supports exactly three v1
subcommands: `init`, `validate`, and `run`.

## `init`

```text
release-gate init [--repo PATH] [--profile generic|python|node]
```

`--repo` defaults to the current directory and `--profile` to `generic`. The
command writes `.release-gate.yaml` from the matching built-in v1 example and
then validates it. It never overwrites an existing file; an existing target,
non-repository path, or write failure is exit 3. The operator must tailor and
commit the policy before `run`, because runs trust only base-revision policy.

## `validate`

```text
release-gate validate [--repo PATH] [--config PATH]
```

The default input is `<repo>/.release-gate.yaml`. This command performs YAML
parsing, JSON Schema 2020-12 validation, semantic validation, defaults, and
host-platform resolution without running repository commands. Success prints
the config version and check count. Validation diagnostics go to stderr, use
document paths, contain no traceback for expected errors, and exit 3.

`--config` is a convenience for validating an uncommitted file. It is not
accepted by `run` and cannot override trusted base policy.

## `run`

```text
release-gate run --base REF [--repo PATH] [--run-id ID]
                 [--evidence-root PATH]
```

`--repo` defaults to the current directory. `--base` is required and must
resolve to a local commit. `--run-id` defaults to a UTC timestamp plus random
suffix and is limited to portable filename characters. The default evidence
root is `<repo>/.release-gate/runs`; it is engine-owned and excluded from
candidate capture. An existing run directory is never overwritten.

Preflight resolves the base, reads `.release-gate.yaml` from it, validates the
policy, checks the source repository, and captures the working tree through a
temporary index. Invalid refs, invalid/missing policy, ambiguous input, patch
reconstruction failure, or an unsafe evidence path exit 3 before a candidate
verdict.

After capture, preflight compares `.release-gate.yaml` and every directly
invoked repository-local launcher with the base. Any candidate add, modify,
rename, or delete of the policy, or change to a covered launcher, is valid
candidate input but requires review: no configured preparation/check command
runs, all controls are recorded `SKIPPED`, a complete `NEEDS_HUMAN` result is
finalized, and the command exits 2. Policy scope and severity cannot weaken
this rule.

After preflight, expected check/tool/report failures are finalized in
`result.json` and map to a candidate verdict. Normal stdout ends with these
stable lines:

```text
VERDICT: PASS|FAIL|NEEDS_HUMAN
RESULT: <absolute-path-to-result.json>
```

Human-readable progress goes to stderr. Automation MUST consume `result.json`,
not parse progress text. The result is complete before the verdict lines are
printed.

## Exit codes

| Exit | Meaning | `result.json` guaranteed? |
|---:|---|---|
| 0 | Candidate verdict `PASS`. | Yes |
| 1 | Candidate verdict `FAIL`. | Yes |
| 2 | Candidate verdict `NEEDS_HUMAN`. | Yes |
| 3 | Invalid CLI usage, repository/input, or configuration before a candidate verdict. | No |
| 4 | Unrecoverable internal gate failure before complete evidence/result finalization. | No |

`NEEDS_HUMAN` outranks `FAIL`: if both conditions occur, the command exits 2.
Exit 4 is not a fourth verdict. If a partial run directory exists, it contains
a `.incomplete` marker and MUST NOT be consumed as an evidence package.

SIGINT, host shutdown, disk exhaustion, or an engine defect yields exit 4 when
the engine cannot finalize a complete result. If a check process is interrupted
but the engine remains able to record and finalize the event, it is an evidence
error and yields `NEEDS_HUMAN` instead.

## Compatibility

The new CLI does not replace or proxy `demo/gate/gate.sh`. Existing demo
commands and their 0/1/2 behavior remain intact. There is no A3 request-file,
execution-result, plugin, or adapter mode in v1.
