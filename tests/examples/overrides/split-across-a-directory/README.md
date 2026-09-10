# Rules split across two files

The two files together carry the same first two rules as the single root file.
The global `match: all` rule is not loaded here, so the legacy batch row keeps
the enable from `01_age_rules.yaml`.

Level:    moderate
Input:    `python3 examples/main.py -o examples/rules/split_by_topic/01_age_rules.yaml examples/rules/split_by_topic/02_email_rules.yaml`
Expected: row 3 (the LEGACY_A/BATCH row) reports AGE_NOT_INTEGER; exit 0
