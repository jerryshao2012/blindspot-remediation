# Workbench Gate Toolchain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make first-time workbench setup and every reset install all tools required by the fail-closed gate.

**Architecture:** Keep a single Bash array of gate package names in `demo/setup_workbench.sh`. Both setup branches retain their branch-specific work, then converge on one editable-package and gate-tool installation command before the baseline test.

**Tech Stack:** Bash, Python virtual environments, pip, pytest, pytest-cov, mypy, ruff

---

### Task 1: Prove and repair gate-tool restoration

**Files:**
- Modify: `demo/setup_workbench.sh:14-47`
- Test: integration commands against `demo/workbench/venv`

- [ ] **Step 1: Remove one gate tool to reproduce the reset defect**

Run:

```bash
demo/workbench/venv/bin/pip uninstall -y mypy
bash demo/setup_workbench.sh reset
demo/workbench/venv/bin/python -c "import pytest, pytest_cov, mypy, ruff"
```

Expected: reset's 82-test baseline check passes, but the final import command
fails with `ModuleNotFoundError: No module named 'mypy'`. This proves the
current reset does not restore the full gate toolchain.

- [ ] **Step 2: Define the gate packages once**

Add the package array immediately after the workbench paths:

```bash
GATE_TOOLS=(pytest pytest-cov mypy ruff)
```

- [ ] **Step 3: Converge both setup paths on one install command**

Remove the branch-local pip install commands. After the closing `fi`, add:

```bash
"$VENV/bin/pip" install -q -e "$REPO" "${GATE_TOOLS[@]}"
```

Do not change the reset-only `Unidecode` removal, clone/checkout behavior,
virtualenv creation, or baseline test.

- [ ] **Step 4: Check Bash syntax**

Run:

```bash
bash -n demo/setup_workbench.sh
```

Expected: exit 0 with no output.

- [ ] **Step 5: Verify reset restores a missing tool**

Run:

```bash
demo/workbench/venv/bin/pip uninstall -y mypy
bash demo/setup_workbench.sh reset
demo/workbench/venv/bin/python -c "import pytest, pytest_cov, mypy, ruff; print('gate tools import: OK')"
```

Expected: reset reports `82 passed`, and the import command prints
`gate tools import: OK`.

- [ ] **Step 6: Verify first-time setup in an isolated temporary directory**

Create a temporary directory under `/tmp`, copy only the setup script into it,
and run that copy so its `DEMO` and `workbench` paths stay outside the real
workspace:

```bash
mktemp -d /tmp/blindspot-setup-test.XXXXXX
cp demo/setup_workbench.sh <returned-temp-path>/setup_workbench.sh
bash <returned-temp-path>/setup_workbench.sh
<returned-temp-path>/workbench/venv/bin/python -c "import pytest, pytest_cov, mypy, ruff; print('fresh setup gate tools import: OK')"
```

Expected: the temporary setup reports `82 passed`, and the import command
prints `fresh setup gate tools import: OK`. Remove only the exact temporary
directory returned by `mktemp` after the check.

- [ ] **Step 7: Commit the setup-script repair**

```bash
git add demo/setup_workbench.sh
git commit -m "fix(demo): restore gate tools during workbench setup"
```

### Task 2: Remove obsolete manual-install instructions

**Files:**
- Modify: `README.md:282-290`
- Modify: `demo/RUN.md:234-241`

- [ ] **Step 1: Simplify first-time setup instructions**

Change the README block from two commands to the self-contained command:

```bash
bash demo/setup_workbench.sh
```

- [ ] **Step 2: Update missing-tool recovery guidance**

Replace the manual `pip install pytest pytest-cov mypy ruff` instruction in
`demo/RUN.md` with:

```text
Run `bash demo/setup_workbench.sh reset` and re-run step 4.
```

Preserve the explanation that `NEEDS_HUMAN` is correct fail-closed behavior.

- [ ] **Step 3: Confirm no obsolete manual-install instruction remains**

Run:

```bash
rg -n "pip install pytest(-cov)?|pip install pytest pytest-cov mypy ruff" README.md demo
```

Expected: no setup or troubleshooting instruction tells the operator to
install the gate tools manually. Historical run evidence may contain other
pip text and is not in scope.

- [ ] **Step 4: Commit the documentation update**

```bash
git add README.md demo/RUN.md docs/superpowers/plans/2026-08-17-workbench-gate-toolchain.md
git commit -m "docs(demo): make workbench setup self-contained"
```

### Task 3: Run final verification

**Files:**
- Verify: `demo/setup_workbench.sh`
- Verify: `demo/gate/gate.sh`
- Generated evidence: `demo/runs/setup-verification-20260817/`

- [ ] **Step 1: Re-run the complete reset from a healthy environment**

Run:

```bash
bash demo/setup_workbench.sh reset
```

Expected: exit 0, the pinned commit is restored, and all 82 baseline tests
pass.

- [ ] **Step 2: Verify all gate modules are importable**

Run:

```bash
demo/workbench/venv/bin/python -c "import pytest, pytest_cov, mypy, ruff; print('gate tools import: OK')"
```

Expected: `gate tools import: OK`.

- [ ] **Step 3: Run the complete gate**

Run:

```bash
bash demo/gate/gate.sh "$PWD/demo/workbench/python-slugify" "$PWD/demo/workbench/venv" setup-verification-20260817
```

Expected: tests, coverage, types, lint, secrets, and scope all report `pass`,
followed by `VERDICT: PASS`.

- [ ] **Step 4: Inspect the final change set**

Run:

```bash
git diff --check HEAD~2..HEAD
git status --short
```

Expected: no whitespace errors; only the previously generated untracked gate
evidence may remain outside the committed changes.
