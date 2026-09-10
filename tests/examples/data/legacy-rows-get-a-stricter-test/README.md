# Legacy rows get a stricter test

`AGE_NOT_INTEGER` is off by default. This rule file turns it on for rows whose
`source_system` starts `LEGACY_` *and* whose `record_type` is `BATCH` -- both
criteria must match, which is what makes it a rule rather than a switch.

Level:    moderate
Input:    `examples/data/customers.csv` with the age rule file
Expected: `AGE_NOT_INTEGER` firing on the legacy batch rows with a decimal age,
          and disabled everywhere else; exit 0
