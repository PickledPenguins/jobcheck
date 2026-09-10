# Summary across the frame

Per-test counts (failed, errored, skipped, disabled, passed) and a tally of what
each failing row bottomed out at. A high `skipped` count means a fundamental
test is failing often and hiding what is below it.

Level:    simple
Input:    `python3 examples/main.py --summary`
Expected: the failure table, then the summary and the root-cause tally; exit 0
