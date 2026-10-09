#!/usr/bin/env bash
# Install the pre-push gate (scripts/pre-push). Run once per clone:  ./scripts/install-hooks.sh
set -euo pipefail
cd "$(dirname "$0")/.."

hook=".git/hooks/pre-push"
target="../../scripts/pre-push"

# Never clobber someone else's hook silently: keep a copy and say so.
if [ -e "$hook" ] && [ "$(readlink "$hook")" != "$target" ]; then
    backup="$hook.bak"
    if [ -e "$backup" ]; then
        echo "refusing to overwrite $hook: $backup already exists" >&2
        echo "move or delete it, then run this script again" >&2
        exit 1
    fi
    mv "$hook" "$backup"
    echo "existing hook moved to $backup"
fi

ln -sfn "$target" "$hook"
echo "installed $hook -> scripts/pre-push"
