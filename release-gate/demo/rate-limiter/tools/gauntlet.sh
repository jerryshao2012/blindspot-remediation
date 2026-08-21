#!/bin/sh
# POSIX convenience wrapper. Release Gate invokes gauntlet.py directly so the
# same checks run on Windows and macOS.
set -eu
cd "$(dirname "$0")/.."
PYTHON=${PYTHON:-.venv/bin/python}
exec "$PYTHON" tools/gauntlet.py
