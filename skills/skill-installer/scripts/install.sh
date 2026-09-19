#!/bin/sh
# Platform entry point for POSIX shells. Accepts the consuming repository
# root as an explicit first argument, runs its own runtime preflight, then
# delegates installation to install.py unchanged. Implements no
# installation semantics of its own.
set -eu

fail() {
    echo "install.sh: $1" >&2
    exit 1
}

resolve_dir() {
    # Physical directory of $1, following symlinks, independent of cwd.
    src=$1
    while [ -L "$src" ]; do
        dir=$(CDPATH= cd -- "$(dirname -- "$src")" && pwd -P)
        target=$(readlink "$src")
        case "$target" in
            /*) src=$target ;;
            *) src="$dir/$target" ;;
        esac
    done
    CDPATH= cd -- "$(dirname -- "$src")" && pwd -P
}

if [ "$#" -lt 1 ]; then
    fail "usage: install.sh <consumer-root> [install.py options...]"
fi

CONSUMER_ROOT=$1
shift

for arg in "$@"; do
    case "$arg" in
        --root|--root=*)
            fail "--root is supplied positionally as <consumer-root>; do not pass it again"
            ;;
    esac
done

# --- runtime preflight ---------------------------------------------------

[ -e "$CONSUMER_ROOT" ] || fail "consumer root does not exist: $CONSUMER_ROOT"
[ -d "$CONSUMER_ROOT" ] || fail "consumer root is not a directory: $CONSUMER_ROOT"

command -v git >/dev/null 2>&1 || fail "git executable not found"

CDUP=$(cd "$CONSUMER_ROOT" 2>/dev/null && git rev-parse --show-cdup 2>/dev/null) \
    || fail "consumer root does not resolve as a Git working tree: $CONSUMER_ROOT"
[ -z "$CDUP" ] \
    || fail "consumer root is not the root of its Git working tree: $CONSUMER_ROOT"

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

SCRIPT_DIR=$(resolve_dir "$0")

# --- dependency preflight ---------------------------------------------------
# Confirms the selected interpreter can import the installer's bundled
# runtime dependencies. Never installs anything; a missing dependency is a
# preflight failure naming scripts/requirements.txt.

"$PY" -c 'import yaml, markdown_it, ruamel.yaml' >/dev/null 2>&1 \
    || fail "missing installer runtime dependency; install with: pip install -r $SCRIPT_DIR/requirements.txt (in an isolated virtual environment)"

# --- delegate --------------------------------------------------------------

exec "$PY" "$SCRIPT_DIR/install.py" --root "$CONSUMER_ROOT" "$@"
