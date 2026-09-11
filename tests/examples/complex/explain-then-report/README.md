# The worst row, then the whole file

`--explain` is deliberately exclusive: one row's detail is a different question from the file's report.

Level:    complex
Input:    row 3 of `examples/data/customers.csv` with `examples/rules/error_overrides.yaml`
Expected: the explanation alone -- `--explain` exits before the report
