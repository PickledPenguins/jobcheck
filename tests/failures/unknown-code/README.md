# Code misspelled in a rule

Input:    `python3 examples/main.py -o tests/failures/unknown-code/rules.yaml`
Expected: stderr `unknown code 'AGE_NEGATIV'. Load the suite that defines it before loading overrides, or fix the code.`; exit 1
