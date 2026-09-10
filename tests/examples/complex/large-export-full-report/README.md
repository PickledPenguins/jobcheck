# Large export, full report

2,000 rows, every skipped test included, a data column, and a rule file --
the shape of a nightly job's output rather than a demonstration.

Level:    complex
Input:    `examples/data/customers_large.csv` with a global rule file
Expected: several thousand report lines, then the summary; exit 0

Why this combination:

Volume is the point: layering that looks tidy on six rows has to stay tidy on
two thousand, and the summary is the only thing that can be checked by eye at
that size. It also pins the cost -- this case is the slowest in the catalog.
