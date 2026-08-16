#!/usr/bin/env bash
# =============================================================================
#  GRADE A RUN  —  the offline lane, for one run
# =============================================================================
#
#  The gate has spoken. Now WE find out whether it was right, by running the
#  hidden oracle tests the gate never saw. Then we put the run in one of the
#  four boxes and append a row to the run log.
#
#                         change was CORRECT      change was WRONG
#      gate said PASS     good_pass               FALSE_RELEASE   <- dangerous
#      gate said FAIL     FALSE_BLOCK <- costly   good_catch
#      gate NEEDS_HUMAN   escalated               escalated
#
#  Usage:
#      bash demo/grade.sh <run_id> [wall_seconds] [cost|unknown] [model|unknown] [card] [human_step]
#
#  wall_seconds, cost and model are what YOU observed for the Copilot step.
#  cost is in the tool's own unit (Copilot CLI shows "AIC used"). If the tool
#  did not show a value, write "unknown" — do not invent one.
#  card is the task-card version the AI saw (v1, v2, ...). human_step is
#  "none" if the gate's first verdict stood on the AI's work alone, otherwise
#  what the human did before this (re-)gate, e.g. "re-gate after pip install".
# =============================================================================
set -uo pipefail

RUN_ID="${1:?usage: grade.sh <run_id> [wall_seconds] [cost|unknown] [model|unknown] [card] [human_step]}"
WALL="${2:-unknown}"
COST="${3:-unknown}"
MODEL="${4:-unknown}"
CARD="${5:-unknown}"
HUMAN="${6:-none}"

DEMO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$DEMO/runs/$RUN_ID"
PY="$DEMO/workbench/venv/bin/python"
LOG="$DEMO/runs/RUNLOG.md"

[[ -f "$RUN_DIR/evidence.json" ]] || { echo "no evidence for run $RUN_ID — run the gate first"; exit 3; }
VERDICT=$(sed -n 's/.*"verdict": "\([A-Z_]*\)".*/\1/p' "$RUN_DIR/evidence.json")

echo "== running the HIDDEN oracle (the gate never saw these) =="
"$PY" -m pytest "$DEMO/oracle" -q -p no:cacheprovider > "$RUN_DIR/oracle.log" 2>&1
case $? in
  0) TRUTH=correct ;;
  1) TRUTH=wrong ;;
  *) TRUTH=oracle_error ;;   # the answer key itself broke: this run cannot be graded
esac
tail -1 "$RUN_DIR/oracle.log"

case "$VERDICT/$TRUTH" in
  PASS/correct)         BOX=good_pass ;;
  PASS/wrong)           BOX=FALSE_RELEASE ;;
  FAIL/correct)         BOX=FALSE_BLOCK ;;
  FAIL/wrong)           BOX=good_catch ;;
  NEEDS_HUMAN/*)        BOX=escalated ;;
  */oracle_error)       BOX=ungradeable ;;
  *)                    BOX=ungradeable ;;
esac

[[ -f "$LOG" ]] || cat > "$LOG" <<'EOF'
# Run log

One row per run. `tokens` is what the tool reported; `unknown` means it did not
report one — never a guess. `box` is the confusion-matrix cell.

| run_id | task | card | gate verdict | truth (oracle) | box | human step | wall_s (copilot) | cost | model |
|---|---|---|---|---|---|---|---|---|---|
EOF
ROW="| $RUN_ID | X1 | $CARD | $VERDICT | $TRUTH | $BOX | $HUMAN | $WALL | $COST | $MODEL |"
# Insert the row at the END OF THE TABLE, not the end of the file: the log
# carries notes below the table, and a plain append would land the row under
# the prose (this happened once). The table ends at the first blank line
# after its header row.
"$PY" - "$LOG" "$ROW" <<'PYEOF'
import sys
path, row = sys.argv[1], sys.argv[2]
lines = open(path, encoding="utf-8").read().split("\n")
hdr = next(i for i, l in enumerate(lines) if l.startswith("| run_id |"))
end = hdr + 1
while end < len(lines) and lines[end].startswith("|"):
    end += 1
lines.insert(end, row)
open(path, "w", encoding="utf-8").write("\n".join(lines))
PYEOF

echo
echo "gate said:  $VERDICT"
echo "truth was:  $TRUTH"
echo "box:        $BOX"
echo "logged to:  $LOG"
