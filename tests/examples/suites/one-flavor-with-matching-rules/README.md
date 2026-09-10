# One suite, with a rule file limited to that suite

Narrowing the suites means narrowing the rules too: a rule naming a soft_tests
code would be a load-time error here.

Input:    `python3 examples/main.py -e hard_tests -o examples/rules/split_by_topic/01_age_rules.yaml`
Expected: no EMAIL codes anywhere; exit 0
