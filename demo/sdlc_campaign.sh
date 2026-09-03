#!/usr/bin/env bash
# =============================================================================
#  SDLC-STYLE CAMPAIGN — online lane only
# =============================================================================
#  Simulates the gate inside a real SDLC process, N times:
#     task card → fresh `claude -p` session edits the repo → release-gate run
#     → verdict. Nothing is graded against the hidden oracle; the gate's
#     answer IS the outcome, exactly as it would be in production.
#
#  Per run it records what the team asked for:
#     tokens   — input / output / cache read / cache write (from claude -p
#                --output-format json, field modelUsage; reported, not estimated)
#     time     — start timestamp, executor wall seconds, gate milliseconds
#     model    — the model id claude actually used
#     changes  — files touched (from result.json scope.changed_paths) + a
#                fingerprint of the whole diff, so consistency across runs
#                is measurable afterwards
#
#  Usage:  bash demo/sdlc_campaign.sh [N] [model]
# =============================================================================
set -uo pipefail
N="${1:-5}"
MODEL="${2:-claude-haiku-4-5-20251001}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO="$ROOT/release-gate/demo/python-slugify"
WB="$DEMO/workbench/python-slugify"
CARD="$ROOT/demo/tasks/X1_v3.md"
CSV="$ROOT/demo/runs/sdlc-runs.csv"
BASE=release-gate-demo-base

command -v claude >/dev/null || { echo "claude CLI not found"; exit 3; }
command -v release-gate >/dev/null || { echo "release-gate CLI not found"; exit 3; }
[[ -f "$CSV" ]] || echo 'run_id,start_utc,model,turns,tok_input,tok_output,tok_cache_read,tok_cache_write,cost_usd,executor_wall_s,gate_ms,verdict,reason_codes,files_changed,changed_paths,diff_sha12,result_path' > "$CSV"

for i in $(seq 1 "$N"); do
  RUN="sdlc-$(date -u +%Y%m%dT%H%M%SZ)"
  START=$(date -u +%F' '%T)
  echo "== [$i/$N] $RUN =="
  ( cd "$DEMO" && python3 demo.py reset >/dev/null 2>&1 ) || { echo "reset failed"; exit 4; }

  T0=$(date +%s)
  OUT="$ROOT/demo/runs/${RUN}-executor.json"
  ( cd "$WB" && claude -p "$(cat "$CARD")" \
        --model "$MODEL" --output-format json --max-turns 40 \
        --permission-mode bypassPermissions --add-dir "$DEMO/workbench" \
        > "$OUT" 2>"$ROOT/demo/runs/${RUN}-executor.err" )
  EXEC_RC=$?
  WALL=$(( $(date +%s) - T0 ))

  read -r MODEL_USED TURNS TIN TOUT TCR TCW COST EXEC_OK <<<"$(python3 -c "
import json
try: d=json.load(open('$OUT'))
except Exception: print('unreadable 0 0 0 0 0 unknown error'); raise SystemExit
ok='ok' if not d.get('is_error') and d.get('subtype') in (None,'success') else 'error'
mu=d.get('modelUsage',{})
m=next(iter(mu),'unknown'); u=mu.get(m,{})
print(m, d.get('num_turns',0), u.get('inputTokens',0), u.get('outputTokens',0),
      u.get('cacheReadInputTokens',0), u.get('cacheCreationInputTokens',0),
      (lambda c: f'{c:.4f}' if isinstance(c,(int,float)) else 'unknown')(d.get('total_cost_usd')), ok)")"
  if [[ $EXEC_RC -ne 0 || "$EXEC_OK" != "ok" ]]; then
    echo "  executor infra failure (rc=$EXEC_RC, $EXEC_OK) — recorded, gate skipped"
    echo "$RUN,$START,$MODEL_USED,$TURNS,$TIN,$TOUT,$TCR,$TCW,$COST,$WALL,,EXEC_ERROR,rc=$EXEC_RC,,," >> "$CSV"
    continue
  fi

  DIFFSHA=$(git -C "$WB" diff | shasum -a 256 | cut -c1-12)
  GOUT=$( cd "$WB" && release-gate run --repo . --base "$BASE" 2>&1 )
  GATE_RC=$?
  VERDICT=$(sed -n 's/^VERDICT: //p' <<<"$GOUT" | tail -1)
  RESULT=$(sed -n 's/^RESULT: //p' <<<"$GOUT" | tail -1)
  if [[ $GATE_RC -ge 3 || -z "$RESULT" ]]; then
    echo "  gate infra error (exit $GATE_RC)"
    echo "$RUN,$START,$MODEL_USED,$TURNS,$TIN,$TOUT,$TCR,$TCW,$COST,$WALL,,GATE_ERROR,exit $GATE_RC,,,$DIFFSHA," >> "$CSV"
    continue
  fi
  read -r REASONS NFILES PATHS GMS <<<"$(python3 -c "
import json;d=json.load(open('$RESULT'))
p=d.get('scope',{}).get('changed_paths',[])
print(';'.join(d.get('reason_codes',[])) or '-', len(p), '|'.join(p) or '-', d.get('duration_ms',''))")"

  # Archive the gate evidence OUT of the disposable workbench: a workbench
  # rebuild deletes .release-gate/runs/, and batch 1 lost its artifacts that
  # way. The CSV row now points at the durable copy.
  ARCH="$ROOT/demo/runs/$RUN-gate"
  cp -R "$(dirname "$RESULT")" "$ARCH" 2>/dev/null && RESULT="$ARCH/result.json"
  echo "$RUN,$START,$MODEL_USED,$TURNS,$TIN,$TOUT,$TCR,$TCW,$COST,$WALL,$GMS,$VERDICT,\"$REASONS\",$NFILES,\"$PATHS\",$DIFFSHA,$RESULT" >> "$CSV"
  printf "  verdict=%s files=%s wall=%ss cost=\$%s tokens(in/out/cacheR)=%s/%s/%s\n" \
    "$VERDICT" "$NFILES" "$WALL" "$COST" "$TIN" "$TOUT" "$TCR"
done

echo; echo "rows -> $CSV"
python3 - "$CSV" <<'PY'
import csv,sys,collections
rows=[r for r in csv.DictReader(open(sys.argv[1])) if r['run_id'].startswith('sdlc-')]
v=collections.Counter(r['verdict'] for r in rows)
print("verdicts:", dict(v))
sets=collections.Counter(r['changed_paths'] for r in rows if r['changed_paths'])
print("distinct change-sets:", len(sets))
for s,c in sets.most_common(): print(f"  x{c}  {s}")
PY
