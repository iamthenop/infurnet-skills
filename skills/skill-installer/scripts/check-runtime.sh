#!/bin/sh
# Runtime preflight for skill-installer on POSIX shells. Verifies a
# supported Python, a usable Git, and that the supplied path is the actual
# root of its Git working tree, then classifies the consumer as bootstrap
# or managed by installation-manifest presence alone. Prints exactly one
# state line to stdout on success; diagnostics go to stderr. Non-mutating.
set -eu

fail() {
    echo "check-runtime: $1" >&2
    exit 1
}

if [ "$#" -ne 1 ]; then
    fail "usage: check-runtime.sh <consumer-root>"
fi

CONSUMER_ROOT=$1

[ -e "$CONSUMER_ROOT" ] || fail "consumer root does not exist: $CONSUMER_ROOT"
[ -d "$CONSUMER_ROOT" ] || fail "consumer root is not a directory: $CONSUMER_ROOT"

command -v git >/dev/null 2>&1 || fail "git executable not found"

TOPLEVEL=$(cd "$CONSUMER_ROOT" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null) \
    || fail "consumer root does not resolve as a Git working tree: $CONSUMER_ROOT"

RESOLVED_ROOT=$(cd "$CONSUMER_ROOT" && pwd -P)
RESOLVED_TOPLEVEL=$(cd "$TOPLEVEL" && pwd -P)
if [ "$RESOLVED_ROOT" != "$RESOLVED_TOPLEVEL" ]; then
    fail "consumer root is not the root of its Git working tree: $CONSUMER_ROOT (root is $TOPLEVEL)"
fi

PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)' >/dev/null 2>&1; then
            PY=$candidate
            break
        fi
    fi
done
[ -n "$PY" ] || fail "no supported Python interpreter found (requires Python >= 3.12; tried: python3, python)"

MANIFEST="$CONSUMER_ROOT/.agents/infurnet-skills.manifest.json"
if [ -e "$MANIFEST" ] || [ -L "$MANIFEST" ]; then
    echo "state=managed"
else
    echo "state=bootstrap"
fi
