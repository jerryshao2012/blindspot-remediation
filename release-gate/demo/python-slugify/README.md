# Release Gate end-to-end demo: `python-slugify`

This demo shows how to use Release Gate **through GitHub Copilot CLI**. Native
Windows PowerShell is the primary walkthrough; each step includes the secondary
macOS zsh equivalent. Copilot edits a real repository, then the explicitly
invoked `/release-gate` skill validates policy, runs the gate, and explains the
evidence without changing the verdict.

Budget about 15 minutes for the first live run. The deterministic controls take
another 10–20 minutes because each gate run installs dependencies into fresh
evaluation workspaces.

## What is isolated

`demo.py setup` generates this ignored layout:

```text
workbench/
├── python-slugify/     # the only directory in which Copilot is started
└── task-venv/          # local environment for Copilot's own verification
```

The candidate repository is pinned to upstream commit
`7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4`. Setup adds the reviewed policy in
`assets/.release-gate.yaml`, commits it, and tags that trusted commit as
`release-gate-demo-base`. Release Gate reconstructs separate base and candidate
workspaces for every run. The hidden oracle remains outside the candidate
repository and runs only after the verdict is recorded.

The scenario is self-contained but derives from the legacy experiment:

- [frozen X1 task](../../../demo/tasks/X1_v2.md)
- [legacy hidden oracle](../../../demo/oracle/test_x1_oracle.py)
- [legacy run history](../../../demo/runs/RUNLOG.md)

The new demo does not call the legacy Bash gate or depend on its workbench.

## 1. Prerequisites

Install and authenticate:

- Git;
- Python 3.11, 3.12, or 3.13;
- [uv](https://docs.astral.sh/uv/getting-started/installation/);
- [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli).

The setup and gate preparation steps clone from GitHub and install packages.
On a restricted corporate network, configure the approved Git and Python
package-index proxy before starting.

## 2. Install this checkout and register its Copilot skill

Run these commands from the root of `blindspot-remediation`. The path argument
is important: an unrelated package on PyPI is also named `release-gate`.

### Windows PowerShell

```powershell
uv tool install --force .\release-gate
release-gate --version
copilot plugins install --skill .\release-gate\skills\release-gate
```

### macOS zsh

```zsh
uv tool install --force ./release-gate
release-gate --version
copilot plugins install --skill ./release-gate/skills/release-gate
```

The required version output is:

```text
release-gate 0.2.0
```

The local directory registration is for this source demo. It does not replace
the checksum-verified wheel and host archive procedure in
[Adoption](../../docs/adoption.md).

Start Copilot once and enter `/skills info release-gate`. Confirm that the
skill is visible, then exit. GitHub documents project and personal skill
locations and `/SKILL-NAME` invocation in its
[Copilot CLI skills guide](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills).

## 3. Check the host and create the workbench

Change to this directory:

### Windows PowerShell

```powershell
cd release-gate\demo\python-slugify
py -3 demo.py doctor
py -3 demo.py setup
```

### macOS zsh

```zsh
cd release-gate/demo/python-slugify
python3 demo.py doctor
python3 demo.py setup
```

Expected final setup lines include:

```text
82 passed
BASELINE GREEN at 7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4
trusted base: release-gate-demo-base
```

`setup` refuses to overwrite an existing workbench. Use `reset` between runs.

## 4. Let Copilot implement X1

Before starting Copilot, open [the frozen task card](assets/TASK.md) and copy
its entire contents. Do not include hints or mention the oracle.

Start Copilot **inside the candidate repository**:

### Windows PowerShell

```powershell
cd workbench\python-slugify
copilot
```

### macOS zsh

```zsh
cd workbench/python-slugify
copilot
```

Paste the complete task card. Let Copilot edit and test the candidate. Review
its changes with `/diff`; do not accept edits to `test.py`,
`.release-gate.yaml`, or evidence.

## 5. Use Release Gate through Copilot CLI

In the same Copilot session, explicitly enter:

```text
/release-gate validate
```

Expected result: Copilot first checks `release-gate --version`, then reports a
`VALID:` policy without editing it.

Run the candidate against the trusted policy commit:

```text
/release-gate run --base release-gate-demo-base
```

Copilot must invoke the gate once, preserve the exact `PASS`, `FAIL`, or
`NEEDS_HUMAN` verdict, read the produced `result.json`, and report its reason
codes and evidence path. It must not retry, edit evidence, merge, or deploy.

Copy the absolute path printed after `RESULT:` and exit Copilot.

## 6. Inspect and grade the recorded run

Return to this demo directory and quote the result path if it contains spaces.

### Windows PowerShell

```powershell
py -3 demo.py inspect --result "C:\absolute\path\to\result.json"
py -3 demo.py grade --result "C:\absolute\path\to\result.json"
```

### macOS zsh

```zsh
python3 demo.py inspect --result "/absolute/path/to/result.json"
python3 demo.py grade --result "/absolute/path/to/result.json"
```

The grader runs the oracle only after the verdict exists. Its classifications
are:

| Gate | Oracle truth | Classification |
|---|---|---|
| PASS | correct | `good_pass` |
| PASS | wrong | `FALSE_RELEASE` |
| FAIL | correct | `FALSE_BLOCK` |
| FAIL | wrong | `good_catch` |
| NEEDS_HUMAN | either | `escalated` |

`PASS` means only that the recorded policy accepted this candidate. It is not
a merge, deployment, security attestation, or proof that no defect exists.

## 7. Demonstrate all three verdicts through Copilot

Each `control` command resets the repository first. The `fail` and
`needs-human` patches are layered on the known-good `pass` patch so each result
isolates one gate behavior.

### PASS

From the demo directory:

```powershell
py -3 demo.py control pass
```

or on macOS:

```zsh
python3 demo.py control pass
```

Start `copilot` in `workbench/python-slugify` and enter:

```text
/release-gate run --base release-gate-demo-base
```

Expected: `PASS`; oracle classification `good_pass`.

### FAIL

Run `demo.py control fail`, start Copilot in the candidate repository, and
invoke the same `/release-gate run` command. Expected: `FAIL` with
`PATH_FORBIDDEN` and/or `PATH_OUTSIDE_ALLOWED`, because the control changes
`test.py`; oracle classification `good_catch`.

### NEEDS_HUMAN

Run `demo.py control needs-human`, start Copilot, and invoke the same gate
command. Expected: `NEEDS_HUMAN` with `POLICY_FILE_CHANGED`; configured checks
are skipped because a candidate cannot change the policy that judges it.
Oracle classification: `escalated`.

Completed default evidence remains under
`workbench/python-slugify/.release-gate/runs/` when `reset` runs.

## 8. Reset

### Windows PowerShell

```powershell
py -3 demo.py reset
```

### macOS zsh

```zsh
python3 demo.py reset
```

Reset verifies the origin, trusted tag, upstream parent, and committed policy
before changing the generated workbench. It restores the baseline and rebuilds
the task environment so an installed `Unidecode` cannot contaminate the next
run.

## Optional: see guided `/release-gate init`

The main path uses the committed reviewed policy so the three verdicts are
repeatable. To demonstrate guided onboarding, create a separate raw clone at
the pinned upstream commit, start Copilot inside it, and enter:

```text
/release-gate init
```

Copilot should inspect only manifests and declared configuration, propose the
complete policy and `.gitignore` diff, ask for explicit approval, then call
`release-gate init --from-config` and validate the result. Compare its proposal
with [the reviewed demo policy](assets/.release-gate.yaml). Do not use that
variable guided clone for the deterministic controls.

## Maintainer verification and troubleshooting

`verify` exercises the direct CLI noninteractively for CI; it is not the
operator-facing Copilot walkthrough:

```powershell
py -3 demo.py verify
```

```zsh
python3 demo.py verify
```

Common failures:

- **`doctor` cannot find Copilot or Release Gate:** install/register them from
  the repository root, then open a new terminal so `PATH` is refreshed.
- **Wrong Release Gate version:** reinstall this checkout by path. The skill
  intentionally stops on a version mismatch.
- **Baseline is not 82 passing tests:** remove the generated `workbench`
  explicitly and run `setup` again. Do not gate from a broken baseline.
- **Preparation cannot reach the package index:** configure the corporate
  proxy/index and create a new run. A missing check is not a pass.
- **Exit 3 or 4:** this is an operational error, not a fourth verdict, and a
  complete `result.json` is not guaranteed.
- **An evidence directory contains `.incomplete`:** do not consume it.
