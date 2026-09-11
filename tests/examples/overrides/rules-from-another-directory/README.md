# Rules from another directory

Rule files are named one by one, so they can live wherever the pipeline keeps them.

Level:    moderate
Input:    `examples/rules/split_by_topic/01_age_rules.yaml` and `examples/rules/from_another_directory/global_age_rule.yaml`
Expected: both loaded; rule files need not share a directory
