# The same report as CSV

Same columns, unwrapped, for a spreadsheet or another tool. The library writes
it; the flag only chooses the format.

Input:    `python3 examples/main.py --report csv`
Expected: a CSV header row followed by one line per failure; exit 0
