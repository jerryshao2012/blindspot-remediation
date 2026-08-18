# Security and Trust Model

## Supported threat model

V1 protects policy provenance, source-worktree integrity, evidence path
handling, deterministic status classification, and accidental artifact
tampering. It does not isolate hostile code. This is trusted host execution:
configured prepare/check commands and candidate tests execute with the
operator's local account and may read files, consume resources, or access the
network.

Do not run this version against an untrusted repository, patch, dependency, or
base policy. Clean clones prevent base/candidate contamination; they are not
security sandboxes. Containers, virtual machines, network denial, operating
system resource controls, and remote attestations are future execution
backends outside v1.

## Trust boundaries

Trusted inputs are the installed release-gate package and schema files, the
operator-selected base commit, and the `.release-gate.yaml` bytes at that
commit. Candidate worktree bytes, reports, stdout/stderr, generated filenames,
and all executed repository code are untrusted.

The engine MUST:

- resolve the base to an immutable commit before policy loading;
- never load policy or check definitions from candidate-modified bytes;
- treat any candidate change to `.release-gate.yaml` as non-configurable
  preflight `NEEDS_HUMAN`, using base policy and executing no configured
  command;
- require directly invoked repository-local launchers to match
  `scope.review_required_paths`, evaluate scope before execution, and execute
  no configured command when a candidate changes one of those launchers;
- canonicalize the repository and both Git metadata roots, then lexically
  classify the selected evidence spelling before candidate capture; inspect a
  default candidate without following it and canonically resolve only custom
  evidence roots; always reject aliases into the absolute per-worktree
  `--git-dir`, shared `--git-common-dir`, or execution clones; and pin and
  recheck accepted filesystem identities through finalization;
- capture the candidate with a temporary Git index without changing the real
  index or candidate source bytes, and create no missing default evidence
  component until capture is complete;
- use distinct clean base and candidate clones and keep evidence outside them;
- run argv directly with no shell and resolve `cwd` beneath the clone root;
- reject report/evidence traversal, absolute paths, unsafe symlink targets,
  duplicate normalized paths, and existing run destinations;
- parse XML without DTDs, external entities, or network retrieval;
- bound command time, retained streams, individual reports, and total evidence;
  and
- treat unavailable required evidence as `NEEDS_HUMAN`, never as a pass.

Only the literal `<canonical-repo>/.release-gate/runs` path can be the
engine-owned in-repository exception. Lexical normalization must produce that
path under native filesystem case rules, and a no-follow inspection must show
that each existing `.release-gate` and `runs` component is a real directory.
POSIX symbolic links and every Windows reparse point, including junctions, are
rejected even when they target the real default or a safe external directory.
A missing component is not created before capture. The engine checks the node
itself before enabling the descendant exclusion, so a tracked or untracked
candidate redirect remains visible and produces exit 3. It repeats the check
after capture, then creates missing components individually with
no-follow/no-reparse semantics and verifies stable identity after each
creation.

No rejected redirect is followed, replaced, deleted, or written, and
pre-capture validation leaves source bytes, index, and status unchanged. A
pre-execution failure removes only still-empty default scaffolding created by
that invocation. Evidence opens and atomic renames are relative to pinned
directory handles, or a platform-equivalent primitive, rather than a
re-resolved path string. Identities are checked before and after capture,
after creation, after clone placement, before configured preparation/check
commands, and before and after finalization. Candidate evaluation begins
immediately before invariant policy/launcher and configured-scope evaluation,
after the post-clone identity check. A mismatch before that transition is exit
3; after it, identity loss yields exit 4 and no valid package. A late
substitution cannot redirect a write.

A custom root whose normalized spelling or any existing-prefix identity
encountered during canonical resolution enters the source repository,
per-worktree Git directory, or shared Git common directory is rejected, not
excluded; all other non-ignored untracked files remain candidates. This
catches symlinks that enter and then leave a protected tree. The default
exception never permits Git-metadata or clone containment. A custom root may
be an ancestor of a protected path only when its final run directory is
disjoint from every protected path. Checks use component-aware containment
with native Windows case behavior, not textual prefixes.

## Environment and secrets

Checks receive no implicit host environment. Each command copies only names in
its closed `inherit_environment` list, then overlays literal `environment`
values. A requested inherited name that is absent is an evidence error. The
engine does not automatically forward `PATH`, CI tokens, cloud credentials,
SSH agents, credential-helper sockets, or the full developer environment.

On POSIX, names are case-sensitive; on Windows, identity is case-insensitive
and evidence names are uppercased. Same-name inherited/literal overlap is
allowed and the literal wins; case-colliding duplicates within a list or map
are invalid. Platform literal values overlay common values, while a platform
inherit list replaces the common list.

The engine injects a clone-specific `HOME` on every platform after both
configured layers. It additionally injects clone-specific `TMPDIR` on POSIX
and consistent clone-specific `USERPROFILE`/`HOMEDRIVE`/`HOMEPATH`/`TEMP`/`TMP`
values on Windows. Policies cannot inherit or set any of those engine-owned
names or any name with the `RELEASE_GATE_` prefix. Windows applies this rule
case-insensitively and rejects case-colliding configured names. The engine
never adds `.` or a clone path to `PATH`.

Configuration has no environment-variable interpolation or secret reference
feature. Do not put secrets in `.release-gate.yaml`: the effective policy is
retained as evidence. The manifest records environment variable names but not
their values. This limits evidence leakage; it does not stop executed code
from discovering host-readable credentials through other channels. Run the
gate under a dedicated low-privilege identity when consequences matter.

## Git and filesystem handling

Git arguments are passed after `--` where paths are accepted. Refs are
resolved with commit peeling and recorded as object IDs. Patch application
uses Git's binary-safe machinery and rejects paths outside the worktree,
submodule surprises not represented by the base, and ambiguous case-folding
collisions on the host. The source repository, its index, and its refs remain
read-only to the engine.

Artifact paths use Unicode NFC and POSIX separators in contracts and native
paths only after validated joining. Each component is 1-128 Unicode code
points and rejects ASCII controls, Windows-illegal `<>:"/\|?*`, a trailing
dot or space, empty/dot/dotdot names, and case-insensitive DOS device basenames
`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, and `LPT1`-`LPT9`, including with
extensions. Paths have at most 32 components and 1,024 code points total, so
leading `/`, UNC/device syntax, drive forms, leading `./`, and trailing `/`
are also invalid. Each lexical path appears exactly once. On every host the
verifier rejects non-NFC components and two paths whose NFC forms have the
same Unicode `casefold()`, preventing aliases in evidence transported across
platforms. That portable key is also compared with `manifest.json`; case
variants and non-ASCII casefold aliases of the manifest name are forbidden
artifact paths.

Report collection opens only regular files whose resolved location remains
inside the appropriate clone. FIFOs, devices, sockets, and escaping symlinks
are rejected as evidence errors.

## Evidence claims

SHA-256 manifests reveal later artifact changes when compared with the
original manifest. Local evidence is **tamper-evident, not immutable** and V1
never claims signing or attestation. Protect or sign the complete evidence
package externally if the operator and verifier do not share a trust boundary.

Truncation, missing reports, parser failures, timeouts, and interrupted checks
are explicit reason-coded events. Logs and report contents must be treated as
untrusted when displayed; user interfaces should escape control characters
and markup.

## Operational guidance

Pin and review the gate version, review base-policy changes like production
code, keep dependency installation deterministic, and select an explicit base
commit. In CI, use an ephemeral low-privilege runner without unrelated secrets.
Archive evidence before deleting the workspace. A `PASS` is a policy result,
not a guarantee of security or correctness; the gate neither performs nor
authorizes a merge or deployment.
