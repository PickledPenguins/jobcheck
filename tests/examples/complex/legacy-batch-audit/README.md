# The legacy batch audit

The question a migration actually asks: what is wrong with the rows coming from
the old system? One suite, the rule that only fires on `LEGACY_*` + `BATCH`,
full verbosity, and the three columns that decide it shown beside each failure.

Level:    complex
Input:    `examples/data/customers.csv`, `hard_tests`, the legacy rule, verbosity 2
Expected: `AGE_NOT_INTEGER` on the legacy batch rows only, with the columns that
          selected them; exit 0

Why this combination:

A two-criterion rule can fire for the wrong reason and still look right. Showing
`source_system` and `record_type` next to every failure is what makes the rule
auditable rather than merely configured.
