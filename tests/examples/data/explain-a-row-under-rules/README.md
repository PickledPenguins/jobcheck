# Explain a row under rules

A `disabled` line says which rule decided it, which is what makes a rule file auditable.

Level:    moderate
Input:    row 3 of `examples/data/customers.csv` with `examples/rules/split_by_topic/01_age_rules.yaml`
Expected: the explanation naming the rule that disabled a check, by name
