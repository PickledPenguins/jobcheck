# Last file wins

Precedence is positional: for a given row, the last matching rule decides.

Level:    moderate
Input:    `examples/rules/split_by_topic/01_age_rules.yaml`, `examples/rules/split_by_topic/02_email_rules.yaml`, `examples/rules/from_another_directory/global_age_rule.yaml`
Expected: the global rule, listed last, overrides the age rules before it
