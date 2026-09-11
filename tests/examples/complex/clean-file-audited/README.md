# A clean file, audited

The audit run against a good file, so the difference from a bad one is one diff away.

Level:    complex
Input:    `examples/data/customers_clean.csv` with `examples/rules/split_by_topic/01_age_rules.yaml` and `examples/rules/from_another_directory/global_age_rule.yaml`, summarized
Expected: an empty failure table and counts that are all passes
