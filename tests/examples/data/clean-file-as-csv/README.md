# A clean file as CSV

A clean file under `--report csv` prints the CSV header row alone where the failures
would go -- what `--write` would put in the file. The table format prints `(empty)`
instead, so the two cases record different output.

Level:    simple
Input:    `examples/data/customers_clean.csv`
Expected: the CSV header row and nothing under it; exit 0
