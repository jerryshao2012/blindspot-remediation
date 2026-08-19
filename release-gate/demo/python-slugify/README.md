# Release Gate end-to-end demo: `python-slugify`

This demo shows how to use Release Gate **through GitHub Copilot CLI**. Native
Windows PowerShell is the primary walkthrough; each step includes the secondary
macOS zsh equivalent. Copilot edits a real repository, then the explicitly
invoked `/release-gate` skill validates policy, runs the gate, and explains the
evidence without changing the verdict.

If Copilot CLI cannot reach GitHub on your network (see
[Troubleshooting: Copilot CLI blocked by corporate firewall](#maintainer-verification-and-troubleshooting)),
use [VS Code Copilot Chat instead](#appendix-driving-the-demo-with-vs-code-copilot-chat).
Steps 3, 6, 7 (setup, inspect/grade, reset) are unaffected either way — they
run through `demo.py`, not Copilot.

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

```shell
uv --version
uv 0.11.16 (135a36367 2026-05-21 x86_64-pc-windows-msvc)

python --version
Python 3.12.3

git --version
git version 2.39.2.windows.1

copilot --version
GitHub Copilot CLI 1.0.80.
Run 'copilot update' to check for updates.
```

## 2. Install this checkout and register its Copilot skill

Run these commands from the root of `blindspot-remediation`. The path argument
is important: an unrelated package on PyPI is also named `release-gate`.

### Windows PowerShell

You will need to setup corporate proxy settings if your network restricts GitHub or PyPI access. Then run `uv sync` in `blindspot-remediation\release-gate` to ensure you have the latest version of `uv` and its dependencies. After that, execute the following commands:

```powershell
uv tool install --force .
release-gate --version
copilot skill add .\release-gate\skills\release-gate
```

### macOS zsh

```zsh
uv tool install --force ./release-gate
release-gate --version
copilot skill add ./release-gate/skills/release-gate
```

The required version output is:

<!-- release-version-sync:start -->
```text
release-gate 0.2.3
```
<!-- release-version-sync:end -->

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
cd .\demo\python-slugify
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
INITIALIZED: your_path_to\.release-gate.yaml
........................................................................ [ 87%]
..........                                                               [100%]
82 passed in 0.57s
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
python -m venv .release-gate-venv
.\.release-gate-venv\Scripts\activate
pip install --disable-pip-version-check --no-build-isolation . pytest==8.4.2 pytest-cov==6.3.0 mypy==1.20.2
copilot

# deactivate; Remove-Item -Recurse -Force .release-gate-venv;
```

### macOS zsh

```zsh
cd workbench/python-slugify
python3 -m venv .release-gate-venv
source .release-gate-venv/bin/activate
pip install --disable-pip-version-check --no-build-isolation . pytest==8.4.2 pytest-cov==6.3.0 mypy==1.20.2
copilot
```

Note: fix corporate proxy settings if pip install fails. The `--no-build-isolation` flag is required because the `python-slugify` package does not declare its build dependencies in `pyproject.toml`.

Paste [the complete task card](assets/TASK.md). Let Copilot edit and test the candidate. Review
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
- **`release-gate.exe` is blocked by corporate policy (`OSError: [WinError 6] The
  handle is invalid`):** endpoint security killed the freshly spawned process.
  `demo.py` now runs `python -m release_gate` via the interpreter next to the
  shim instead of the shim itself, which works if `python.exe` is trusted even
  when the custom-named exe is not. Still request an allow-list exception for
  `release-gate.exe` from your security team for `copilot skill` invocations,
  which call the exe directly.
- Coporate proxy settings:
  ```shell
$username = [uri]::EscapeDataString("office\your_username")
$password = [uri]::EscapeDataString("your_password")
$proxy  = "http://${username}:${password}@ebcswg.bmogc.net:8080/"     
$env:HTTP_PROXY = $proxy
$env:HTTPS_PROXY = $proxy
$env:ALL_PROXY = $proxy
$env:http_proxy = $proxy
$env:https_proxy = $proxy
$env:all_proxy = $proxy
$env:NO_PROXY = "localhost,127.0.0.1"
$env:UV_SYSTEM_CERTS = "true"
$env:UV_LINK_MODE="copy"

uv sync
.\.venv\Scripts\activate
  ```

- **Copilot CLI fails with `ProxyResponseError: HTTP 403 response does not
  appear to originate from GitHub` (`https://gh.io/copilot-firewall`):** this
  is Copilot CLI itself failing to reach GitHub's Copilot API through the
  corporate proxy, not the demo's git clone step — local files cannot work
  around it because Copilot needs live network access to run at all. Diagnose
  with `curl.exe`, not the `curl` alias (which is `Invoke-WebRequest` in
  PowerShell and does not accept `--verbose`/`-x`):
  ```powershell
  curl.exe --verbose https://copilot-proxy.githubusercontent.com/_ping
  curl.exe --verbose -x $env:HTTPS_PROXY -i https://api.githubcopilot.com/_ping
  ```
  A 200 response means the connection works. If the request only succeeds
  with `--insecure` added, the corporate proxy is intercepting TLS and
  Copilot doesn't trust its certificate; install the corporate root CA into
  the Windows trust store (Copilot CLI reads it automatically via `win-ca`).
  If the proxied request returns `403 Forbidden` with an HTML body from your
  proxy (not GitHub), the proxy is blocking the domain by category (for
  example, "Generative AI"), not by certificate — request an allow-list
  exception from IT for `api.githubcopilot.com` and the other domains in the
  [Copilot allowlist reference](https://gh.io/copilot-firewall). Until that
  exception is granted, use
  [VS Code Copilot Chat instead](#appendix-driving-the-demo-with-vs-code-copilot-chat).

## Appendix: driving the demo with VS Code Copilot Chat

Use this appendix in place of steps 4 and 5 if Copilot CLI cannot reach
GitHub on your network. VS Code's Copilot Chat authenticates and connects
independently of the CLI, so it can work even while `copilot` is blocked.
Steps 3 (setup), 6 (inspect/grade), and 8 (reset) are unchanged — run them
from a terminal exactly as written above.

### A. Register the skill for VS Code

VS Code Copilot Chat discovers project skills from `.github/skills`. Copy
the skill into the candidate repository once, after `demo.py setup` has
created it. Run this from **this demo directory**
(`release-gate/demo/python-slugify`), the same directory used in step 3:

#### Windows PowerShell

```powershell
Copy-Item -Recurse -Force `
  ..\..\skills\release-gate `
  workbench\python-slugify\.github\skills\release-gate
```

#### macOS zsh

```zsh
mkdir -p workbench/python-slugify/.github/skills
cp -R ../../skills/release-gate workbench/python-slugify/.github/skills/release-gate
```

`demo.py reset` and `demo.py control` run `git clean`, which removes
untracked files, so repeat this copy after every `reset`.

### B. Let Copilot implement X1

Open the candidate repository as its own VS Code window:

```powershell
code workbench\python-slugify
```

Open the Copilot Chat view, switch to **Agent** mode, and paste the complete
contents of [the frozen task card](assets/TASK.md) — the same card used for
the CLI walkthrough, with no hints and no mention of the oracle. Let the
agent edit and test the candidate. Review its changes in the **Source
Control** view; do not stage or accept edits to `test.py`,
`.release-gate.yaml`, or evidence.

### C. Use Release Gate through Copilot Chat

In the same chat session, explicitly ask Copilot to use the `release-gate`
skill, naming both the action and the base ref so it cannot guess:

```text
Use the release-gate skill to validate this repository.
```

Expected result: Copilot first checks `release-gate --version`, then reports
a `VALID:` policy without editing it.

```text
Use the release-gate skill to run against base release-gate-demo-base.
```

Copilot must invoke the gate once, preserve the exact `PASS`, `FAIL`, or
`NEEDS_HUMAN` verdict, read the produced `result.json`, and report its reason
codes and evidence path. It must not retry, edit evidence, merge, or deploy.
Copy the absolute path printed after `RESULT:`.

If Copilot's terminal tool reports the same `release-gate.exe` blocked error
described above, ask it to run the equivalent `python -m release_gate`
command instead (see that troubleshooting entry) — the arguments after the
subcommand are identical.

Continue with steps 6 (inspect/grade), 7 (all three verdicts, substituting
this appendix for the Copilot part of each scenario), and 8 (reset) exactly
as written above.
