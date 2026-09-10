# `match` key omitted

Input:    `python3 examples/main.py -o tests/failures/missing-match/rules.yaml`
Expected: stderr `missing 'match'. Use 'match: all' to apply the rule to every row.`; exit 1
