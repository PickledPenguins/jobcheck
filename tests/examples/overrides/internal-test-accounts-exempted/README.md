# Internal accounts exempted

The shipped rule file, applied to a real export: the rows a rule exempts simply stop being reported.

Level:    simple
Input:    `examples/data/customers.csv` with `examples/rules/error_overrides.yaml`
Expected: no email failures for the `internal.test` rows
