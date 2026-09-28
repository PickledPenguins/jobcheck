# A broken check among real failures

A check that calls `.upper()` on a blank cell raises on three rows. The run carries on: those lines are `errored` with the exception as the detail, the check that depends on it is skipped, and the summary counts errors apart from failures. An errored check is still a root cause, so on row S4 it outranks a genuine delivered-before-shipped failure -- fix the check before reading the data failures below it.

Level:    complex
Input:    `run.yaml` naming `setup.yaml` (two check files, no rules) and `shipments.csv` (seven rows, three with a blank carrier)
Expected: a report with three `ERROR (9)` lines and the real failures beside them, then the summary with `errored 3` on `CARRIER_KNOWN`; exit 0
