# Release Gate end-to-end demo: `python-slugify`

This demo lets an assistant implement a real maintenance task, then asks
Release Gate to judge the candidate against a reviewed policy and trusted Git
base. The gate records its verdict before an external oracle grades whether the
candidate is actually correct.

Budget about 15 minutes for one interactive run. The automated three-verdict
verification normally takes another 10–20 minutes because each gate run
installs dependencies in fresh evaluation workspaces.

## Choose a path

| Goal | Path |
|---|---|
| Verify setup and all three verdict controls | Follow [automated verification](#automated-verification). |
| Let GitHub Copilot CLI implement and gate X1 | Follow [interactive Copilot CLI walkthrough](#interactive-copilot-cli-walkthrough). |
| Copilot CLI is blocked by your network | Use [VS Code Copilot Chat](#vs-code-copilot-chat). |
| Demonstrate policy generation instead of the fixed experiment | See [guided initialization](#optional-guided-initialization). |

## 1. Prerequisites and one-time installation

Install Git, Python 3.12, `uv`, and GitHub Copilot CLI. Authenticate
Copilot before the live walkthrough. Setup clones GitHub and installs Python
packages, so configure your approved proxy or package index on restricted
networks.

Run these commands from the root of `blindspot-remediation`. The path is
important because an unrelated package on PyPI is also named `release-gate`.

### Windows PowerShell

```powershell
uv tool install --force .\release-gate
release-gate --version
copilot skill add .\release-gate\skills\release-gate
cd .\release-gate\demo\python-slugify
```

### macOS zsh

```zsh
uv tool install --force ./release-gate
release-gate --version
copilot skill add ./release-gate/skills/release-gate
cd release-gate/demo/python-slugify
```

The required version is:

<!-- release-version-sync:start -->
```text
release-gate 0.4.0
```
<!-- release-version-sync:end -->

Every helper command below uses `uv run --python 3.12`; Windows and macOS
therefore select the same interpreter instead of relying on `py` or `python3`.
The helper and Release Gate also use `uv venv --python 3.12 --seed` followed by
`uv pip install`. The reviewed setuptools and wheel versions are installed
before the project, so package building never depends on a global toolchain.

Optionally start Copilot once and enter `/skills info release-gate` to confirm
that the skill is registered, then exit.

## Automated verification

This path does not use Copilot. It creates or validates the workbench, applies
the known PASS, FAIL, and NEEDS_HUMAN candidates, invokes the direct Release
Gate CLI, grades every result with the hidden oracle, and resets safely.

### Windows PowerShell

```powershell
uv run --python 3.12 --no-project python demo.py verify
```

### macOS zsh

```zsh
uv run --python 3.12 --no-project python demo.py verify
```

The final line must be:

```text
verify: PASS, FAIL, and NEEDS_HUMAN controls matched expectations
```

Do not treat an earlier green line as completion. `verify` fails if setup, a
gate result, oracle grading, or the final reset fails.

## Interactive Copilot CLI walkthrough

### 2. Check the host and create the trusted base

Run from `release-gate/demo/python-slugify`:

#### Windows PowerShell

```powershell
uv run --python 3.12 --no-project python demo.py doctor
uv run --python 3.12 --no-project python demo.py setup
```

#### macOS zsh

```zsh
uv run --python 3.12 --no-project python demo.py doctor
uv run --python 3.12 --no-project python demo.py setup
```

Expected final setup output includes:

```text
82 passed
BASELINE GREEN at 7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4
trusted base: release-gate-demo-base
```

Setup creates this ignored layout:

```text
workbench/
├── python-slugify/   # the only directory in which Copilot is started
└── task-venv/        # local candidate-verification environment
```

The candidate is pinned to upstream commit
`7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4`. Setup commits the reviewed
policy and tags that commit `release-gate-demo-base`. It refuses to overwrite
an existing workbench.

### 3. Let Copilot implement X1

Open [the complete frozen task card](assets/TASK.md) and copy all of it. Do not
include hints or mention the oracle.

Start Copilot inside the generated candidate repository:

```powershell
cd workbench\python-slugify
copilot
```

```zsh
cd workbench/python-slugify
copilot
```

Paste the task card and let Copilot edit and test the candidate. Review `/diff`.
Do not accept changes to `test.py`, `.release-gate.yaml`, or evidence.

### 4. Validate and run Release Gate

In the same Copilot session, enter:

```text
/release-gate validate
/release-gate run --base release-gate-demo-base
```

Copilot must invoke the gate once, preserve the exact verdict, read the
produced `result.json`, and report its reason codes and evidence path. It must
not retry, edit evidence, merge, or deploy. Copy the absolute path printed
after `RESULT:` and exit Copilot.

### Direct CLI equivalent

From the demo directory:

```powershell
release-gate validate --repo .\workbench\python-slugify
release-gate run --repo .\workbench\python-slugify --base release-gate-demo-base
```

```zsh
release-gate validate --repo ./workbench/python-slugify
release-gate run --repo ./workbench/python-slugify --base release-gate-demo-base
```

Exit codes are 0 for `PASS`, 1 for `FAIL`, and 2 for `NEEDS_HUMAN`. Exit 3 or 4
is an operational error, not another verdict.

### 5. Inspect and grade the recorded run

Return to `release-gate/demo/python-slugify` and quote paths containing spaces:

```powershell
uv run --python 3.12 --no-project python demo.py inspect --result "C:\absolute\path\to\result.json"
uv run --python 3.12 --no-project python demo.py grade --result "C:\absolute\path\to\result.json"
```

```zsh
uv run --python 3.12 --no-project python demo.py inspect --result "/absolute/path/to/result.json"
uv run --python 3.12 --no-project python demo.py grade --result "/absolute/path/to/result.json"
```

The hidden oracle remains outside the candidate repository and runs only after
the verdict exists. It cannot change or retry that verdict.

| Gate | Oracle truth | Classification |
|---|---|---|
| PASS | correct | `good_pass` |
| PASS | wrong | `FALSE_RELEASE` |
| FAIL | correct | `FALSE_BLOCK` |
| FAIL | wrong | `good_catch` |
| NEEDS_HUMAN | either | `escalated` |

`PASS` means only that the recorded policy accepted this candidate. It is not
a merge, deployment, security attestation, or proof that no defect exists.

## 6. Demonstrate every verdict

Each control resets first and then creates one known candidate. Run the gate
immediately after selecting a control.

| Control | Expected gate result | Expected grade | Important evidence |
|---|---|---|---|
| `pass` | `PASS` | `good_pass` | Only the reviewed X1 files changed. |
| `fail` | `FAIL` | `good_catch` | `test.py` is forbidden and outside allowed scope. |
| `needs-human` | `NEEDS_HUMAN` | `escalated` | `POLICY_FILE_CHANGED`; configured checks are skipped. |

```powershell
uv run --python 3.12 --no-project python demo.py control pass
uv run --python 3.12 --no-project python demo.py control fail
uv run --python 3.12 --no-project python demo.py control needs-human
```

```zsh
uv run --python 3.12 --no-project python demo.py control pass
uv run --python 3.12 --no-project python demo.py control fail
uv run --python 3.12 --no-project python demo.py control needs-human
```

The PASS candidate changes `README.md`, `setup.py`, `slugify/slugify.py`, and
`tox.ini`. The FAIL candidate adds `test.py`; inspection reports
`outside allowed: test.py` and `forbidden: test.py`. The NEEDS_HUMAN candidate
adds `.release-gate.yaml`; inspection reports
`review required: .release-gate.yaml`.

On Windows, set a short temporary directory before the PASS control if your
profile path is long:

```powershell
New-Item -ItemType Directory -Force C:\rg-temp | Out-Null
$env:TEMP = "C:\rg-temp"
$env:TMP = "C:\rg-temp"
```

## 7. Reset

```powershell
uv run --python 3.12 --no-project python demo.py reset
```

```zsh
uv run --python 3.12 --no-project python demo.py reset
```

Reset verifies the origin, trusted tag, pinned upstream parent, and committed
policy before changing the generated workbench. It rebuilds the task
environment so a prior dependency cannot contaminate the next run. Completed
evidence remains under `workbench/python-slugify/.release-gate/runs/`.

## What is isolated and what is measured

Release Gate reconstructs independent base and candidate workspaces for every
run. The candidate cannot edit the policy at the trusted base, the hidden
oracle, or completed evidence. The scenario derives from:

- [frozen X1 task](../../../demo/tasks/X1_v2.md)
- [legacy hidden oracle](../../../demo/oracle/test_x1_oracle.py)
- [legacy run history](../../../demo/runs/RUNLOG.md)

The new demo does not call the legacy Bash gate or depend on its workbench.
Repeated X1 trials measure X1 repeatability, not universal model reliability.

## Optional: guided initialization

The repeatable walkthrough uses a committed reviewed policy. To demonstrate
onboarding, create a separate raw clone at the pinned upstream commit, start
Copilot inside it, and enter:

```text
/release-gate init
```

Copilot should inspect manifests and declared configuration, propose the full
policy and `.gitignore` diff, and ask for an assurance map. For every
failure mode or assurance claim, it must cite the repository command or report, ask
whether it runs in candidate or differential mode, record severity and known
limitations, and classify omitted layers as `N-A`, `UNAVAILABLE`, or
`SUBSTITUTED`. It must ask for approval, call
`release-gate init --from-config`, and validate the result. Compare it with
[the reviewed demo policy](assets/.release-gate.yaml). Do not use this variable
clone for deterministic controls.

## Troubleshooting

- **Doctor cannot find Copilot or Release Gate:** repeat the one-time install
  from the repository root, then open a new terminal.
- **Wrong Release Gate version:** reinstall this checkout by path. The skill
  intentionally stops on a version mismatch.
- **Baseline is not 82 passing tests:** remove the generated workbench
  explicitly and run setup again. Do not gate from a broken baseline.
- **`PREPARATION_FAILED` on the PASS control:** inspect `result.json`. If scope
  passed and only the four expected files changed, dependency preparation—not
  the candidate patch—failed. On Windows, use `C:\rg-temp` as shown above.
- **Exit 3 or 4:** this is an operational error; a complete `result.json` is not
  guaranteed.
- **Evidence contains `.incomplete`:** do not consume that evidence package.
- **`release-gate.exe` is blocked:** endpoint security may reject the shim.
  `demo.py` prefers the sibling interpreter with `python -m release_gate`, but
  Copilot calls the executable directly and may require an allow-list exception.

### Corporate proxy settings

Configure only organization-approved values. A typical PowerShell setup is:

```powershell
$env:HTTP_PROXY = "http://proxy.example:8080/"
$env:HTTPS_PROXY = $env:HTTP_PROXY
$env:NO_PROXY = "localhost,127.0.0.1"
$env:UV_SYSTEM_CERTS = "true"
$env:UV_LINK_MODE = "copy"
```

These variables help `demo.py setup`, which runs in the operator environment.
The committed deterministic gate policy inherits only executable-discovery
variables: Release Gate treats every requested inherited variable as mandatory,
so listing optional proxy variables would make direct-network hosts stop with
`INHERITED_ENVIRONMENT_MISSING`. If isolated gate preparation requires a proxy,
use your organization's approved non-secret system/package-index configuration
or review and commit a separate policy for that environment; do not alter the
trusted deterministic control policy in place.

If Copilot CLI returns a proxy 403, test the documented GitHub endpoints with
`curl.exe` and request the required allow-list from IT. Local files cannot
replace Copilot's network connection. Use VS Code Copilot Chat if it is already
approved and connected in your environment.

## VS Code Copilot Chat

Use this path instead of the Copilot CLI portions of steps 3 and 4. Setup,
inspection, grading, controls, and reset remain unchanged.

After setup, copy the skill into the generated candidate. Repeat this after
every reset because `git clean` removes untracked files.

```powershell
New-Item -ItemType Directory -Force workbench\python-slugify\.github\skills | Out-Null
Copy-Item -Recurse -Force ..\..\skills\release-gate workbench\python-slugify\.github\skills\release-gate
code workbench\python-slugify
```

```zsh
mkdir -p workbench/python-slugify/.github/skills
cp -R ../../skills/release-gate workbench/python-slugify/.github/skills/release-gate
code workbench/python-slugify
```

Open Copilot Chat in Agent mode, paste the complete
[task card](assets/TASK.md), and review the candidate in Source Control. Then
ask:

```text
Use the release-gate skill to validate this repository.
Use the release-gate skill to run against base release-gate-demo-base.
```

Copy the `RESULT:` path and continue with inspection and grading.
