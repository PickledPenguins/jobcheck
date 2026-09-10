# `-e` repeated instead of multi-valued

Occurrences are flattened in the order typed, so this matches the multi-value form.

Level:    simple
Input:    `python3 examples/main.py -e hard_checks -e soft_checks`
Expected: identical output to `-e hard_checks soft_checks`; exit 0
