# A clean file as CSV

An empty CSV report still carries its header, so a downstream reader does not have to special-case it.

Level:    simple
Input:    `examples/data/customers_clean.csv`
Expected: the header row and nothing under it
