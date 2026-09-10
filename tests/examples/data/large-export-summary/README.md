# Summary of a large export

2,000 rows. The per-row report is too long to read, so the summary is the
output that matters: which tests fire, how often, and what each failing row
bottomed out at.

Level:    moderate
Input:    `examples/data/customers_large.csv` (2,000 rows, about one in six carrying a problem)
Expected: a long CSV report, then per-test counts over 2,000 rows; exit 0
