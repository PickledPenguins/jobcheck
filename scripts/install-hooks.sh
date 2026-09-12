#!/usr/bin/env bash
# Install the pre-commit gate. Run once per clone:  ./scripts/install-hooks.sh
set -euo pipefail
cd "$(dirname "$0")/.."

hook=".git/hooks/pre-commit"
marker="tests/run-tests.sh fast"

# Never clobber someone else's hook silently: keep a copy and say so.
if [ -e "$hook" ] && ! grep -q "$marker" "$hook"; then
    backup="$hook.bak"
    if [ -e "$backup" ]; then
        echo "refusing to overwrite $hook: $backup already exists" >&2
        echo "move or delete it, then run this script again" >&2
        exit 1
    fi
    mv "$hook" "$backup"
    echo "existing hook moved to $backup"
fi

cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
# Fast suite gates every commit. Bypass with git commit --no-verify.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
if ! ./tests/run-tests.sh fast -q; then
    echo "pre-commit: fast suite failed; commit blocked" >&2
    exit 1
fi
HOOK
chmod +x "$hook"
echo "installed $hook"
