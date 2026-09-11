# Age rules on a file with nothing wrong

One topic's rules over a clean export. The rules still load and still apply --
they change which checks run, not whether the data is good -- so the report is
empty and the registry table shows the age checks the rules could touch.

Level:    simple
Input:    `examples/data/customers_clean.csv` (24 clean rows) with `examples/rules/split_by_topic/01_age_rules.yaml`
Expected: `No failures.`; exit 0
