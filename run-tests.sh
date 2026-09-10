#!/usr/bin/env bash
# Test entry point. One mode per gate:
#
#   ./run-tests.sh fast    unit, smoke, interface, regression, cheap pathological
#                          plus mypy -- the pre-commit gate
#   ./run-tests.sh long    integration, load, end-to-end catalogs
#   ./run-tests.sh all     both, plus mypy
#   ./run-tests.sh cov     fast suite with a coverage report, gated at 95%
#   ./run-tests.sh types   mypy alone, for a CI step that has already run the tests
#
# Extra arguments are passed through to pytest.
set -uo pipefail
cd "$(dirname "$0")"

MODE="${1:-fast}"
shift || true

COVERAGE_MIN=95
# Targets come from [tool.mypy] in pyproject.toml.

run_mypy() {
    echo "== mypy =="
    python3 -m mypy || return 1
}

case "$MODE" in
    fast)
        python3 -m pytest -m fast "$@" || exit 1
        run_mypy || exit 1
        ;;
    long)
        python3 -m pytest -m long "$@" || exit 1
        ;;
    types)
        run_mypy || exit 1
        ;;
    all)
        python3 -m pytest "$@" || exit 1
        run_mypy || exit 1
        ;;
    cov)
        python3 -m coverage run -m pytest -m fast "$@" || exit 1
        echo "== coverage =="
        python3 -m coverage report -m --fail-under="$COVERAGE_MIN" || {
            echo "coverage below ${COVERAGE_MIN}%"
            exit 1
        }
        ;;
    *)
        echo "usage: $0 {fast|long|all|cov|types} [pytest args]" >&2
        exit 2
        ;;
esac

echo "$MODE suite: PASS"
