# Security and Trust Model

For supported release lines and private vulnerability reporting, see the
[security policy](../SECURITY.md).

## Release artifact trust

Treat the Python wheel and assistant skill as two separate supply-chain inputs.
Install only a matching pair from one immutable `release-gate-v*` GitHub
release after verifying each file against its published SHA-256 manifest. The
skill checks the installed CLI version before every operation and stops on a
missing executable or mismatch.

The wheel checksum covers only the Release Gate wheel. A normal
`uv tool install` resolves the wheel's declared dependency ranges from the
configured package index; the development `uv.lock` is not consumed, and
resolved dependency bytes are outside the release asset checksum. Environments
that require a fully reproducible dependency closure must impose and retain
their own index, version, and hash controls.

An unrelated existing PyPI project uses the name `release-gate`. This project
is not published to PyPI: never install it by an unqualified package name.
Follow the exact wheel and host-archive procedure in
[Adoption](adoption.md). Preserve the prior verified release for rollback and
upgrade by removal plus installation of the next pinned archive, never through
an unpinned skill update.

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
- capture the candidate with an invocation-owned temporary Git index and
  `GIT_OBJECT_DIRECTORY`, expose source objects only as read-only alternates,
  and change neither the real index, candidate source bytes, nor source/shared
  object databases; create no missing default evidence component until
  capture is complete;
- use distinct clean base and candidate clones and keep evidence outside them;
- run argv directly with no shell and resolve `cwd` beneath the clone root;
- reject report/evidence traversal, absolute paths, unsafe symlink targets,
  duplicate normalized paths, and existing run destinations;
- parse XML without DTDs, external entities, or network retrieval;
- validate evidence timestamps with the strict Release Gate RFC 3339 profile,
  including calendar reality and mandatory zones, rather than treating JSON
  Schema `format` as self-enforcing;
- bound command time, retained streams, individual reports, policy shape, and
  total evidence; reserve bounded finalization before candidate evaluation;
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

Initialization treats its policy and `.gitignore` changes as a guarded
two-target update sequence. An optional `--from-config` source is size-bounded and
fully validated before target mutation. The policy must be absent. Its bytes
are first written and flushed in a private repository-local staging directory;
only after the ignore update succeeds is that staged inode published at the
policy path with an atomic, exclusive hard link. There are no fallible target
operations after publication and no policy rollback. Cleanup is limited to
the identity-verified policy file in the random, private staging directory
(mode 0700 where POSIX modes apply); it does not recursively remove unproven
entries. The staging directory's own identity is checked before cleanup and
again immediately before `rmdir`; detected replacements and nonempty
directories are left for human inspection. The staged policy source is created
exclusively without following links, and that descriptor remains open through
publication. Its descriptor identity, bytes, path identity, and containing
directory identity are checked before linking.

An existing `.gitignore` must be an ordinary file, never a symbolic link or
Windows reparse point; its identity, length, and digest are snapshotted. The
command opens or exclusively creates the final path, takes a nonblocking
exclusive advisory lock, and performs the final snapshot check through that
pinned handle. That lock is held through an append or existing-entry no-op,
policy publication, and failure rollback. Ignore bytes are flushed before
publication. Immediately before the policy link, the command revalidates the
ignore path identity and exact expected descriptor bytes, even when the ignore
entry already existed and no append was required. Rollback truncation is
attempted through the still-locked handle only when the path identity and exact
invocation-written tail remain proven, with a second verification at the
rollback boundary. Detected later or unproven bytes cause rollback refusal and
are preserved. A newly created ignore file is left empty on a later failure;
the command never uses a check-then-unlink sequence that could delete a
concurrent replacement. Locks are advisory, so other writers should use a
compatible lock; non-cooperating changes are detected where portable file APIs
allow and cause destructive rollback to be refused.

These checks narrow race windows but do not create a filesystem transaction.
Portable APIs cannot atomically bind the final ignore verification to the
policy hard link, the exact-content rollback check to `ftruncate`, or an
identity check to `unlink`/`rmdir`. The random staging namespace is private
(0700 on POSIX) but a hostile same-user process can still discover and race it,
and a non-cooperating writer can bypass the advisory ignore lock. Such a process
may win a syscall-level race after the last check. Release Gate performs no
unsafe retry or target-path unlink in response. Operators must exclude other
same-user repository writers during `init`; same-user filesystem access is an
explicit trust boundary.

Git arguments are passed after `--` where paths are accepted. Refs are
resolved with commit peeling and recorded as object IDs. Patch application
uses Git's binary-safe machinery and rejects paths outside the worktree,
submodule surprises not represented by the base, and ambiguous case-folding
collisions on the host. The source repository, its index, and its refs remain
read-only to the engine.

Candidate capture also isolates object writes. The engine removes every
ambient `GIT_*` variable, then supplies only a closed invocation-owned Git
environment, including its temporary index/object directory and validated
source object locations as read-only alternates. Alternate lists use
`os.pathsep` (`:` on POSIX, `;` on Windows) plus Git's documented
quoting/escaping for entries containing the separator or quotes. Source Git
reads use `GIT_OPTIONAL_LOCKS=0` so status/index refresh cannot write through an
optional lock. The temporary object directory remains live through diff
emission and candidate-tree reconstruction and is then removed. Tests compare
the real index, status,
refs, and a filename/content inventory of the per-worktree and shared object
databases before and after capture, including linked worktrees and pre-existing
alternates.

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

Every retained regular file counts toward `limits.total_bytes`, including
`manifest.json` although the manifest cannot inventory itself. Before a
verdict, the exact patch and effective configuration must fit beside a fixed
7 MiB result/manifest/trace reserve; otherwise the input is rejected with exit
3 and no result. Once evaluation begins, deterministic stream/report quotas
preserve the reserve, and budget exhaustion becomes a complete
`NEEDS_HUMAN` package. Accepted patch/config bytes are never truncated. This
makes every allowed 16-200 MiB total feasible rather than relying on disk
exhaustion during finalization.

Archive evidence before deleting the workspace. A `PASS` is a policy result,
not a guarantee of security or correctness; the gate neither performs nor
authorizes a merge or deployment.

## Repair security and isolation

The bounded repair workflow operates under strict safety guarantees:
- **Untrusted logs**: All logs from check failures are treated as untrusted data.
- **No network/dependency installs**: Repair workers do not have network access and cannot install new dependencies or modify `.release-gate.yaml`, control launchers, or playbooks.
- **Strict path boundaries**: Repair edits are confined strictly to approved paths computed from initial changed files and base playbooks.
- **Source worktree immutability**: The source repository worktree and real index remain untouched during repair iterations.
- **Pre-apply recapture verification**: Before applying any passing patch, the source worktree is recaptured and verified against candidate `C0`'s tree and patch digest. Any intervening edits cause an immediate abort.
- **Transactional rollback**: If patch application fails, changes are cleanly rolled back to the base commit.
