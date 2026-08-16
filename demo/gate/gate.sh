#!/usr/bin/env bash
# =============================================================================
#  THE GATE  —  ReleaseGateService, minimum viable version
# =============================================================================
#
#  Given a repository that contains a candidate change, gather several
#  independent kinds of evidence and return ONE verdict:
#
#      PASS         every check ran and every check succeeded
#      FAIL         a check ran and found a problem with the candidate
#      NEEDS_HUMAN  a check COULD NOT RUN (tool missing, timeout, crash) —
#                   we have no evidence either way, so a human must look
#
#  The one rule that matters:  FAIL CLOSED.
#  A check that breaks is not a pass. It is not even a fail — we learned
#  nothing about the candidate, so we escalate. This is the distinction the
#  scaffolding calls "infrastructure failure is not candidate failure"
#  (B3 invariant 7). Getting it wrong is how a gate becomes theatre.
#
#  Usage:
#      bash demo/gate/gate.sh <repo_dir> <venv_dir> [run_id]
#
#  Output: the verdict on stdout, one line per check, and an evidence file at
#      demo/runs/<run_id>/evidence.json
#  Exit code: 0 PASS, 1 FAIL, 2 NEEDS_HUMAN
# =============================================================================
set -uo pipefail

REPO="${1:?usage: gate.sh <repo_dir> <venv_dir> [run_id]}"
VENV="${2:?usage: gate.sh <repo_dir> <venv_dir> [run_id]}"
RUN_ID="${3:-$(date -u +%Y%m%dT%H%M%SZ)}"

DEMO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$DEMO/runs/$RUN_ID"
mkdir -p "$RUN_DIR"
PY="$VENV/bin/python"

# ---- policy: the numbers a human chose, written down where they can be seen
COVERAGE_FLOOR=85          # hard floor: below this the suite is not real evidence
COVERAGE_DROP_MAX=1        # % points a candidate may LOWER coverage by (differential)
CHECK_TIMEOUT=300          # seconds; a check that runs longer has not "passed"

# ---- evidence accumulator ---------------------------------------------------
declare -a NAMES STATUSES DETAILS
record() {                 # record <name> <status: pass|fail|error> <detail>
  NAMES+=("$1"); STATUSES+=("$2"); DETAILS+=("$3")
  printf '  %-16s %-6s %s\n' "$1" "$2" "$3"
}

# run_check <name> <cmd...>
#   exit 0        -> pass
#   exit 1        -> fail   (the tool ran and found a problem)
#   exit 124      -> error  (timeout: no verdict)
#   anything else -> error  (the tool itself broke: no verdict)
# pytest follows this convention: 0 ok, 1 tests failed, 2-5 = usage/collection
# error/interrupted — the LAST group is the one most gates get wrong.
# Portable timeout: GNU `timeout` is not on macOS, so run the check through
# Python's subprocess with a deadline. Exit 124 on timeout, like GNU timeout.
with_timeout() {
  "$PY" - "$CHECK_TIMEOUT" "$@" <<'PYEOF'
import subprocess, sys
limit = float(sys.argv[1]); cmd = sys.argv[2:]
try:
    sys.exit(subprocess.run(cmd, timeout=limit).returncode)
except subprocess.TimeoutExpired:
    sys.exit(124)
except FileNotFoundError:
    sys.exit(127)
PYEOF
}

# run_check <name> [--needs <module>] <cmd...>
run_check() {
  local name="$1"; shift
  local log="$RUN_DIR/$name.log"
  if [[ "${1:-}" == "--needs" ]]; then
    # If the tool is not importable, `python -m tool` exits 1, which would be
    # mislabelled as a candidate FAIL. Check first and label it as ERROR.
    "$PY" -c "import $2" 2>/dev/null || { record "$name" error "tool '$2' not installed — check cannot run"; return; }
    shift 2
  fi
  with_timeout "$@" >"$log" 2>&1
  local rc=$?
  case $rc in
    0)   record "$name" pass  "exit 0" ;;
    1)   record "$name" fail  "exit 1 — see $(basename "$log")" ;;
    124) record "$name" error "TIMEOUT after ${CHECK_TIMEOUT}s — no verdict" ;;
    *)   record "$name" error "exit $rc — tool did not run cleanly, no verdict" ;;
  esac
}

# The gate is not allowed to run without its tools. Missing tool = error,
# not silently skipped. (A gate that skips missing checks is one `pip
# uninstall` away from passing everything.)
need() { "$PY" -c "import $1" 2>/dev/null || record "tool:$1" error "not installed in $VENV — check cannot run"; }

echo "GATE run=$RUN_ID"
echo "  repo=$REPO"
echo "  candidate=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?')  dirty=$(git -C "$REPO" status --porcelain | wc -l | tr -d ' ') files changed"
echo

# ---- 0. preconditions ---------------------------------------------------------
need pytest; need pytest_cov; need mypy; need ruff

# ---- 1. behavioural: does the existing suite still pass? -----------------------
run_check tests --needs pytest "$PY" -m pytest "$REPO/test.py" -q -p no:cacheprovider

# ---- 2. coverage: is the suite actually exercising the code? --------------------
# Two rules. (a) A hard floor: below COVERAGE_FLOOR the suite is too thin to
# be evidence at all. (b) Differential: the candidate must not LOWER coverage
# by more than COVERAGE_DROP_MAX points. Rule (b) is what catches "I changed
# the code and left the old path behind as dead code" — dead code never runs,
# so coverage falls. Coverage that is merely printed is decoration.
cov_pct() {   # cov_pct <src_dir> <test_file>  -> integer percent, or empty on error
  "$PY" -m pytest "$2" -q -p no:cacheprovider --cov="$1" --cov-report=term 2>/dev/null \
    | sed 's/\x1b\[[0-9;]*m//g' | awk '/^TOTAL/{gsub("%","",$NF); print $NF}'
}
COV_BASE_TREE="$RUN_DIR/.covbase"; rm -rf "$COV_BASE_TREE"; mkdir -p "$COV_BASE_TREE"
if git -C "$REPO" archive HEAD slugify test.py 2>/dev/null | tar -x -C "$COV_BASE_TREE" 2>/dev/null; then
  base_cov=$(cd "$COV_BASE_TREE" && cov_pct "$COV_BASE_TREE/slugify" "$COV_BASE_TREE/test.py")
  cand_cov=$(cd "$REPO" && cov_pct "$REPO/slugify" "$REPO/test.py")
  "$PY" -m pytest "$REPO/test.py" -q -p no:cacheprovider --cov="$REPO/slugify" --cov-report=term-missing > "$RUN_DIR/coverage.log" 2>&1
  if [[ -z "$base_cov" || -z "$cand_cov" ]]; then
    record coverage error "could not measure coverage (base='$base_cov' cand='$cand_cov') — no verdict"
  elif (( cand_cov < COVERAGE_FLOOR )); then
    record coverage fail  "candidate ${cand_cov}% is below the ${COVERAGE_FLOOR}% floor"
  elif (( base_cov - cand_cov > COVERAGE_DROP_MAX )); then
    record coverage fail  "baseline ${base_cov}% -> candidate ${cand_cov}%: dropped $((base_cov-cand_cov)) pts (max ${COVERAGE_DROP_MAX}) — dead or untested code added"
  else
    record coverage pass  "baseline ${base_cov}% -> candidate ${cand_cov}%"
  fi
else
  record coverage error "could not extract baseline tree — no verdict"
fi
rm -rf "$COV_BASE_TREE"

# ---- 3. static: types -----------------------------------------------------------
run_check types --needs mypy "$PY" -m mypy "$REPO/slugify" --ignore-missing-imports

# ---- 4. static: lint — DIFFERENTIAL -------------------------------------------
# The upstream baseline is not lint-clean (58 pre-existing findings on
# 2026-08-16). A gate that lints the whole tree would fail every candidate for
# sins it did not commit, and the check would carry no information. So the
# question is not "is the tree clean?" but "did the CANDIDATE make it worse?":
# count findings on the baseline commit and on the candidate; fail on increase.
lint_count() { "$PY" -m ruff check --quiet --output-format=concise "$@" 2>/dev/null | grep -c . ; }
BASE_TREE="$RUN_DIR/.baseline"
rm -rf "$BASE_TREE"; mkdir -p "$BASE_TREE"
if git -C "$REPO" archive HEAD slugify setup.py 2>/dev/null | tar -x -C "$BASE_TREE" 2>/dev/null; then
  base_n=$(lint_count "$BASE_TREE/slugify" "$BASE_TREE/setup.py")
  cand_n=$(lint_count "$REPO/slugify" "$REPO/setup.py")
  if [[ "$cand_n" -le "$base_n" ]]; then
    record lint pass  "findings baseline=$base_n candidate=$cand_n (no new findings)"
  else
    "$PY" -m ruff check --output-format=concise "$REPO/slugify" "$REPO/setup.py" > "$RUN_DIR/lint.log" 2>&1
    record lint fail  "findings baseline=$base_n candidate=$cand_n — candidate ADDED $((cand_n-base_n)), see lint.log"
  fi
else
  record lint error "could not extract baseline tree for comparison — no verdict"
fi
rm -rf "$BASE_TREE"

# ---- 5. must-not: secrets in the candidate ---------------------------------------
# For a "must find nothing" grep, exit 1 (no matches) is the ONLY pass.
# exit 0 = found something = FAIL.  exit >=2 = grep itself broke = ERROR.
# Calibrated on the baseline 2026-08-16: the word "secrets" appears in a test
# fixture string, so the pattern is anchored to credential shapes, not words.
grep -rInE '(api[_-]?key[[:space:]]*[=:]|passw(or)?d[[:space:]]*[=:]|BEGIN[[:space:]]+[A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,})' \
  "$REPO/slugify" "$REPO/setup.py" >"$RUN_DIR/secrets.log" 2>&1
case $? in
  1) record secrets pass  "no credential patterns" ;;
  0) record secrets fail  "credential-shaped string found — see secrets.log" ;;
  *) record secrets error "scan itself failed (rc>=2) — no verdict" ;;
esac

# ---- 6. scope: did the candidate touch what it was told not to? -----------------
# X1 says: do not modify test.py.  A candidate that rewrites the tests can make
# any change "pass" — this is the cheapest and most common way an AI change
# games a test-based gate.
if git -C "$REPO" diff --quiet HEAD -- test.py; then
  record scope pass "test.py unchanged"
else
  record scope fail "test.py was modified — candidate altered its own evidence"
fi

# ---- verdict ---------------------------------------------------------------------
# Precedence: any ERROR -> NEEDS_HUMAN, else any FAIL -> FAIL, else PASS.
# ERROR outranks FAIL on purpose: if a check could not run, we do not fully
# know what the candidate is, and "FAIL" would claim knowledge we lack.
VERDICT=PASS; EXIT=0
for s in "${STATUSES[@]}"; do [[ $s == fail ]] && { VERDICT=FAIL; EXIT=1; }; done
for s in "${STATUSES[@]}"; do [[ $s == error ]] && { VERDICT=NEEDS_HUMAN; EXIT=2; }; done

# ---- evidence file: what the gate saw, machine-readable, one per run --------------
{
  echo '{'
  echo "  \"run_id\": \"$RUN_ID\","
  echo "  \"repo\": \"$REPO\","
  echo "  \"candidate_commit\": \"$(git -C "$REPO" rev-parse HEAD 2>/dev/null)\","
  echo "  \"candidate_diff_sha256\": \"$(git -C "$REPO" diff HEAD | shasum -a 256 | cut -c1-16)\","
  echo "  \"policy\": {\"coverage_floor\": $COVERAGE_FLOOR, \"check_timeout_s\": $CHECK_TIMEOUT},"
  echo '  "checks": ['
  for i in "${!NAMES[@]}"; do
    sep=,; [[ $i -eq $((${#NAMES[@]}-1)) ]] && sep=
    printf '    {"name": "%s", "status": "%s", "detail": "%s"}%s\n' "${NAMES[$i]}" "${STATUSES[$i]}" "${DETAILS[$i]//\"/\\\"}" "$sep"
  done
  echo '  ],'
  echo "  \"verdict\": \"$VERDICT\","
  echo "  \"decided_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""
  echo '}'
} > "$RUN_DIR/evidence.json"
git -C "$REPO" diff HEAD > "$RUN_DIR/candidate.patch"

echo
echo "VERDICT: $VERDICT"
echo "evidence: $RUN_DIR/evidence.json"
exit $EXIT
