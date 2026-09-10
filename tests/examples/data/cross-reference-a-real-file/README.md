# Cross-reference columns on a real file

`-v` adds the cross-reference columns to the registry tables: which rules could
override each test, and which tests each rule touches.

Level:    moderate
Input:    `examples/data/customers.csv`, verbosity 1
Expected: registry tables with cross-reference columns, then the report and summary; exit 0
