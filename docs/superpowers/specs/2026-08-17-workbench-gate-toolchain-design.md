# Workbench Gate Toolchain Setup Design

## Goal

Make `demo/setup_workbench.sh` self-contained so both first-time setup and
`reset` leave the workbench able to run every gate check without a separate
manual package-installation step.

## Current Problem

The first-time path installs the editable `python-slugify` checkout and
`pytest`, while the reset path installs only the editable checkout. The gate
also requires `pytest-cov`, `mypy`, and `ruff`. A new or previously modified
virtual environment can therefore produce `NEEDS_HUMAN` solely because those
tools are absent.

## Design

Define the gate packages once in `demo/setup_workbench.sh` and execute one
common installation command after the initialization/reset branch. That
command will install the editable workbench repository plus:

- `pytest`
- `pytest-cov`
- `mypy`
- `ruff`

The reset-only `Unidecode` removal remains unchanged and still runs before
the common installation step. The clone, pinned checkout, virtualenv creation,
and 82-test baseline check also retain their existing behavior.

This central list is preferred over duplicating packages in both branches,
which could drift, and over adding a requirements file, which is unnecessary
for four fixed tool names in a single script.

## Documentation

Update `README.md` and `demo/RUN.md` so setup instructions no longer ask the
operator to install gate tools manually. Troubleshooting should direct the
operator to rerun `bash demo/setup_workbench.sh reset`, which now repairs a
missing gate tool itself.

## Error Handling

Package-installation failures remain fatal under `set -euo pipefail`. The
script must not claim a green baseline when the toolchain could not be
installed. The gate's existing fail-closed `NEEDS_HUMAN` behavior is not
changed.

## Verification

Use an integration-level red/green check against the real workbench:

1. Uninstall `mypy` from `demo/workbench/venv`.
2. With the current script, run reset and confirm importing all four gate
   modules still fails because `mypy` remains absent.
3. Apply the setup-script and documentation change.
4. Uninstall `mypy` again, run reset, and confirm `pytest`, `pytest_cov`,
   `mypy`, and `ruff` all import successfully.
5. Run the complete gate and require all six checks plus the final verdict to
   pass.

## Non-Goals

- Changing gate policy, verdict precedence, or individual checks.
- Pinning tool versions.
- Activating the virtualenv globally.
- Changing the candidate repository baseline.
