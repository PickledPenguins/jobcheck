# The worst row, explained

Row 3 has a negative age, which fails one test and blocks none -- while the
blank-age rows block four. The explanation names, for every test, whether it
ran, was disabled by a rule, or was skipped because a prerequisite did not pass.

Level:    complex
Input:    row 3 of `examples/data/customers.csv`, with two rule files loaded
Expected: one line per registered test, then the root cause; exit 0

Why this combination:

This is the view a person opens when the report is right and they do not
believe it. Every other output aggregates; this one accounts for one row
completely, including the tests that produced nothing.
