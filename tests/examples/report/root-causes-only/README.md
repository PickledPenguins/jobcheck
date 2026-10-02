# Only the root causes

The first pass over a messy file: what to fix first on each row. The shipped data never fails one row at two layers, so this case carries its own.

Level:    simple
Input:    `two_layers.csv` in this directory: row 2001 has a negative age (layer 2) and an email with no `@` (layer 1)
Expected: row 2001 reports only `EMAIL_MISSING_AT`, its shallowest failure, and drops `AGE_NEGATIVE`; exit 0
