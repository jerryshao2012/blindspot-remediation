#!/usr/bin/env python3
"""Parse a claude -p stream-json transcript into per-run struggle metrics.

Reads the JSONL transcript, prints one line of space-separated values:
  model turns session_id tok_in tok_out tok_cache_r tok_cache_w cost ok
  commands_run self_test_runs test_failures iterations_to_green repair_cycles
  did_reinstall claimed_success
Never raises: on any parse problem prints 'unknown'/0 placeholders with ok=error.
"""
import json, re, sys

def main(path):
    tool_cmds = {}          # tool_use_id -> bash command
    edits_seq = []          # ordered events: ('edit',) or ('pytest', failed_bool)
    commands = tests = fails = 0
    reinstall = False
    result_ev = None
    try:
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if not line: continue
            try: ev = json.loads(line)
            except Exception: continue
            t = ev.get('type')
            if t == 'assistant':
                for b in (ev.get('message') or {}).get('content') or []:
                    if b.get('type') != 'tool_use': continue
                    name = b.get('name', '')
                    if name == 'Bash':
                        cmd = (b.get('input') or {}).get('command', '')
                        tool_cmds[b.get('id')] = cmd
                        commands += 1
                        if 'pip install -e' in cmd: reinstall = True
                    elif name in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
                        edits_seq.append(('edit', None))
            elif t == 'user':
                for b in (ev.get('message') or {}).get('content') or []:
                    if b.get('type') != 'tool_result': continue
                    cmd = tool_cmds.get(b.get('tool_use_id'), '')
                    if 'pytest' not in cmd: continue
                    tests += 1
                    txt = b.get('content')
                    if isinstance(txt, list):
                        txt = ' '.join(c.get('text','') for c in txt if isinstance(c, dict))
                    txt = str(txt or '')
                    failed = bool(re.search(r'\b[1-9]\d* (failed|error)', txt) or 'Traceback' in txt or 'ModuleNotFoundError' in txt)
                    if failed: fails += 1
                    edits_seq.append(('pytest', failed))
            elif t == 'result':
                result_ev = ev
    except FileNotFoundError:
        print('unknown 0 unknown 0 0 0 0 unknown error 0 0 0 - 0 0 unknown'); return

    # iterations_to_green: 1-based index of first all-green self-test
    itg = '-'
    n = 0
    for kind, failed in edits_seq:
        if kind == 'pytest':
            n += 1
            if not failed: itg = str(n); break
    # repair_cycles: edit actions after the first failing self-test
    rc = 0; seen_fail = False
    for kind, failed in edits_seq:
        if kind == 'pytest' and failed: seen_fail = True
        elif kind == 'edit' and seen_fail: rc += 1

    if result_ev:
        ok = 'ok' if not result_ev.get('is_error') and result_ev.get('subtype') in (None, 'success') else 'error'
        mu = result_ev.get('modelUsage') or {}
        m = next(iter(mu), 'unknown'); u = mu.get(m, {})
        cost = result_ev.get('total_cost_usd')
        cost = f'{cost:.4f}' if isinstance(cost, (int, float)) else 'unknown'
        final = str(result_ev.get('result') or '')
        claimed = 0 if re.search(r'unable|cannot|not able|blocked|failed to complete', final, re.I) else 1
        print(m, result_ev.get('num_turns', 0), result_ev.get('session_id', 'unknown'),
              u.get('inputTokens', 0), u.get('outputTokens', 0),
              u.get('cacheReadInputTokens', 0), u.get('cacheCreationInputTokens', 0),
              cost, ok, commands, tests, fails, itg, rc, int(reinstall), claimed)
    else:
        print('unknown 0 unknown 0 0 0 0 unknown error', commands, tests, fails, itg, rc, int(reinstall), 'unknown')

if __name__ == '__main__':
    main(sys.argv[1])
