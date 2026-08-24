#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENVIRONMENT_SCRIPT="$ROOT/../env.sh"
if [ ! -f "$ENVIRONMENT_SCRIPT" ]; then
    printf '%s\n' "Missing $ENVIRONMENT_SCRIPT. Copy ../env.example.sh to ../env.sh and fill in approved local values." >&2
    exit 1
fi

# shellcheck disable=SC1090
. "$ENVIRONMENT_SCRIPT"
PYTHON=$(uv python find 3.12 | tail -n 1 | tr -d '\r')
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
    printf '%s\n' "uv did not resolve a Python 3.12 executable" >&2
    exit 1
fi

VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
case "$VERSION" in
    3.12.*) ;;
    *) printf '%s\n' "Resolved interpreter is Python $VERSION, expected Python 3.12.x" >&2; exit 1 ;;
esac

exec "$PYTHON" "$ROOT/demo.py" "$@"