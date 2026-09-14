#!/bin/sh
# Platform entry point for POSIX shells. Accepts the consuming repository
# root as an explicit first argument, runs runtime preflight, then
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

SCRIPT_DIR=$(resolve_dir "$0")

"$SCRIPT_DIR/check-runtime.sh" "$CONSUMER_ROOT" >/dev/null

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

exec "$PY" "$SCRIPT_DIR/install.py" --root "$CONSUMER_ROOT" "$@"
