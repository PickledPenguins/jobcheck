# Legacy rows get a stricter check

A rule that switches a check *on* for chosen rows rather than off.

Level:    moderate
Input:    `examples/data/customers.csv` with `examples/rules/split_by_topic/01_age_rules.yaml`
Expected: `AGE_NOT_INTEGER`, off by default, reported for the legacy rows only
