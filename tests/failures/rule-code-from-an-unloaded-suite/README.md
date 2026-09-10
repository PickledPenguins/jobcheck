# Rule names a code whose suite was not loaded

The default rule file disables two soft_checks codes, so loading only hard_checks
is an error rather than a silent skip.

Input:    `python3 examples/main.py -e hard_checks`
Expected: stderr `ValueError: rule ... unknown code 'EMAIL_MISSING_AT'. ...`; exit 1
