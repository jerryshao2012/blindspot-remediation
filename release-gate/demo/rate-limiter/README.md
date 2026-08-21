# Release Gate end-to-end demo: `rate-limiter`

This demo answers a concrete question: can Release Gate distinguish a safe
candidate, a behavioral regression, and a change to the policy that judges the
candidate?

The helper creates an isolated Git repository under `workbench/`. Release Gate
reconstructs separate base and candidate workspaces, records its verdict, and
only then runs an independent oracle. A complete automated run normally takes
10–20 minutes because every gate run installs dependencies in fresh workspaces.

## Choose a path

| Goal | Path |
|---|---|
| Verify the complete demo without Copilot | Follow [automated verification](#automated-verification). |
| See the assistant skill operate the gate | Follow [interactive Copilot CLI walkthrough](#interactive-copilot-cli-walkthrough). |
| Copilot CLI is blocked on your network | Use [VS Code Copilot Chat](#vs-code-copilot-chat). |

## 1. Prerequisites and one-time installation

You need Git, Python 3.12, `uv`, and Release Gate 0.3.0. The interactive
paths also require an authenticated GitHub Copilot CLI or VS Code Copilot Chat.

Run all installation commands from the root of `blindspot-remediation`. The
path is important because an unrelated package on PyPI is also named
`release-gate`.

### Windows PowerShell

```powershell
uv tool install --force .\release-gate
release-gate --version
copilot skill add .\release-gate\skills\release-gate
cd .\release-gate\demo\rate-limiter
```

### macOS zsh

```zsh
uv tool install --force ./release-gate
release-gate --version
copilot skill add ./release-gate/skills/release-gate
cd release-gate/demo/rate-limiter
```

The required version is:

```text
release-gate 0.3.0
```

Every helper command below uses `uv run --python 3.12`; Windows and macOS
therefore select the same interpreter instead of relying on `py` or `python3`.
The helper and Release Gate use `uv venv --python 3.12 --seed` and install the
pinned package set with `uv pip install`.

## Automated verification

This is the fastest way to test the demo itself. It creates the workbench,
proves that the independent oracle kills all eight scripted mutants, runs the
three Release Gate controls, grades their evidence, and resets the candidate.

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

Do not treat an earlier green line as completion. `verify` fails if setup, the
oracle, any gate result, or the final reset fails.

## Interactive Copilot CLI walkthrough

### 2. Check the host and create the trusted base

From `release-gate/demo/rate-limiter`:

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

Setup creates:

```text
workbench/
├── rate-limiter/   # independent candidate Git repository
└── task-venv/      # baseline verification environment
```

The committed policy is tagged `release-gate-rate-limiter-base`. Setup refuses
to overwrite an existing workbench.

#### Where pytest is installed

`setup` installs the pinned development tools, including pytest, inside
`workbench/task-venv`; it does not modify your global Python installation. From
the demo directory, use that interpreter if you want to run the generated
candidate tests directly:

```powershell
.\workbench\task-venv\Scripts\python.exe -m pytest .\workbench\rate-limiter\tests -q
```

```zsh
./workbench/task-venv/bin/python -m pytest ./workbench/rate-limiter/tests -q
```

If VS Code marks `import pytest` as unresolved, run **Python: Select Interpreter**
and select the same `workbench/task-venv` interpreter. A bare
host command such as `python -m pytest` can fail with “No module named pytest”
because the host interpreter is deliberately not used for demo dependencies.

### 3. Prepare a known candidate

Start with the PASS control:

```powershell
uv run --python 3.12 --no-project python demo.py control pass
cd workbench\rate-limiter
copilot
```

```zsh
uv run --python 3.12 --no-project python demo.py control pass
cd workbench/rate-limiter
copilot
```

The control changes only `README.md`. Review it with `/diff` before running the
gate.

### 4. Validate and run Release Gate

In the Copilot session, enter these commands exactly:

```text
/release-gate validate
/release-gate run --base release-gate-rate-limiter-base
```

Copilot must invoke the gate once, preserve the exact verdict, read the
produced `result.json`, and report its reason codes and evidence path. It must
not retry, edit evidence, merge, or deploy. Copy the absolute path printed
after `RESULT:` and exit Copilot.

### Direct CLI equivalent

From the demo directory, the non-assistant equivalent is:

```powershell
release-gate validate --repo .\workbench\rate-limiter
release-gate run --repo .\workbench\rate-limiter --base release-gate-rate-limiter-base
```

```zsh
release-gate validate --repo ./workbench/rate-limiter
release-gate run --repo ./workbench/rate-limiter --base release-gate-rate-limiter-base
```

Exit codes are 0 for `PASS`, 1 for `FAIL`, and 2 for `NEEDS_HUMAN`. Exit 3 or 4
is an operational error, not another verdict.

### 5. Inspect and grade the evidence

Return to `release-gate/demo/rate-limiter` and quote paths that contain spaces:

```powershell
uv run --python 3.12 --no-project python demo.py inspect --result "C:\absolute\path\to\result.json"
uv run --python 3.12 --no-project python demo.py grade --result "C:\absolute\path\to\result.json"
```

```zsh
uv run --python 3.12 --no-project python demo.py inspect --result "/absolute/path/to/result.json"
uv run --python 3.12 --no-project python demo.py grade --result "/absolute/path/to/result.json"
```

The oracle is outside the candidate repository and runs only after the verdict
exists. It does not change or retry the gate result.

| Gate | Oracle truth | Classification |
|---|---|---|
| PASS | correct | `good_pass` |
| PASS | wrong | `FALSE_RELEASE` |
| FAIL | correct | `FALSE_BLOCK` |
| FAIL | wrong | `good_catch` |
| NEEDS_HUMAN | either | `escalated` |
| any verdict | oracle unavailable | `oracle_error` |

`PASS` means the committed policy accepted this candidate. It is not a merge,
deployment, security attestation, or proof that no defect exists.

## 6. Demonstrate every verdict

Run each control from the demo directory, then invoke the same Release Gate
command against `release-gate-rate-limiter-base`.

| Control | Candidate change | Expected gate result | Expected grade |
|---|---|---|---|
| `pass` | Adds a README usage note | `PASS` | `good_pass` |
| `fail` | Expires a request at the exact boundary | `FAIL` | `good_catch` |
| `needs-human` | Changes `.release-gate.yaml` | `NEEDS_HUMAN` | `escalated` |

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

Each command resets first, so run the gate immediately after the selected
control. The FAIL control is caught by the deterministic exact-boundary test.
The NEEDS_HUMAN control produces `POLICY_FILE_CHANGED` and skips configured
checks because a candidate cannot change the policy that judges it.

## 7. Reset

```powershell
uv run --python 3.12 --no-project python demo.py reset
```

```zsh
uv run --python 3.12 --no-project python demo.py reset
```

Reset verifies ownership, the trusted tag, and the committed policy before it
changes the generated workbench. Completed evidence remains under
`workbench/rate-limiter/.release-gate/runs/`.

## What is tested

The portable `tools/gauntlet.py` runs scenario and property tests, coverage,
strict typing, Ruff lint/format checks, dependency auditing, must-not scans,
eight scripted mutants, and a real-clock example. `tools/gauntlet.sh` is only a
POSIX convenience wrapper. Release Gate invokes the Python entry point on both
Windows and macOS.

The hidden oracle independently compares the candidate with a brute-force
reference model across boundary, interleaved-key, denial, and backward-clock
sequences. It also checks invalid construction and denial storage. It is still
a repository-owned demo oracle, not an external certification.

## Troubleshooting

- **Workench already exists:** run `demo.py reset`; remove `workbench` only if
  setup stopped before creating a valid repository.
- **Wrong Release Gate version:** reinstall `./release-gate` from the repository
  root. Do not install the unrelated PyPI project.
- **Dependency preparation fails:** configure the approved package-index or
  corporate proxy, then create a new gate run. A missing check is not a pass.
- **Exit 3 or 4:** inspect stderr. A complete `result.json` is not guaranteed.
- **Evidence contains `.incomplete`:** do not consume that evidence package.
- **Copilot CLI cannot reach GitHub:** use VS Code Copilot Chat below. The direct
  CLI and `demo.py verify` do not require Copilot.

## VS Code Copilot Chat

After setup, copy the skill into the generated candidate. Repeat this after a
reset because `git clean` removes untracked files.

```powershell
New-Item -ItemType Directory -Force workbench\rate-limiter\.github\skills | Out-Null
Copy-Item -Recurse -Force ..\..\skills\release-gate workbench\rate-limiter\.github\skills\release-gate
code workbench\rate-limiter
```

```zsh
mkdir -p workbench/rate-limiter/.github/skills
cp -R ../../skills/release-gate workbench/rate-limiter/.github/skills/release-gate
code workbench/rate-limiter
```

In Copilot Chat Agent mode, ask:

```text
Use the release-gate skill to validate this repository.
Use the release-gate skill to run against base release-gate-rate-limiter-base.
```

Then continue with evidence inspection and grading exactly as above.
