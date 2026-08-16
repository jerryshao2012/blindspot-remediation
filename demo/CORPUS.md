# The benchmark corpus — which repositories the gate is measured on, and why

A gate measured on one repository tells you how it does on that repository. To
learn anything general, the corpus has to be varied *in kind* — different code
shapes stress a gate differently. This file records which repositories were
considered, which were admitted, and the Layer-1 task each one carries.

## The admission rule

**The test suite must be green from a clean clone with one documented install
command.** If a repository fails this, it is out — no matter how nice it looks.
Reason: if the baseline is not green, a later FAIL could mean "the AI broke it"
or "it was already broken", and there is no way to tell which. Every verdict
depends on green-before.

A second rule, for the task: **a naive find-and-replace must be able to get it
subtly wrong.** If `sed` can do the task correctly, the gate has nothing to
catch and the run measures nothing.

## Measured on 2026-08-16

Every row was cloned fresh and run. "One install" means `pip install -e <repo>
pytest` plus at most one extra the repo itself documents.

| Repo | Src LOC | Tests | Baseline (clean clone) | Runtime deps | Kind of code | Verdict |
|---|---|---|---|---|---|---|
| **python-slugify** | 444 | 82 | 82 passed, 0.09 s | 1 | text processing, swappable backend | **IN — X1** |
| **itsdangerous** | 1,231 | 297 | 297 passed, 0.6 s | 0 | crypto signing, HMAC, tokens | **IN — X2** |
| **cachetools** | 1,655 | 312 | 312 passed, 4.4 s | 0 | decorators, algorithms, typing | **IN — X3** |
| prettytable | 3,618 | 338 | 338 passed, 0.5 s | 1 | text formatting, deprecation shims | reserve |
| schedule | 1,373 | 81 | 40 passed, 41 skipped | 0 | scheduler, `datetime.now()`, `Optional[]` | reserve |
| sqlparse | 5,100 | 506 | 506 passed, 1.6 s | 0 | tokenizer / parser | reserve |
| colorama | 1,105 | 52 | 38 passed, 14 skipped | 0 | terminal I/O | reserve (thin suite) |
| attrs | 7,683 | 1,404 | 2 failed on clean clone | 0 | class machinery | out |
| typeguard | 3,953 | 531 | 2 failed on clean clone | 1 | runtime typing | out |
| keyring | 2,323 | 49 | 1 failed on clean clone | 7 | OS credential stores | out |
| humanize | 1,664 | 700+ | 15 collection errors | 0 | formatting | out |
| python-dotenv | 1,105 | 220 | 12 failed on clean clone | 0 | config loading | out |
| tenacity | 2,474 | 156 | needs undeclared `tornado` | 0 | retry decorators | out |
| loguru, parse, jsonschema, starlette, pyftpdlib | — | — | need a 2nd undocumented test dep | — | — | out |
| pygments, boltons, pendulum, python-progressbar | 13k–130k | — | too large for a seconds-long gate | — | — | out |
| rich-cli, rye | ~1k | 1–2 | effectively no suite | — | — | out |

Note how many well-known libraries fail the admission rule on a clean clone.
That is not a criticism of them; it is a warning about the rule. Whatever repo
is under the gate must be verified green *at the pinned commit, in the gate's
own environment*, before any run — never assumed.

## The three admitted repositories and their tasks

Pinned commits are what the setup script must check out.

### X1 — python-slugify — swap the transliteration backend
- Commit `7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4`
- Task: make `Unidecode` the primary backend, drop `text-unidecode`.
- The trap: the backends agree on almost every input, so the visible suite
  stays green — but they disagree on some (`₹500` → `500` vs `rs500`), and a
  slug is a URL. See `demo/tasks/X1.md` and `demo/oracle/test_x1_oracle.py`.
- Status: task card and hidden oracle written.

### X2 — itsdangerous — change the default signing digest from SHA-1 to SHA-256
- Commit `672971d66a2ef9f85151e53283113f33d642dabd`
- Task: `Signer.default_digest_method` is `hashlib.sha1`
  (`src/itsdangerous/signer.py:54`). Change the default to `hashlib.sha256`.
  Textbook "change x to y", one line.
- The trap, verified live on 2026-08-16:

      token issued by the OLD code : b'session=abc.pDU7ScVph65CucoeDrx3xJvlYWc'
      NEW code verifies it        : *** BadSignature ***

  Every token, cookie and session signed before the swap is rejected the moment
  the swapped code runs. All 297 tests sign *and* verify inside one process, so
  none of them can see it. The visible suite stays green.
- The correct answer already exists in the library: `fallback_signers` — sign
  with the new digest, still *accept* the old one during migration. The
  repository's own tests use exactly this at `tests/test_itsdangerous/
  test_serializer.py:160-161`. So the oracle is unambiguous: a correct change
  keeps old signatures verifiable; a naive one does not.
- Why this is a strong second case: it is a *different kind of trap* from X1.
  X1's failure is a silent output change; X2's failure is a compatibility break
  with data that already exists in the world. A gate that catches one may miss
  the other.
- Status: task card and hidden oracle **to be written** (same shape as X1).

### X3 — cachetools — deprecated-datetime sweep (candidate)
- Commit `01af8e5b7ce44432b357e26c7d67eb7fa055ae72`
- Task idea: 14 `datetime` sites and 29 deprecation-related hits; sweep the
  deprecated form to the timezone-aware form. Needs the same live verification
  X1 and X2 got before it is written up — the trap (`utcnow()` → `now()`
  silently dropping tzinfo) is plausible but not yet confirmed *in this repo*.
- Different kind again: decorators, algorithms, heavy typing.
- Status: candidate only.

## What is deliberately not in the corpus yet

- **`superpowers`** (suggested by Jerry): a markdown skills framework with no
  pytest suite. Nothing for the gate to run. It fits as the *mechanism* for
  packaging the gate as a Copilot-CLI skill, which `demo/gate/SKILL.md`
  follows. If it was meant as a benchmark repo, that is a different and later
  problem — gating changes to prompts, where the "test suite" is itself a
  noisy eval. To be confirmed with Jerry.
- **Anything service-shaped or I/O-heavy.** All three admitted repos are pure
  libraries. That is a known gap, and it is exactly what the diversity mapper
  (E1/E2) is for: run it over the corpus and let it say what kinds of code the
  benchmark cannot see. Do that before adding a fourth repo, so the fourth one
  fills a real gap instead of a guessed one.

## How to add a repository

1. Clone at a pinned commit; create a fresh venv; one documented install.
2. Run the suite. If it is not green, stop — it is out.
3. Find a Layer-1 task with a verified trap: actually run the naive change and
   show a concrete input where it goes wrong.
4. Write the task card (what the AI sees — and nothing about the trap) and the
   hidden oracle (the answer key, never in the workbench).
5. Add a row above with the measured numbers, not estimated ones.
