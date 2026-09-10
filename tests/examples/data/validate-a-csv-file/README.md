# Validate a CSV export

The everyday run: point the tool at a file and read the failures.

Level:    simple
Input:    `examples/data/customers.csv` (49 rows, a real export's worth of mess)
Expected: one line per failure, keyed by `id`; exit 0 -- failures in the data are a report, not an error
