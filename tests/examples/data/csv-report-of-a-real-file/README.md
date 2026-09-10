# CSV report of a real file

The same report as CSV, for a spreadsheet or a downstream job. Cells that a
spreadsheet would run as a formula are neutralised on the way out.

Level:    simple
Input:    `examples/data/customers.csv`
Expected: comma-separated failures with a header row; exit 0
