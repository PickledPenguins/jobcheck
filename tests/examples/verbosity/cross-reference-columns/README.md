# `-v`: which rules could affect each code

Adds `could_be_overridden_by`. It lists rules that *reference* a code, not rules
that fired -- that is a per-row question.

Level:    moderate
Input:    `python3 examples/main.py -v`
Expected: registry table with a `could_be_overridden_by` column; no source files; exit 0
