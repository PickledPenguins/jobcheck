# Write the report to a file

`--report-file` writes the report instead of printing it, in whichever format
`--report` names. Nothing is printed but the confirmation line, which is the
point: a scheduled job wants the file, not the terminal.

The bytes that land in the file are the ones `csv-format` prints.

Level:    moderate
Input:    `examples/data/customers.csv`, written as CSV to a path under /tmp
Expected: the `wrote ...` line only; exit 0
