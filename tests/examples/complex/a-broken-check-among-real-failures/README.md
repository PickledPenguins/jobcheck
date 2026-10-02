# A broken check among real failures

A check that calls `.upper()` on a blank cell raises on three rows. The run carries on: those lines are `errored` with the exception as the detail, the check that depends on it is skipped, and the summary counts errors apart from failures. Root causes put data failures first: on row S4 the genuine delivered-before-shipped failure is flagged and the broken check is not, while on S3, where the broken check is the only problem, the errored line is flagged so the row still shows in a filter on `is_root_cause`.

Level:    complex
Input:    `run.yaml` naming `setup.yaml` (two check files, no rules) and `shipments.csv` (seven rows, three with a blank carrier)
Expected: a report with three `ERROR (9)` lines and the real failures beside them, then the summary with `errored 3` on `CARRIER_KNOWN`; exit 3, with `warning: 3 check run(s) raised` on stderr
