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
- capture the candidate with a temporary Git index without changing the real
  index or source working tree;
- use distinct clean base and candidate clones and keep evidence outside them;
- run argv directly with no shell and resolve `cwd` beneath the clone root;
- reject report/evidence traversal, absolute paths, unsafe symlink targets,
  duplicate normalized paths, and existing run destinations;
- parse XML without DTDs, external entities, or network retrieval;
- bound command time, retained streams, individual reports, and total evidence;
  and
- treat unavailable required evidence as `NEEDS_HUMAN`, never as a pass.

The engine-owned `.release-gate/runs` path is excluded from candidate capture.
All other non-ignored untracked files are candidates and are included.

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

The engine injects clone-specific home/temp values after both configured
layers. Policies cannot inherit or set POSIX `HOME`/`TMPDIR`, Windows
`USERPROFILE`/`HOMEDRIVE`/`HOMEPATH`/`TEMP`/`TMP`, or any name with the
`RELEASE_GATE_` prefix. The engine never adds `.` or a clone path to `PATH`.

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
paths only after validated joining. They reject leading `/`, UNC/device
syntax, Windows drive prefixes (including `C:relative` forms), backslashes,
empty/`.`/`..` components, leading `./`, and trailing `/`. Each lexical path
appears exactly once. On every host the verifier also rejects two paths whose
NFC forms have the same Unicode `casefold()`, preventing Windows case-fold
aliases in evidence transported across platforms. That portable key is also
compared with `manifest.json`; case variants and non-ASCII casefold aliases of
the manifest name are forbidden artifact paths.

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
