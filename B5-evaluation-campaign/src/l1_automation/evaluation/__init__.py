"""
Offline evaluation and capability-qualification package.

This package evaluates the COMPLETE automation system.

It must not be imported by the online ReleaseGateService for access to hidden
benchmark information.

Dependency direction should remain approximately:

    EvaluationCampaignRunner
          │
          ├── invokes online pipeline through an explicit port
          │
          ├── obtains hidden truth through HiddenOraclePort
          │
          └── calculates evaluation metrics

The online pipeline must never depend on:

    HiddenOracle
    BenchmarkTruth
    expected acceptability
    expected gate outcome
    reference solution

because doing so would contaminate the evaluation.
"""

