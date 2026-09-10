# The same files reversed

The same three files in the other order, to show the ordering is the whole mechanism.

Level:    moderate
Input:    `examples/rules/from_another_directory/global_age_rule.yaml`, `examples/rules/split_by_topic/01_age_rules.yaml`, `examples/rules/split_by_topic/02_email_rules.yaml`
Expected: the age rules now win, because they are read after the global one
