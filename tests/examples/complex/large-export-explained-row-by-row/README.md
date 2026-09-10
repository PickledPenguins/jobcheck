# One row out of two thousand

`--explain` addresses a row by position, so the last row of a 2,000-row file is
row 1999. The explanation costs the same as any other row's: the frame is
validated once and one row's outcomes are printed.

Level:    complex
Input:    row 1999 of `examples/data/customers_large.csv`
Expected: that row's tests, outcomes and root cause; exit 0

Why this combination:

Position addressing is the part that breaks quietly. A frame filtered, sorted or
re-indexed upstream would make row 1999 someone else, and the only way to see
that is to ask for a row a long way from the start.
