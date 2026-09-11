# One row of a large export, under every rule

The deepest single-row diagnosis the demo can make: row 1,999 of a 2,000-row
file, with all four rule files loaded, so a `disabled` line names the rule that
decided it and a `skipped` line names what blocked it. `--explain` exits before
the report deliberately -- one row's detail is a different question from the
file's.

Level:    complex
Input:    row 1999 of `examples/data/customers_large.csv` under all four rule files
Expected: one line per check for that row, each non-evaluating line saying why,
          then the row's root cause; no report, no summary; exit 0
