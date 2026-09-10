# Three rule files in order

Precedence over a real export, where the row count makes the effect visible in the counts.

Level:    complex
Input:    `examples/data/customers.csv` with `examples/rules/split_by_topic/01_age_rules.yaml`, `examples/rules/split_by_topic/02_email_rules.yaml`, `examples/rules/from_another_directory/global_age_rule.yaml`
Expected: the age rules overridden by the global rule that follows them
