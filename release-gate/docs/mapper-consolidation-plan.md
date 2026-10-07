# Mapper consolidation

Approved design: bundle the domain-neutral engine under its existing import path in Release Gate, preserving behavior and evidence adapters.

1. Move implementation, documentation, example, and smoke tests.
2. Remove the separate dependency and update builds, CI, qualification, and installation instructions.
3. Run tests, lint, type checks, build and installed-wheel verification.
4. Remove the old directory after verification and commit only consolidation changes on local main.

Validation: 176 integration checks passed; wheel/sdist build and installed CLI smoke test passed; relocated source and changed tests/scripts pass lint, and release-gate passes mypy. Full isolated suite initially reported 739 passed, 3 skipped, 33 existing demo/presentation failures and one stale presentation link; the link is corrected as part of consolidation. Existing adoption edits, .gitignore changes, and staged logs are excluded from this commit.
