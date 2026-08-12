# Shared Contracts: First Steps

This is the first implemented component of the AI engineering platform.

It contains only cross-service data contracts. It deliberately contains no:

- Azure clients
- Git commands
- LLM calls
- test-generation logic
- release-gating algorithms
- statistical interval calculations
- benchmark execution code
- persistence implementations

Those responsibilities will be implemented in later components.

## 1. Create a Python environment

```bash
python -m venv .venv
```

Activate it:

PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

Bash or zsh

```bash
source .venv/bin/activate
```

## 2. Install the package

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## 3. Run the example

```bash
validate-contract-example
```

This validates a realistic TaskRunRequest, serializes it to JSON, calculates
a stable content fingerprint, and verifies a JSON round trip.

## 4. Run the tests

```bash
pytest
```

## 5. Export JSON schemas

```bash
export-contract-schemas --output-directory generated-schemas
```

The command creates one JSON Schema document for each public top-level
contract.

## Important interpretation rules

1. `ExecutionResult.local_check_results` are executor claims. They are not
   authoritative release evidence.
2. `GateResult.decision` is a recommendation. The release gate does not merge
   or deploy code.
3. `HUMAN_REVIEW_REQUIRED` sends a signal to an external workflow. A human is
   not part of the release-gate implementation.
4. A large number of generated tests against one candidate patch does not
   become a large number of independent observations of pipeline reliability.
5. `BenchmarkCase.hidden_oracle` must not be accessible to the executor or
   release gate. It is used only after the gate decision is finalized.
6. A content fingerprint detects changes but is not a digital signature.

---

# Expected Repository Layout

```text
shared-contracts/
├── pyproject.toml
├── README-FIRST-STEPS.md
├── src/
│   └── ai_engineering_contracts/
│       ├── __init__.py
│       ├── base.py
│       ├── constants.py
│       ├── enums.py
│       ├── example.py
│       ├── models.py
│       └── schema_export.py
└── tests/
    ├── test_contracts.py
    └── test_schema_export.py
```

# Verification Commands

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest
validate-contract-example
export-contract-schemas --output-directory generated-schemas
```

No method in this package is intentionally left unimplemented. The package
either returns a validated result or raises a specific validation, value, or
runtime error rather than silently accepting incomplete data.
