# `-e` repeated instead of multi-valued

Occurrences are flattened in the order typed, so this matches the multi-value form.

Level:    simple
Input:    `python3 examples/main.py -e hard_tests -e soft_tests`
Expected: identical output to `-e hard_tests soft_tests`; exit 0
