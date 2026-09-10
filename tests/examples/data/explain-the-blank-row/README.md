# Explain the blank row

Row 21 of the file is entirely empty. `--explain` shows what every test did on
one row -- including the ones that never ran, and why.

Level:    simple
Input:    row 21 of `examples/data/customers.csv`
Expected: one line per test with its outcome, and the root cause underneath; exit 0
