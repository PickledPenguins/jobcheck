# A clean file as CSV

A clean file under `--report csv` prints `No failures.` where the CSV rows would go, the
same line the table format prints. The CSV stays on the console between the registry and
the summary, so stdout is never a CSV file in either case; `write_report` is the call
that writes one, and it writes the header alone when nothing failed.

Level:    simple
Input:    `examples/data/customers_clean.csv`
Expected: `No failures.` under the report heading, no header row; exit 0
