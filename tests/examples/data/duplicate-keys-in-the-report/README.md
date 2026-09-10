# Duplicate keys in the report

Two rows share the id `1023`. The report keys by whatever column it is told to,
and does not deduplicate: a repeated key is the data's problem to fix, and
hiding it would lose a row.

Level:    moderate
Input:    `examples/data/customers.csv`
Expected: both `1023` rows present, distinguishable by `name`; exit 0
