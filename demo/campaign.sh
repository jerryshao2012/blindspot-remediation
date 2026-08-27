#!/usr/bin/env bash
# =============================================================================
#  LIVE CAMPAIGN  —  N fresh LLM sessions through the release gate
# =============================================================================
#
#  Each iteration is one LIVE run (this is what measures the AI — scripted
#  control patches measure only the gate):
#
#    1. reset the release-gate slugify workbench to the pinned green baseline
#    2. a FRESH `claude -p` session (Anthropic, default Haiku) gets ONLY the
#       task card demo/tasks/X1_v3.md and edits the working copy
#    3. release-gate run  →  VERDICT (PASS / FAIL / NEEDS_HUMAN)
#    4. demo.py grade against the hidden oracle  →  truth + classification
#    5. one row appended to demo/runs/campaign.csv  (exact USD cost included —
#       claude -p reports it; never guessed)
#
#  Usage:
#     bash demo/campaign.sh [N] [model]
#     bash demo/campaign.sh 1                       # validate the plumbing
#     bash demo/campaign.sh 10 claude-haiku-4-5-20251001
#
#  Notes on honesty and isolation:
#  - Executor sessions run with --permission-mode bypassPermissions so the loop
#    is unattended. Blast radius is the disposable workbench; the card forbids
#    leaving the repository. This is development isolation, not a sandbox.
#  - Each session is fresh: it sees the card and the workbench, never the
#    oracle, never this script, never previous runs.
#  - Rows from different executors/models/cards are separate populations.
#    Do not average them together.
# =============================================================================
set -uo pipefail

N="${1:-1}"
MODEL="${2:-claude-haiku-4-5-20251001}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO="$ROOT/release-gate/demo/python-slugify"
WB="$DEMO/workbench/python-slugify"
CARD="$ROOT/demo/tasks/X1_v3.md"
CSV="$ROOT/demo/runs/campaign.csv"
BASE=release-gate-demo-base

command -v claude >/dev/null || { echo "claude CLI not found"; exit 3; }
command -v release-gate >/dev/null || { echo "release-gate CLI not found"; exit 3; }
[[ -f "$CARD" ]] || { echo "task card missing: $CARD"; exit 3; }

[[ -f "$CSV" ]] || echo 'run_id,date_utc,repo,task,gate,executor,model,card,verdict,reason_codes,truth,classification,human_step,wall_s,cost_usd,result_path' > "$CSV"

for i in $(seq 1 "$N"); do
  RUN="live-$(date -u +%Y%m%dT%H%M%SZ)"
  echo "== [$i/$N] $RUN =="

  ( cd "$DEMO" && python3 demo.py reset >/dev/null 2>&1 ) || { echo "reset failed"; exit 4; }

  T0=$(date +%s)
  OUT="$ROOT/demo/runs/${RUN}-executor.json"
  ( cd "$WB" && claude -p "$(cat "$CARD")" \
        --model "$MODEL" --output-format json \
        --permission-mode bypassPermissions --add-dir "$DEMO/workbench" \
        > "$OUT" 2>"$ROOT/demo/runs/${RUN}-executor.err" )
  EXEC_RC=$?
  WALL=$(( $(date +%s) - T0 ))
  COST=$(python3 -c "
import json,sys
try: d=json.load(open('$OUT'))
except Exception: print('unknown'); sys.exit()
c=d.get('total_cost_usd')
print(f'{c:.4f}' if isinstance(c,(int,float)) else 'unknown')")
  EXEC_ERR=$(python3 -c "
import json
try: d=json.load(open('$OUT'))
except Exception: print('unreadable'); raise SystemExit
print('error' if d.get('is_error') or d.get('subtype') not in (None,'success') else 'ok')")
  # Executor infrastructure failure (rate limit, auth, network) must NOT be
  # gated: an unchanged tree would grade as a fake candidate outcome. Same
  # invariant as the gate's own error!=fail rule, applied one stage earlier.
  if [[ $EXEC_RC -ne 0 || "$EXEC_ERR" != "ok" ]]; then
    echo "  executor infra failure (rc=$EXEC_RC, json=$EXEC_ERR) — row recorded, gate skipped"
    echo "$RUN,$(date -u +%F' '%T),python-slugify,X1,release-gate 0.6.0,claude -p,$MODEL,v3,EXEC_ERROR,\"rc=$EXEC_RC $EXEC_ERR\",not graded,-,none,$WALL,$COST," >> "$CSV"
    continue
  fi

  GOUT=$( cd "$WB" && release-gate run --repo . --base "$BASE" 2>&1 )
  GATE_RC=$?
  VERDICT=$(sed -n 's/^VERDICT: //p' <<<"$GOUT" | tail -1)
  RESULT=$(sed -n 's/^RESULT: //p' <<<"$GOUT" | tail -1)
  if [[ $GATE_RC -ge 3 || -z "$RESULT" ]]; then
    echo "  gate infra error (exit $GATE_RC) — no verdict; row recorded as ungradeable"
    echo "$RUN,$(date -u +%F' '%T),python-slugify,X1,release-gate 0.6.0,claude -p,$MODEL,v3,GATE_ERROR,exit $GATE_RC,not graded,-,none,$WALL,$COST," >> "$CSV"
    continue
  fi
  REASONS=$(python3 -c "import json;d=json.load(open('$RESULT'));print('; '.join(d.get('reason_codes',[])) or '-')")

  GRADE=$( cd "$DEMO" && python3 demo.py grade --result "$RESULT" 2>&1 | tail -3 )
  TRUTH=$(sed -n 's/^truth: //p' <<<"$GRADE"); TRUTH=${TRUTH:-not graded}
  BOX=$(sed -n 's/^classification: //p' <<<"$GRADE"); BOX=${BOX:--}

  echo "$RUN,$(date -u +%F' '%T),python-slugify,X1,release-gate 0.6.0,claude -p,$MODEL,v3,$VERDICT,\"$REASONS\",$TRUTH,$BOX,none,$WALL,$COST,$RESULT" >> "$CSV"
  printf "  verdict=%s  truth=%s  box=%s  wall=%ss  cost=\$%s\n" "$VERDICT" "$TRUTH" "$BOX" "$WALL" "$COST"
done

echo
echo "campaign rows -> $CSV"
python3 - "$CSV" <<'PY'
import csv,sys,collections
rows=list(csv.DictReader(open(sys.argv[1])))
c=collections.Counter(r['classification'] for r in rows)
print(f"total live rows: {len(rows)}  " + "  ".join(f"{k}={v}" for k,v in sorted(c.items())))
PY
