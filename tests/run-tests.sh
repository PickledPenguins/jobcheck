#!/usr/bin/env bash
# Test entry point. One mode per gate:
#
#   tests/run-tests.sh fast    unit, smoke, interface, regression, cheap
#                              pathological plus mypy -- the pre-commit gate
#   tests/run-tests.sh long    integration, load, concurrency, faults, scaling,
#                              end-to-end catalogs, then the example profile
#   tests/run-tests.sh all     both, plus mypy
#   tests/run-tests.sh cov     fast suite with a coverage report, gated at 95%
#   tests/run-tests.sh perf    timing against this machine's baseline (own gate)
#   tests/run-tests.sh memory  peak-memory ceilings under tracemalloc (own gate)
#   tests/run-tests.sh profile the example profile alone, without the tests
#   tests/run-tests.sh types   mypy alone, for a CI step that ran the tests
#
# Extra arguments are passed through to pytest.
#
# PYTHON=/path/to/python selects the interpreter; the default is python3. The
# long suite needs hypothesis (the [dev] extra) and refuses to run without it
# rather than skipping the property tests quietly.
set -uo pipefail
# Every mode runs from the project root: pytest, coverage and mypy all read
# their settings out of pyproject.toml there, and the script lives one down.
cd "$(dirname "$0")/.."

MODE="${1:-fast}"
shift || true

PYTHON="${PYTHON:-python3}"
COVERAGE_MIN=95
# Targets come from [tool.mypy] in pyproject.toml.

run_mypy() {
    echo "== mypy =="
    "$PYTHON" -m mypy || return 1
}

# A skipped property suite reads as a pass. It is the one category that finds
# cases nobody wrote down, so its absence is a failed gate, not a footnote.
require_hypothesis() {
    if ! "$PYTHON" -c "import hypothesis" 2>/dev/null; then
        echo "error: hypothesis is not importable by $PYTHON, so the property tests" >&2
        echo "       would skip silently. Install the dev extra (pip install -e '.[dev]')" >&2
        echo "       or point PYTHON= at an interpreter that has it." >&2
        return 1
    fi
}

# The catalog runs each case in a subprocess, so a profiler cannot follow it.
# This drives the same code path in-process and prints where the time went.
run_profile() {
    echo
    "$PYTHON" scripts/profile_examples.py || return 1
}

case "$MODE" in
    fast)
        "$PYTHON" -m pytest -m fast "$@" || exit 1
        run_mypy || exit 1
        ;;
    long)
        require_hypothesis || exit 1
        "$PYTHON" -m pytest -m long "$@" || exit 1
        run_profile || exit 1
        ;;
    types)
        run_mypy || exit 1
        ;;
    all)
        require_hypothesis || exit 1
        "$PYTHON" -m pytest -m "fast or long" "$@" || exit 1
        run_mypy || exit 1
        run_profile || exit 1
        ;;
    cov)
        "$PYTHON" -m coverage run -m pytest -m fast "$@" || exit 1
        echo "== coverage =="
        "$PYTHON" -m coverage report -m --fail-under="$COVERAGE_MIN" || {
            echo "coverage below ${COVERAGE_MIN}%"
            exit 1
        }
        ;;
    perf)
        "$PYTHON" -m pytest -m perf "$@" || exit 1
        ;;
    memory)
        "$PYTHON" -m pytest -m memory "$@" || exit 1
        ;;
    profile)
        run_profile || exit 1
        ;;
    *)
        echo "usage: $0 {fast|long|all|cov|perf|memory|profile|types} [pytest args]" >&2
        exit 2
        ;;
esac

echo "$MODE suite: PASS"
