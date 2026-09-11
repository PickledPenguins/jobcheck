# Every level of failure in one run

Presence failures, shape failures and range failures together in one file, with
two rule files pulling in opposite directions -- the email rules exempting rows
the global age rule does not -- rendered as CSV and then counted. The output is
the one a pipeline hands on, and the counts are what a person reads instead.

Level:    complex
Input:    `examples/data/customers.csv` with `examples/rules/split_by_topic/02_email_rules.yaml` and `examples/rules/from_another_directory/global_age_rule.yaml`
Expected: a CSV report carrying every kind of failure, then the per-check counts
          and the root cause of each failing row; exit 0
