# Showing what a failure blocked

Adds the tests that never ran because a prerequisite failed, each naming the
prerequisite. Use it when the question is "why did nothing fire?" rather than
"what is wrong with this row?".

Level:    simple
Input:    `python3 examples/main.py --include-skipped --report table`
Expected: extra rows with outcome `skipped` and a `prerequisite did not pass` note; exit 0
