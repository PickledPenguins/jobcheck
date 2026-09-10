# `-vv`: source files and the by-rule table

Adds `source_file` to both registry tables and prints a third table organised by
rule rather than by code.

Level:    moderate
Input:    `python3 examples/main.py -vv`
Expected: both tables with `source_file`, plus `== Override rules (by rule) ==`; exit 0
