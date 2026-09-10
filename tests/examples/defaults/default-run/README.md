# Default run

Loads `hard_checks` and `soft_checks` plus the always-on base suite, and the root
`examples/rules/error_overrides.yaml`.

Level:    simple
Input:    `python3 examples/main.py`
Expected: registry table, registry-vs-overrides table, per-row results; exit 0
