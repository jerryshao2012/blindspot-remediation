#!/usr/bin/env bash
# =============================================================================
#  SDLC CAMPAIGN v2 — online lane only, eval-grade columns
# =============================================================================
#  Same experiment as sdlc_campaign.sh (fresh claude -p session -> release-gate
#  -> verdict, online) with schema v2:
#   - executor captured as stream-json TRANSCRIPT (per-attempt struggle metrics:
#     self-test runs, failures before green, repair edits, reinstall) parsed by
#     demo/parse_executor.py
#   - identity columns (card/policy/base/tool versions) so every row carries
#     its own comparability proof
#   - change-shape columns (lines +/-, unexpected paths, scope-creep flag)
#  Writes demo/runs/sdlc-runs-v2.csv. The v1 CSV and the 20-run workbook are
#  frozen populations - never appended to.
#  Usage: bash demo/sdlc_campaign_v2.sh [N] [model]
# =============================================================================
set -uo pipefail
N="${1:-1}"; MODEL="${2:-claude-haiku-4-5-20251001}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO="$ROOT/release-gate/demo/python-slugify"
WB="$DEMO/workbench/python-slugify"
CARD="$ROOT/demo/tasks/X1_v3.md"
CSV="$ROOT/demo/runs/sdlc-runs-v2.csv"
BASE=release-gate-demo-base
EXPECTED_PATHS="README.md setup.py slugify/slugify.py tox.ini"

command -v claude >/dev/null || { echo "claude CLI missing"; exit 3; }
command -v release-gate >/dev/null || { echo "release-gate CLI missing"; exit 3; }
CARD_SHA=$(shasum -a 256 "$CARD" | cut -c1-12)
GATE_VER=$(release-gate --version 2>/dev/null | awk '{print $2}')
EXEC_VER=$(claude --version 2>/dev/null | awk '{print $1}')

[[ -f "$CSV" ]] || echo 'run_id,start_utc,model,session_id,turns,commands_run,self_test_runs,test_failures,iterations_to_green,repair_cycles,did_reinstall,tok_input,tok_output,tok_cache_read,tok_cache_write,cost_usd,executor_wall_s,gate_ms,verdict,reason_codes,files_changed,changed_paths,unexpected_paths,scope_creep,lines_added,lines_removed,diff_sha12,claimed_success,task_ref,card_sha,policy_sha,base_commit,gate_version,executor_version,result_path' > "$CSV"

for i in $(seq 1 "$N"); do
  RUN="v2-$(date -u +%Y%m%dT%H%M%SZ)"
  START=$(date -u +%F' '%T)
  echo "== [$i/$N] $RUN =="
  ( cd "$DEMO" && python3 demo.py reset >/dev/null 2>&1 ) || { echo "reset failed"; exit 4; }

  T0=$(date +%s)
  TR="$ROOT/demo/runs/${RUN}-transcript.jsonl"
  ( cd "$WB" && claude -p "$(cat "$CARD")" \
        --model "$MODEL" --output-format stream-json --verbose --max-turns 40 \
        --permission-mode bypassPermissions --add-dir "$DEMO/workbench" \
        > "$TR" 2>"$ROOT/demo/runs/${RUN}-executor.err" )
  EXEC_RC=$?
  WALL=$(( $(date +%s) - T0 ))
  read -r M TURNS SID TIN TOUT TCR TCW COST EXEC_OK CMDS TESTS FAILS ITG RC REINST CLAIMED \
    <<<"$(python3 "$ROOT/demo/parse_executor.py" "$TR")"
  if [[ $EXEC_RC -ne 0 || "$EXEC_OK" != "ok" ]]; then
    echo "  executor infra failure (rc=$EXEC_RC, $EXEC_OK) — recorded, gate skipped"
    echo "$RUN,$START,$M,$SID,$TURNS,$CMDS,$TESTS,$FAILS,$ITG,$RC,$REINST,$TIN,$TOUT,$TCR,$TCW,$COST,$WALL,,EXEC_ERROR,rc=$EXEC_RC,,,,,,,,,X1@v3,$CARD_SHA,,,$GATE_VER,$EXEC_VER," >> "$CSV"
    continue
  fi

  LADD=$(git -C "$WB" diff --numstat | awk '{a+=$1} END{print a+0}')
  LDEL=$(git -C "$WB" diff --numstat | awk '{d+=$2} END{print d+0}')
  DIFFSHA=$(git -C "$WB" diff | shasum -a 256 | cut -c1-12)

  GOUT=$( cd "$WB" && release-gate run --repo . --base "$BASE" 2>&1 )
  GATE_RC=$?
  VERDICT=$(sed -n 's/^VERDICT: //p' <<<"$GOUT" | tail -1)
  RESULT=$(sed -n 's/^RESULT: //p' <<<"$GOUT" | tail -1)
  if [[ $GATE_RC -ge 3 || -z "$RESULT" ]]; then
    echo "  gate infra error (exit $GATE_RC)"
    echo "$RUN,$START,$M,$SID,$TURNS,$CMDS,$TESTS,$FAILS,$ITG,$RC,$REINST,$TIN,$TOUT,$TCR,$TCW,$COST,$WALL,,GATE_ERROR,exit $GATE_RC,,,,,$LADD,$LDEL,$DIFFSHA,$CLAIMED,X1@v3,$CARD_SHA,,,$GATE_VER,$EXEC_VER," >> "$CSV"
    continue
  fi
  ARCH="$ROOT/demo/runs/$RUN-gate"
  cp -R "$(dirname "$RESULT")" "$ARCH" 2>/dev/null && RESULT="$ARCH/result.json"
  read -r REASONS NFILES PATHS GMS PSHA BCOM UNEXP CREEP <<<"$(python3 - "$RESULT" "$EXPECTED_PATHS" <<'PYEOF'
import json, sys
d=json.load(open(sys.argv[1])); expected=set(sys.argv[2].split())
p=d.get('scope',{}).get('changed_paths',[])
unexp=[x for x in p if x not in expected]
creep=1 if (unexp or d.get('scope',{}).get('review_required_paths') or d.get('scope',{}).get('outside_allowed_paths')) else 0
print(';'.join(d.get('reason_codes',[])) or '-', len(p), '|'.join(p) or '-', d.get('duration_ms',''),
      d.get('config_sha256','')[:12], d.get('base_commit','')[:12], '|'.join(unexp) or '-', creep)
PYEOF
)"
  echo "$RUN,$START,$M,$SID,$TURNS,$CMDS,$TESTS,$FAILS,$ITG,$RC,$REINST,$TIN,$TOUT,$TCR,$TCW,$COST,$WALL,$GMS,$VERDICT,\"$REASONS\",$NFILES,\"$PATHS\",\"$UNEXP\",$CREEP,$LADD,$LDEL,$DIFFSHA,$CLAIMED,X1@v3,$CARD_SHA,$PSHA,$BCOM,$GATE_VER,$EXEC_VER,$RESULT" >> "$CSV"
  printf "  verdict=%s tests=%s fails=%s itg=%s repair=%s +%s/-%s cost=\$%s creep=%s\n" \
    "$VERDICT" "$TESTS" "$FAILS" "$ITG" "$RC" "$LADD" "$LDEL" "$COST" "$CREEP"
done
echo "rows -> $CSV"
