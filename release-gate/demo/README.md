# Release Gate End-to-End Demos

This directory contains standalone, reproducible end-to-end demonstrations of **Release Gate**—a tool that acts as an independent, policy-driven verification and bounded repair gate between AI coding assistants and production repositories.

Release Gate reconstructs clean, independent evaluation workspaces, evaluates candidate changes against reviewed policy rules, detects AI blindspots, blocks scope and policy tampering, and manages human-approved bounded repair workflows.

---

## Demos Overview & Summary Comparison

Release Gate includes two complementary benchmark demonstrations:

| Feature / Dimension | `rate-limiter` Demo | `python-slugify` Demo (Task X1) |
|---|---|---|
| **Primary Focus** | **Algorithmic Correctness & Bounded Repair** | **Packaging Migration & AI Agent Blindspots** |
| **Domain / Scenario** | In-process sliding-window rate limiter with injected clock. | Open-source library migrating transliteration backend (`text-unidecode` $\to$ `Unidecode`). |
| **Workflow Tested** | Automated 3-verdict controls and **0.6 Bounded Repair Loop** ($C0 \to C1 \to C2$). | Automated 3-verdict controls and **Interactive Copilot CLI / Chat walkthrough**. |
| **Defect Profile** | Exact-boundary off-by-one expiry ($t = \text{window}$), inverted pruning, non-finite window validation. | Ambient environment confusion, uninstalled declared dependencies, silent omission of `tox.ini`. |
| **Assurance Layers** | 100% branch coverage, 8-mutant mutation gauntlet, cache-collision negative controls, strict types, must-not scans. | Package build validation, unit test suites, linting, scope enforcement against test tampering. |
| **Independent Oracle** | Differential brute-force model (11 tests) verifying boundary, interleaving, and clock rollback. | Hidden transliteration oracle (15 checks) verifying symbol/currency divergence (`₹500`, `♥ love`). |
| **Documentation** | [rate-limiter/README.md](rate-limiter/README.md) | [python-slugify/README.md](python-slugify/README.md) |

---

### Detailed Comparison

#### 1. `rate-limiter` (Logic Edge Cases & Bounded Repair)
* **Goal:** Prove that Release Gate can rigorously test deep algorithmic invariants and guide an AI assistant through a human-in-the-loop repair cycle without permitting unapproved edits.
* **The Repair Progression:**
  1. **$C0$ (FAIL):** Seeds an off-by-one window expiry defect (`>=` instead of `>`) alongside an approved documentation note. Triggers `repair-start` and requires human approval.
  2. **$C1$ (FAIL):** The assistant attempts a fix in an isolated disposable workspace but inverts the check (`<=`), failing `repair-evaluate` while leaving the source worktree untouched.
  3. **$C2$ (PASS $\to$ Applied):** The assistant restores the strict boundary (`>`) and preserves approved edits. Release Gate evaluates $C2$ as `PASS`, obtains final human approval bound to the patch digest, and transactionally applies the fix.
* **Key Strengths:** Demonstrates workspace isolation, attempt budgeting (capped at 2 attempts), and full gauntlet hardening (100% coverage, mutation analysis).

#### 2. `python-slugify` (Dependency Lifecycles & Real-World Agent Blindspots)
* **Goal:** Test how AI coding assistants handle real-world package maintenance, exposing common cognitive blindspots.
* **Observed Agent Blindspots:**
  1. **Ambient Environment Confusion:** The assistant declares a dependency in `setup.py` and verifies it using the host Python (where the package happens to exist), but omits installing it in the clean project venv. Release Gate detects the missing package upon collection and halts with `NEEDS_HUMAN`.
  2. **Selective / Incomplete Updates:** The assistant updates code files (`setup.py`, `slugify.py`) but forgets peripheral configuration files (`tox.ini`), demonstrating that LLMs produce stable outputs where actively tested but variable outputs where unchecked.
  3. **Tampering Defenses:** Catches attempts to modify `test.py` (`FAIL`) or `.release-gate.yaml` (`NEEDS_HUMAN`).

---

## Environment & Proxy Configuration (`env.example.ps1` / `env.example.sh`)

Corporate environments frequently operate behind authenticated HTTP/HTTPS proxies or custom enterprise certificate authorities (CAs). The demo directory provides checked-in, credential-free templates:

* [`env.example.ps1`](env.example.ps1) — For Windows PowerShell / GitHub Copilot CLI terminals.
* [`env.example.sh`](env.example.sh) — For POSIX shells (macOS zsh, Linux bash, Git Bash).

### Why these templates exist

1. **Security & Credential Isolation:** Local proxy settings often contain domain credentials. Copying the template to `env.ps1` or `env.sh` (both of which are explicitly gitignored) guarantees that sensitive credentials and internal proxy hosts are never committed.
2. **Consistent Subprocess Inheritance:** Tools like `uv` and Python subprocesses need explicit environment variables (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `UV_SYSTEM_CERTS`, `UV_LINK_MODE`) to reach PyPI and validate SSL certificates via the OS certificate store.
3. **Automated Loading via Launcher Scripts:** The demo launchers (`rate-limiter/run.ps1` and `rate-limiter/run.sh`) automatically dot-source `../env.ps1` or `../env.sh` before resolving Python 3.12, ensuring proxy variables reliably reach Release Gate.

### Setup Instructions

#### Windows PowerShell:
```powershell
Copy-Item env.example.ps1 env.ps1
notepad env.ps1       # replace DOMAIN\user, password, and proxy host
. .\env.ps1           # dot-source into current shell
```

#### macOS / Linux / Git Bash:
```sh
cp env.example.sh env.sh
chmod 600 env.sh
$EDITOR env.sh        # replace DOMAIN\user, password, and proxy host
. ./env.sh            # source into current shell
```

### Key Environment Variables Explained

* **`HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`:** Standard URL-encoded proxy endpoint (e.g. `http://user:pass@proxy.corp:8080/`).
* **`NO_PROXY`:** Comma-separated list of bypass hosts (e.g. `localhost,127.0.0.1`).
* **`UV_SYSTEM_CERTS="true"`:** Tells `uv` to verify TLS certificates using the platform's native certificate store (necessary for corporate intercepting proxies).
* **`UV_LINK_MODE="copy"`:** Ensures virtual environments use standalone file copies rather than hardlinks across Windows drive boundaries.

---

## Quick Start / Running the Demos

### 1. `rate-limiter` Demo
```powershell
# Windows PowerShell
cd release-gate\demo\rate-limiter
.\run.ps1 verify          # 3-verdict automated check
.\run.ps1 verify-repair   # multi-stage bounded repair verification
```

```zsh
# macOS / Linux
cd release-gate/demo/rate-limiter
./run.sh verify           # 3-verdict automated check
./run.sh verify-repair    # multi-stage bounded repair verification
```

### 2. `python-slugify` Demo
```powershell
# Windows PowerShell
cd release-gate\demo\python-slugify
uv run --python 3.12 --no-project python demo.py verify
```

```zsh
# macOS / Linux
cd release-gate/demo/python-slugify
uv run --python 3.12 --no-project python demo.py verify
```
