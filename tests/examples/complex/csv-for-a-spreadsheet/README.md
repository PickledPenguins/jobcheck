# CSV a spreadsheet can open safely

The file holds a row whose name is `=SUM(A1:A9)`. A spreadsheet opening a CSV
treats a leading `=` as a formula, so the report escapes it on the way out --
while the table view and the outcomes keep the value the test actually saw.

Level:    complex
Input:    `examples/data/customers.csv`, CSV output, `name` copied into the report
Expected: the formula cell prefixed with an apostrophe in the CSV; exit 0

Why this combination:

This is the only case where the *output format* changes the data, and it is a
security property rather than a cosmetic one: the escaping has to happen in the
CSV and nowhere else, which needs both halves in one run to see.
