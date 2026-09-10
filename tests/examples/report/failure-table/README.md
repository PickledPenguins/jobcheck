# The failure report

One line per failed test per row, with the status, the layer it sits at, the
message, and the comments the test attached. `is_root_cause` marks the first
failure of each row -- the one everything else follows from.

Level:    simple
Input:    `python3 examples/main.py --report table`
Expected: the registry tables, then a bordered failure table; exit 0
