# Security Policy

## Supported versions

| Version | Status |
|---|---|
| 0.2.x | Supported after its final GitHub release is published. |
| 0.1.x | Prior implementation retained for rollback; security fixes are not promised. |
| Unreleased source snapshots | Development only. |

No package is published to PyPI. Release support applies only to artifacts
attached to this repository's immutable `release-gate-v*` GitHub releases and
matching their published checksums.

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/jerryshao2012/blindspot-remediation/security/advisories/new).
This is the project's only supported private reporting channel. Do not open a
public issue, discussion, or pull request for a suspected vulnerability. If
GitHub private vulnerability reporting is unavailable, retain the report
details and retry after the service is restored; never post the details
publicly.

Include the affected Release Gate version and artifact SHA-256, operating
system and Python version, reproduction steps, expected and observed behavior,
impact, and any proposed mitigation. Remove secrets, credentials, and
unrelated personal or repository data from evidence.

Maintainers will acknowledge and triage reports as capacity permits, coordinate
questions and disclosure through the private advisory, and publish fixes and
credit when appropriate. The project does not promise a response-time SLA or
resolution deadline.

## Scope and trust boundary

Security reports may cover the CLI, bundled schemas, initialization
transaction, evidence integrity and path handling, deterministic skill
packager, assistant adapters, or release workflow. Dependency vulnerabilities
that affect a supported Release Gate path are also in scope.

Release Gate is a trusted-host tool, not a sandbox. Repository-owned prepare
and check commands execute with the operator's account. A malicious repository,
base policy, dependency, local same-user process, or configured command is
outside the isolation guarantee. A `PASS` is a policy verdict, not a security
attestation and not authorization to merge or deploy. See the detailed
[security and trust model](docs/security.md).
