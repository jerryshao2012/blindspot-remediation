#!/usr/bin/env bash
# Set up (or reset) the demo workbench: a clean clone of python-slugify pinned
# at a known-green commit, plus a virtual environment.
#
# Usage:
#   bash demo/setup_workbench.sh          # first-time setup
#   bash demo/setup_workbench.sh reset    # restore the pristine baseline between runs
#
# The baseline rule: the suite must be GREEN before any change is made.
# If the baseline is not green, a gate verdict is meaningless — you cannot
# tell "the AI broke it" apart from "it was already broken".
set -euo pipefail

DEMO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WB="$DEMO/workbench"
REPO="$WB/python-slugify"
VENV="$WB/venv"

# Pinned baseline: verified 82/82 green on 2026-08-16.
SHA=7b6d5d96c1995e6dccb39a19a13ba78d7d0a3ee4
URL=https://github.com/un33k/python-slugify.git

if [[ "${1:-}" == "reset" ]]; then
  echo "== resetting workbench to the pinned baseline =="
  git -C "$REPO" reset --hard "$SHA" --quiet
  git -C "$REPO" clean -fdx --quiet
  # Decontaminate: slugify AUTO-PREFERS Unidecode when it is installed
  # (try/except import). If a previous run installed it, the next baseline
  # would silently use the wrong backend. Remove it.
  "$VENV/bin/pip" uninstall -q -y Unidecode 2>/dev/null || true
  "$VENV/bin/pip" install -q -e "$REPO"
else
  mkdir -p "$WB"
  if [[ ! -d "$REPO/.git" ]]; then
    echo "== cloning python-slugify =="
    git clone --quiet "$URL" "$REPO"
  fi
  git -C "$REPO" checkout --quiet "$SHA"
  if [[ ! -x "$VENV/bin/python" ]]; then
    echo "== creating virtual environment =="
    python3 -m venv "$VENV"
  fi
  # NOTE: deliberately does NOT install Unidecode — the baseline backend
  # must be text-unidecode, which the package itself declares.
  "$VENV/bin/pip" install -q -e "$REPO" pytest
fi

echo "== baseline check: the suite must be green BEFORE any change =="
"$VENV/bin/python" -m pytest "$REPO/test.py" -q

echo
echo "BASELINE GREEN at $SHA"
echo "Workbench: $REPO"
echo "Venv:      $VENV"
