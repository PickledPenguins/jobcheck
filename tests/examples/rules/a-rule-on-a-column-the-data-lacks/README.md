# A rule on a column the data lacks

The one rule mistake the loader cannot catch, because it has no data to compare against: the rule loads, matches nothing, and would silently never apply. The entry point asks `check_override_columns` and prints what it says on stderr.

Level:    moderate
Input:    `examples/data/customers.csv` with a rule matching on `archived`, a column the file does not have
Expected: the run completes and the report is unchanged, and stderr carries one warning naming the rule and the column: the rule can never apply, which nothing else would say; exit 0
