# Rule names a code whose suite was not loaded

The default rule file disables two soft_tests codes, so loading only hard_tests
is an error rather than a silent skip.

Input:    `python3 examples/main.py -e hard_tests`
Expected: stderr `ValueError: rule ... unknown code 'EMAIL_MISSING_AT'. ...`; exit 1
