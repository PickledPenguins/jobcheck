# Summary under topic rules

Compare against `summary-of-a-real-file`: the rules move the counts, and nothing else does.

Level:    moderate
Input:    `examples/data/customers.csv` with `examples/rules/split_by_topic/01_age_rules.yaml` and `examples/rules/split_by_topic/02_email_rules.yaml`
Expected: counts that differ from the unrestricted run by exactly what the rules changed
