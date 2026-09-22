# Explain a legacy row

The other direction: a rule turning a check on shows up as a check that evaluated --
and here, failed, because the row's age is `58.5`.

Level:    moderate
Input:    row 13 (`1014`, `LEGACY_A`/`BATCH`) of `examples/data/customers.csv` with `examples/rules/split_by_topic/01_age_rules.yaml`
Expected: `AGE_NOT_INTEGER`, off by default, `failed` with `value=58.5` because the rule
          enabled it for this row; `root cause: AGE_NOT_INTEGER`; exit 0
