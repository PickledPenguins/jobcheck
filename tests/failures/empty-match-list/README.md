# `match: []` instead of `match: all`

An empty list is far more likely an accidental omission than a deliberate global
rule, so it is rejected.

Input:    `python3 examples/main.py -o tests/failures/empty-match-list/rules.yaml`
Expected: stderr ends with the "Use 'match: all'" guidance; exit 1
