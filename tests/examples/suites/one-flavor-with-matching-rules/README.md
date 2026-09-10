# One suite, with a rule file limited to that suite

Narrowing the suites means narrowing the rules too: a rule naming a soft_checks
code would be a load-time error here.

Level:    moderate
Input:    `python3 examples/main.py -e hard_checks -o examples/rules/split_by_topic/01_age_rules.yaml`
Expected: no EMAIL codes anywhere; exit 0
